"""Late-expiry and long-volatility replay. Market-data endpoints only."""
import argparse
import hashlib
import json
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from math import ceil
from pathlib import Path
from statistics import median

from research.gauntlet.core import Bar, Contract, D, Order, entry, tick_up, tick_down
from research.gauntlet.data import CACHE, ROOT, save
from research.expiry.collect import option_file, fetch
from research.expiry.signals import stamp
from research.multifeature.providers import STORE as OLD
from research.multifeature.quality import tape_issues
from dhan_cas_bot.risk import FeeSchedule

STORE = CACHE / 'finalsearch'
OUT = ROOT / 'research/results/finalsearch'
START = D('9411.18')
NAMES = ('EXPIRY_STRADDLE_1445', 'EXPIRY_STRADDLE_1500', 'EXPIRY_STRADDLE_1515',
         'EXPIRY_STRANGLE_1500', 'EXPIRY_STRANGLE_1515', 'EXPIRY_CHEAP_STRADDLE_1500',
         'ORDINARY_CHEAP_STRADDLE_1000', 'EXPIRY_LATE_OI_EVACUATION')

def source_hash():
    paths = list(Path(__file__).parent.glob('*.py')) + [Path(__file__).with_name('PROTOCOL.md')]
    paths += [ROOT / f for f in ('research/gauntlet/core.py', 'dhan_cas_bot/risk.py',
                                'research/expiry/collect.py', 'research/multifeature/quality.py')]
    return hashlib.sha256(b''.join(str(p.relative_to(ROOT)).encode() + p.read_bytes() for p in sorted(paths))).hexdigest()

def data():
    inst = json.loads((OLD / 'instruments.json').read_text())
    spot = {b.available: b for b in map(Bar.parse, json.loads((OLD / 'indexes/NIFTY.json').read_text())['bars'])}
    # Warm-up only: preserve all outcome-period inputs unchanged.
    for row in json.loads((CACHE / 'expiry_research/spot.json').read_text()):
        b = Bar.parse(row)
        if b.start.date().isoformat() < '2026-03-23':
            if b.available in spot and spot[b.available] != b: raise ValueError('conflicting warm-up index row')
            spot[b.available] = b
    return inst, spot

def choose(chain, spot, strangle=False):
    strikes = sorted(set(c.strike for c in chain if c.side == 'CE') & set(c.strike for c in chain if c.side == 'PE'))
    if not strikes: raise ValueError('MISSING_COMMON_STRIKE')
    atm = min(strikes, key=lambda k: (abs(k - spot), k))
    ce = next((k for k in strikes if k > atm), None) if strangle else atm
    pe = next((k for k in reversed(strikes) if k < atm), None) if strangle else atm
    if ce is None or pe is None: raise ValueError('MISSING_STRANGLE_WING')
    return [next(c for c in chain if c.side == s and c.strike == k) for s, k in [('CE', ce), ('PE', pe)]]

def prepare():
    if not (OUT / 'registration.json').exists():
        save(OUT / 'registration.json', {'registered_at': datetime.now(timezone.utc).isoformat(),
             'protocol_sha256': hashlib.sha256(Path(__file__).with_name('PROTOCOL.md').read_bytes()).hexdigest(),
             'variants': list(NAMES), 'retrospective': True, 'calendar_days_per_window': 90})
    inst, spot = data(); plan = {}; jobs = {}
    for day, x in sorted(inst.items()):
        if 'error' in x: plan[day] = x; continue
        chain = [Contract.parse(m) for m in x['chain'].values()]
        candidates = {}; gaps = {}
        for name in NAMES:
            if name.startswith('EXPIRY') != x['expiry_day']: continue
            times = [f'15:{m:02}' for m in range(10, 20)] if name.endswith('EVACUATION') else [name[-4:-2] + ':' + name[-2:]]
            choices = []
            for hhmm in times:
                at = stamp(day, hhmm); b = spot.get(at)
                if b is None: gaps[name] = 'MISSING_SPOT:' + at.isoformat(); break
                try:
                    selected = choose(chain, b.close, 'STRANGLE' in name)
                    if name.endswith('EVACUATION'):
                        selected += choose(chain, b.close, True)
                    choices.append({'at': at.isoformat(), 'spot': str(b.close), 'keys': [c.key for c in selected]})
                    for c in selected: jobs[day, c.key] = {'day': day, 'key': c.key}
                except ValueError as exc: gaps[name] = str(exc); break
            candidates[name] = choices
        plan[day] = {'partition': x['partition'], 'expiry_day': x['expiry_day'], 'candidates': candidates, 'gaps': gaps}
    save(STORE / 'plan.json', plan); save(STORE / 'jobs.json', list(jobs.values()))
    print('registered', len(NAMES), 'variants;', len(plan), 'sessions;', len(jobs), 'exact contract-days', flush=True)

def collect():
    from research.gauntlet.option_history import plan_ranges, day_path, fetch_range
    inst, _ = data(); jobs = json.loads((STORE / 'jobs.json').read_text())
    pending = [{'contract_key': j['key'], 'day': j['day']} for j in jobs
               if not option_file(j['day'], j['key']).exists() and not day_path(j['key'], j['day']).exists()]
    ranges = plan_ranges(pending); print('new requests', len(ranges), flush=True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        for i, f in enumerate(as_completed([pool.submit(fetch_range, r) for r in ranges]), 1):
            f.result()
            if i % 20 == 0: print('collected', i, '/', len(ranges), flush=True)
    audit = {}
    for j in jobs:
        d, k = j['day'], j['key']; x = inst[d]; record = x['official'].get(k.split('|')[1])
        audit[d + ' ' + k] = fetch(d, k, x['chain'][k], record) if record else {'status': 'UNKNOWN_OFFICIAL_RECORD'}
    save(STORE / 'collection.json', audit)
    print('audits', dict(Counter(r['status'] for r in audit.values())), flush=True)

def load():
    inst, spot = data(); plan = json.loads((STORE / 'plan.json').read_text()); tapes = {}; errors = {}; hashes = []; audit = Counter()
    paths = [STORE / 'plan.json', STORE / 'jobs.json', OLD / 'instruments.json', OLD / 'indexes/NIFTY.json', CACHE / 'expiry_research/spot.json']
    for j in json.loads((STORE / 'jobs.json').read_text()):
        d, k = j['day'], j['key']; f = option_file(d, k)
        if not f.exists(): errors[d, k] = ['UNKNOWN_REQUEST']; continue
        paths.append(f); raw = json.loads(f.read_text()); assert raw['day'] == d and raw['key'] == k
        rows = list(map(Bar.parse, raw['bars'])); tapes[d, k] = {b.start: b for b in rows}
        errors[d, k] = tape_issues(raw, rows); audit.update(errors[d, k] or ['RECONCILED'])
    for f in sorted(set(paths)): hashes.append(str(f.relative_to(ROOT)) + hashlib.sha256(f.read_bytes()).hexdigest())
    return inst, spot, plan, tapes, errors, hashlib.sha256('\n'.join(hashes).encode()).hexdigest(), dict(audit)

def basket_order(contracts, known, at, cash):
    """Choose size only from contemporaneously known data, never entry bars."""
    lots = {c.lot for c in contracts}
    if len(lots) != 1: raise ValueError('inconsistent basket lot')
    lot = next(iter(lots)); limits = []; capacities = []
    for c in contracts:
        rows = known[c.key]
        if any(b.available > at for b in rows): raise ValueError('future in order snapshot')
        recent = sorted((b for b in rows if at - timedelta(minutes=3) <= b.start < at), key=lambda b: b.start)
        if len(recent) != 3 or recent[-1].available != at: return [], 'UNKNOWN_RECENT_MINUTES'
        last = recent[-1]
        if last.close <= 0 or last.oi < 10 * lot: return [], 'KNOWN_ILLIQUID'
        limits.append(tick_up(last.close * D('1.05'), c.tick))
        capacities.append(int(D(min(b.volume for b in recent)) * D('.05')) // lot * lot)
    qty = min(int(cash * D('.95') / (sum(limits) * lot)) * lot, min(capacities))
    fee = FeeSchedule()
    while qty > 0:
        cost = sum((p * qty + fee.buy(p * qty, ceil(qty / c.freeze)) for c, p in zip(contracts, limits)), D(0))
        reserve = sum((fee.sell(D(0), ceil(qty / c.freeze)) * 3 for c in contracts), D(0))
        if cost <= cash * D('.95') and cost + reserve <= cash:
            return [Order(c, at, p, qty, 'finalsearch', known[c.key][-1].close) for c, p in zip(contracts, limits)], 'ORDER_CREATED'
        qty -= lot
    return [], 'UNAFFORDABLE_OR_PAST_CAPACITY'

def forecast(spot, day, at):
    prior = sorted({t.date().isoformat() for t in spot if t.date().isoformat() < day})[-20:]
    if len(prior) != 20: raise ValueError('UNKNOWN_BASELINE_SESSIONS')
    changes = []
    for d in prior:
        begin, end = spot.get(stamp(d, at.strftime('%H:%M'))), spot.get(stamp(d, '15:25'))
        if begin is None or end is None: raise ValueError('UNKNOWN_BASELINE_MINUTE')
        changes.append(abs(end.close - begin.close))
    return median(changes) * D('.8')

def flow(contracts, at, spot, tape):
    """One fixed absolute contract, completed bars only, first chronological event."""
    prices = [spot.get(at - timedelta(minutes=i)) for i in (2, 1, 0)]
    if any(b is None for b in prices): raise ValueError('UNKNOWN_FLOW_SPOT')
    matches = []
    for c in contracts:
        direction = 1 if c.side == 'CE' else -1
        if not (direction * (prices[0].close - c.strike) <= 0 and all(direction * (b.close - c.strike) > 0 for b in prices[1:])): continue
        rows = [tape[c.key].get(at - timedelta(minutes=i + 1)) for i in range(33)]
        if any(b is None for b in rows): raise ValueError('UNKNOWN_FLOW_OPTION')
        if rows[3].oi <= 0 or rows[3].close <= 0: raise ValueError('UNKNOWN_FLOW_REFERENCE')
        baseline = median(sum(b.volume for b in rows[i:i+3]) for i in range(3, 33, 3))
        if baseline <= 0: continue
        if rows[0].close >= rows[3].close * D('1.25') and rows[0].oi <= D(rows[3].oi) * D('.92') and sum(b.volume for b in rows[:3]) >= 4 * baseline:
            matches.append(c)
    return sorted(matches, key=lambda c: (abs(c.strike - prices[-1].close), c.side))[:1]

def trade(orders, tape, day, cash, delay=1, adverse=True, exit_haircut=D(0)):
    fee = FeeSchedule(); fills = []; misses = []; bought = D(0); costs = D(0)
    for o in orders:
        fill = entry(o, list(tape[o.contract.key].values()), delay_bars=delay, adverse=adverse)
        if fill['status'].startswith('UNKNOWN'): return {'status': fill['status'], 'at': fill['time']}
        if fill['status'] != 'MODELED_FILL': misses.append(fill['status']); continue
        turnover = fill['price'] * o.quantity; f = fee.buy(turnover, ceil(o.quantity / o.contract.freeze))
        fills.append((o, fill)); bought += turnover; costs += f
    if not fills: return {'status': 'NO_FILL', 'misses': misses}
    cash_free = cash - bought - costs
    assert cash_free >= 0
    partial = len(fills) < len(orders)
    at = max(f['bar'].available for o, f in fills)
    close_at = stamp(day, '15:35' if day >= '2026-08-03' else '15:25')
    deadline = close_at + timedelta(minutes=2)
    exit_at = at if partial else close_at
    reason = 'PARTIAL_ENTRY_UNWIND' if partial else 'TIMED_CLOSE'
    remaining = {o.contract.key: o.quantity for o, f in fills}; parts = []; proceeds = D(0)
    worst = cash; peak = cash; drawdown = D(0); triggered = partial
    while at <= min(deadline, exit_at + timedelta(minutes=2)):
        rows = {o.contract.key: tape[o.contract.key].get(at) for o, f in fills if remaining[o.contract.key]}
        if any(b is None for b in rows.values()): return {'status': 'UNKNOWN_HOLDING_BAR', 'at': at.isoformat(), 'cash_free': str(cash_free), 'parts': parts}
        mark = cash_free + proceeds + sum((b.close * remaining[k] for k, b in rows.items()), D(0))
        worst = min(worst, mark); peak = max(peak, mark); drawdown = max(drawdown, 1 - mark / peak)
        if at >= exit_at:
            for o, f in fills:
                k = o.contract.key
                if not remaining[k]: continue
                b = rows[k]; qty = min(remaining[k], int(D(b.volume) * D('.05')) // o.contract.lot * o.contract.lot)
                if not qty: continue
                price = tick_down(b.low * (1 - exit_haircut), o.contract.tick)
                gross = price * qty; sellfee = fee.sell(gross, ceil(qty / o.contract.freeze))
                proceeds += gross - sellfee; costs += sellfee; remaining[k] -= qty
                parts.append({'key': k, 'at': at.isoformat(), 'price': str(price), 'quantity': qty, 'fee': str(sellfee)})
            if not any(remaining.values()):
                end = cash_free + proceeds
                return {'status': 'RESOLVED', 'cash_after': str(end), 'pnl': str(end - cash), 'costs': str(costs),
                        'reason': reason, 'entry_at': fills[0][1]['time'], 'exit_at': at.isoformat(),
                        'minutes_exposed': int((at - datetime.fromisoformat(fills[0][1]['time'])).total_seconds() / 60),
                        'partial_entry': partial, 'worst_mark': str(min(worst, end)), 'peak_mark': str(peak), 'intratrade_drawdown': str(max(drawdown, 1 - end / peak)),
                        'fills': [{'key': o.contract.key, 'quantity': o.quantity, 'lot': o.contract.lot, 'limit': str(o.limit), 'price': str(f['price'])} for o, f in fills], 'parts': parts}
        else:
            combined = sum((rows[o.contract.key].close * o.quantity for o, f in fills), D(0))
            # Completed simultaneous closes trigger, then processing delay.
            if not triggered and (combined >= bought * 2 or combined <= bought / 2):
                exit_at = min(exit_at, at + timedelta(minutes=1 + delay))
                reason = 'COMPLETED_CLOSE_2X' if combined >= bought * 2 else 'COMPLETED_CLOSE_HALF_LOSS'
                triggered = True
        at += timedelta(minutes=1)
    return {'status': 'UNKNOWN_EXIT_CAPACITY', 'at': deadline.isoformat(), 'remaining': remaining, 'parts': parts, 'cash_free': str(cash_free)}

def run(inputs, name, period, quality='reported', delay=1, adverse=True, exit_haircut=D(0), skip=None):
    inst, spot, plan, tapes, errors, _, _ = inputs
    cash = START; peak = cash; maxdd = D(0); counts = Counter(); ledger = []; best = None; bestp = D(0); unknown = None; double = None
    for day, p in sorted(plan.items()):
        if p.get('partition') != period: continue
        if 'error' in p: unknown = [day, p['error']]; break
        if name not in p['candidates']: continue
        if name in p['gaps']: unknown = [day, p['gaps'][name]]; break
        for choice in p['candidates'][name]:
            at = datetime.fromisoformat(choice['at']); cs = [Contract.parse(inst[day]['chain'][k]) for k in choice['keys']]
            if any((day, c.key) not in tapes for c in cs): unknown = [day, 'UNKNOWN_TAPE']; break
            if quality == 'strict' and any(errors.get((day, c.key)) for c in cs): unknown = [day, 'UNKNOWN_SOURCE_AUDIT']; break
            tape = {c.key: tapes[day, c.key] for c in cs}
            try:
                if name.endswith('EVACUATION'):
                    cs = flow(cs, at, spot, tape)
                    if not cs: continue
                known = {c.key: sorted((b for b in tape[c.key].values() if b.available <= at), key=lambda b: b.start) for c in cs}
                if 'CHEAP' in name:
                    if any(not v or v[-1].available != at for v in known.values()): raise ValueError('UNKNOWN_PREMIUM_REFERENCE')
                    if sum(v[-1].close for v in known.values()) >= forecast(spot, day, at):
                        counts['FILTERED_NOT_CHEAP'] += 1; continue
                counts['signals'] += 1
                if day == skip: counts['DELETED_BEST_DAY'] += 1; break
                orders, status = basket_order(cs, known, at, cash)
                row = {'day': day, 'signal_at': at.isoformat(), 'cash_before': str(cash), 'status': status}
                if status.startswith('UNKNOWN'): raise ValueError(status)
                if not orders: counts[status] += 1; ledger.append(row); break
                result = trade(orders, tape, day, cash, delay, adverse, exit_haircut); row.update(result); ledger.append(row)
                counts[result['status']] += 1
                if result['status'].startswith('UNKNOWN'): unknown = [day, result['status']]; break
                if result['status'] == 'RESOLVED':
                    counts['trades'] += 1; cash = D(result['cash_after']); pnl = D(result['pnl'])
                    counts['wins' if pnl > 0 else 'losses'] += 1; counts[result['reason']] += 1
                    counts['exposure_minutes'] += result['minutes_exposed']
                    maxdd = max(maxdd, 1 - D(result['worst_mark']) / peak, D(result['intratrade_drawdown']))
                    peak = max(peak, cash, D(result['peak_mark']))
                    if pnl > bestp: bestp = pnl; best = day
                    if cash >= START * 2 and double is None: double = day
                break
            except ValueError as exc: unknown = [day, str(exc)]; break
        if unknown: break
    return {'strategy': name, 'period': period, 'quality': quality, 'final_bankroll': str(cash) if unknown is None else None,
            'last_resolved_bankroll': str(cash), 'unknown': unknown, 'counts': dict(counts), 'max_drawdown': str(maxdd),
            'first_double_date': double, 'best_trade_day': best, 'ledger': ledger}

def replay():
    inputs = load(); sh = source_hash(); rows = []
    for quality in ('reported', 'strict'):
        for period in ('earlier', 'recent'):
            for name in NAMES:
                base = run(inputs, name, period, quality); base['scenario'] = 'primary'; rows.append(base)
                if quality == 'reported':
                    for scenario, opts in [('delay2', {'delay': 2}), ('delay3', {'delay': 3}),
                                           ('open_plus_1pct', {'adverse': False}), ('exit_haircut_1pct', {'exit_haircut': D('.01')}),
                                           ('delete_best', {'skip': base['best_trade_day']})]:
                        r = run(inputs, name, period, quality, **opts); r['scenario'] = scenario; rows.append(r)
                print(quality, period, name, base['final_bankroll'], base['counts'].get('trades', 0), base['unknown'], flush=True)
    assert sh == source_hash()
    save(OUT / 'results.json', {'source_sha256': sh, 'input_sha256': inputs[5], 'audits': inputs[6], 'runs': rows})

if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('stage', choices=['prepare', 'collect', 'replay']); a = p.parse_args(); globals()[a.stage]()
