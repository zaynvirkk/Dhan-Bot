"""Full-session, chronological validation. No live order client is imported."""
import argparse
import hashlib
import json
import random
from math import ceil
from collections import Counter
from datetime import datetime, timedelta
from functools import lru_cache

from research.gauntlet.core import Contract, D, tick_down, tick_up
from research.gauntlet.data import ROOT, save
from research.expiry.fast_order import make_order
from research.expiry.signals import stamp
from research.intraday_challengers.experiment import reserve
from research.broader.replay import fee
from .data import STORE, OUT, NAME, PERIODS, calendar, close_time, raw_option, audit, normalize

START = D('9411.18')


def source_hash():
    files = sorted((ROOT / 'research/rebound_validation').glob('*.py'))
    files += [ROOT / p for p in ('research/rebound_validation/PROTOCOL.md', 'research/gauntlet/core.py',
              'research/expiry/fast_order.py', 'research/intraday_challengers/experiment.py',
              'research/broader/replay.py', 'research/broader/prepare.py',
              'research/gauntlet/data.py', 'research/gauntlet/contracts.py', 'research/gauntlet/option_history.py',
              'research/expiry/signals.py', 'research/multifeature/providers.py',
              'dhan_cas_bot/auth.py', 'dhan_cas_bot/risk.py')]
    return hashlib.sha256(b''.join(str(p.relative_to(ROOT)).encode()+p.read_bytes() for p in files)).hexdigest()


class Dataset:
    def __init__(self, network=True, provider='upstox'):
        self.plan = json.loads((STORE / 'signals.json').read_text())
        self.contracts = json.loads((STORE / 'contracts.json').read_text())
        self.days = calendar()
        self.network = network
        self.provider = provider
        self.used = set()
        self.audits = {}
        self.cache = {}

    def rows(self, s, c, day, quality='reported'):
        key = (c.key, day)
        if key not in self.cache:
            if self.provider == 'upstox':
                bars, p = raw_option(c, day, self.network)
            else:
                from .dhan_history import fixed_contract
                bars, p = fixed_contract(c, day, self.network)
            self.used.add(p)
            receipt = audit(c, day, bars)
            self.audits['|'.join(key)] = receipt
            self.cache[key] = normalize(c, day, bars, receipt)
        issues = self.audits['|'.join(key)]['issues']
        if quality == 'strict' and issues:
            raise ValueError('UNKNOWN_SOURCE_AUDIT:' + ','.join(issues))
        return self.cache[key]


def select(ds, s, cash, side='CE', quality='reported', fee_model='conservative'):
    at = datetime.fromisoformat(s['at'])
    key = '|'.join((s['day'], 'NIFTY', s['exit_day'], side))
    raw = ds.contracts.get(key)
    if raw is None or 'error' in raw:
        raise ValueError('UNKNOWN_CONTRACT_SELECTION')
    trace = []
    for m in raw['contracts']:
        if 'unresolved_key' in m:
            raise ValueError('UNKNOWN_EXACT_METADATA:' + m['unresolved_key'])
        c = Contract.parse(m)
        if c.expiry <= s['exit_day'] or c.side != side:
            raise ValueError('INVALID_EXPIRY_OR_SIDE')
        rows = ds.rows(s, c, s['day'], quality)
        known = [rows.get(at-timedelta(minutes=i)) for i in (3, 2, 1)]
        if any(b is None for b in known):
            raise ValueError('UNKNOWN_DECISION_BARS')
        if fee_model == 'dated':
            from .fees import make_order as dated_order, schedule
            order, status = dated_order(c, known, at, cash, NAME, schedule(s['day']))
        else:
            order, status = make_order(c, known, at, cash, NAME)
        if order:
            order = reserve(order, cash)
            if order is None:
                status = 'EXIT_FEE_RESERVE'
        trace.append({'key': c.key, 'status': status})
        if order:
            return order, trace
    return None, trace


def trade(ds, s, order, quality='reported', delay=1, slip=1, entry_model='high'):
    c = order.contract
    when = order.decided + timedelta(minutes=delay)
    rows = ds.rows(s, c, s['day'], quality)
    b = rows.get(when)
    if b is None:
        raise ValueError('UNKNOWN_ENTRY_BAR')
    px = tick_up(b.high if entry_model == 'high' else b.open*D('1.01'), c.tick)
    if px > order.limit:
        return {'status': 'LIMIT_MISS'}
    if D(order.quantity) > D(b.volume)*D('.05'):
        return {'status': 'CAPACITY_MISS'}
    scheduled = datetime.fromisoformat(s['exit_at'])
    exit_at = scheduled
    trigger_at = None
    reason = 'TIMED_CLOSE'
    pending = False
    parts = []
    remaining = order.quantity
    attempts = 0
    at = when
    low = px
    end_index = ds.days.index(s['exit_day'])
    current_day = s['day']
    while True:
        day = at.date().isoformat()
        if at >= close_time(day):
            i = ds.days.index(day)
            if i >= end_index:
                raise ValueError('UNKNOWN_EXIT_AFTER_DEADLINE')
            at = stamp(ds.days[i+1], '09:15')
            day = at.date().isoformat()
        if day != current_day:
            rows = ds.rows(s, c, day, quality)
            current_day = day
        b = rows.get(at)
        if b is None:
            raise ValueError('UNKNOWN_HOLDING_BAR:' + at.isoformat())
        # Entry-bar low could precede entry; do not claim it as post-fill loss.
        if at > when:
            low = min(low, b.low)
        if at >= exit_at:
            attempts += 1
            q = min(remaining, int(D(b.volume)*D('.05'))//c.lot*c.lot)
            if q:
                price = tick_down(b.low*(1-D('.01')*slip), c.tick)
                parts.append({'at': at.isoformat(), 'quantity': q, 'price': str(price)})
                remaining -= q
            if not remaining:
                return {'status': 'RESOLVED', 'entry': str(px), 'entry_at': when.isoformat(),
                        'exit_at': b.available.isoformat(), 'exit_parts': parts,
                        'trigger_at': trigger_at, 'reason': reason, 'worst': str(low)}
            if attempts >= 3:
                raise ValueError('UNKNOWN_EXIT_CAPACITY')
        elif not pending and (b.close >= 2*px or b.close <= D('.5')*px):
            proposed = b.available + timedelta(minutes=delay)
            if proposed < exit_at:
                exit_at = proposed
                trigger_at = b.available.isoformat()
                pending = True
                reason = 'TARGET_CLOSE' if b.close >= 2*px else 'STOP_CLOSE'
        at += timedelta(minutes=1)


def run(ds, period, *, quality='reported', delay=1, slip=1, entry_model='high', skip=None,
        selected_days=None, seed=None, fee_model='conservative'):
    cash = START
    peak = cash
    dd = D(0)
    busy = ''
    counts = Counter()
    ledger = []
    unknown = None
    best = None
    best_pnl = D(0)
    rng = random.Random(seed)
    for day, x in sorted(ds.plan.items()):
        if x['partition'] != period:
            continue
        counts['sessions'] += 1
        if busy and day <= busy:
            counts['busy'] += 1
            continue
        if NAME in x['errors']:
            unknown = [day, x['errors'][NAME]]
            break
        s = x['signals'].get(NAME) if selected_days is None else x.get('potential') if day in selected_days else None
        if s is None:
            continue
        counts['signals'] += 1
        if day == skip:
            counts['deleted_best'] += 1
            continue
        side = 'CE' if seed is None else rng.choice(['CE', 'PE'])
        row = {'day': day, 'side': side, 'signal_at': s['at'], 'cash_before': str(cash)}
        try:
            o, trace = select(ds, s, cash, side, quality, fee_model)
            row['selection'] = trace
            if o is None:
                row['status'] = 'NO_AFFORDABLE_CONTRACT'
                counts['no_order'] += 1
                ledger.append(row)
                continue
            row.update(contract=o.contract.key, expiry=o.contract.expiry, strike=str(o.contract.strike),
                       quantity=o.quantity, lot=o.contract.lot, freeze=o.contract.freeze, limit=str(o.limit))
            result = trade(ds, s, o, quality, delay, slip, entry_model)
            row.update(result)
            if result['status'] != 'RESOLVED':
                counts['misses'] += 1
                ledger.append(row)
                continue
            buy = D(result['entry'])*o.quantity
            sell = sum((D(p['price'])*p['quantity'] for p in result['exit_parts']), D(0))
            fees = fee(buy, 'BUY', o.contract, False, o.quantity)
            fees += sum((fee(D(p['price'])*p['quantity'], 'SELL', o.contract, False, p['quantity']) for p in result['exit_parts']), D(0))
            if fee_model == 'dated':
                from .fees import schedule
                fees = schedule(day).buy(buy, ceil(o.quantity/o.contract.freeze))
                fees += sum((schedule(p['at'][:10]).sell(D(p['price'])*p['quantity'], ceil(p['quantity']/o.contract.freeze))
                             for p in result['exit_parts']), D(0))
            after = cash-buy+sell-fees
            if after < 0:
                raise ValueError('NEGATIVE_CASH')
            pnl = after-cash
            dd = max(dd, 1-(cash-buy+D(result['worst'])*o.quantity-fees)/peak, 1-after/peak)
            cash = after
            peak = max(peak, cash)
            busy = result['exit_at'][:10]
            counts['trades'] += 1
            counts['wins' if pnl > 0 else 'losses'] += 1
            if pnl > best_pnl:
                best_pnl = pnl
                best = day
            row.update(cash_after=str(cash), pnl=str(pnl), fees=str(fees))
            ledger.append(row)
        except Exception as e:
            row.update(status='UNKNOWN', error=type(e).__name__+':'+str(e))
            ledger.append(row)
            unknown = [day, row['error']]
            break
    return {'strategy': NAME, 'period': period, 'provider': ds.provider, 'quality': quality,
            'delay_minutes': delay, 'slip_multiplier': slip, 'entry_model': entry_model,
            'fee_model': fee_model,
            'final_bankroll': None if unknown else str(cash.quantize(D('.01'))), 'resolved_cash': str(cash),
            'unknown': unknown, 'counts': dict(counts), 'best_trade_day': best,
            'model_drawdown': str(dd), 'ledger': ledger}


def evaluate(provider='upstox'):
    ds = Dataset(provider=provider)
    runs = []
    for period in PERIODS:
        base = run(ds, period)
        base['scenario'] = 'primary'
        runs.append(base)
        print(provider, period, 'primary', base['final_bankroll'], base['counts'], base['unknown'], flush=True)
        for name, kw in [('delay3', {'delay': 3}), ('slippage2', {'slip': 2}),
                         ('open_plus_1pct', {'entry_model': 'open'}),
                         ('dated_fees', {'fee_model': 'dated'}),
                         ('delete_best', {'skip': base['best_trade_day']}), ('strict', {'quality': 'strict'})]:
            r = run(ds, period, **kw)
            r['scenario'] = name
            runs.append(r)
            print(provider, period, name, r['final_bankroll'], r['unknown'], flush=True)
        inputs = ds.used | set((STORE/'official').glob('*.json')) | {STORE / 'signals.json', STORE / 'contracts.json', STORE / 'spot.json'}
        save(OUT / (provider+'.json'), {'source_sha256': source_hash(), 'runs': runs, 'audits': ds.audits,
             'input_hashes': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(inputs)}})


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--provider', choices=['upstox', 'dhan'], default='upstox')
    evaluate(p.parse_args().provider)
