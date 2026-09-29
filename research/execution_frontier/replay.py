"""Frozen execution scenarios, causal signals and independent bankroll paths."""
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from math import ceil

from research.gauntlet.core import Bar, Contract, D, Order, tick_down, tick_up
from research.gauntlet.data import ROOT, save
from research.rebound_validation import replay as parent
from research.rebound_validation.data import STORE, PERIODS, close_time
from research.rebound_validation.fees import schedule
from research.expiry.signals import stamp

OUT = ROOT/'research/results/execution_frontier'
RULES = ('SELLOFF_CALL', 'SELLOFF_PUT', 'RALLY_PUT', 'RALLY_CALL',
         'TWO_SIDED_REVERSAL', 'TWO_SIDED_CONTINUATION', 'TREND_PULLBACK', 'TREND_CONTINUATION')
ALLOCATIONS = (D('.25'), D('.50'), D('.95'))
SCENARIOS = {
    'rest3': {}, 'arrival_open': {'entry_model': 'open'},
    'delay3': {'delay': 3}, 'slippage2': {'slip': 2},
    'tight_limit': {'cap': D('.01')}, 'strict': {'quality': 'strict'},
}


def digest():
    files = sorted((ROOT/'research/execution_frontier').glob('*.py'))
    files += [ROOT/'research/execution_frontier/PROTOCOL.md']
    return hashlib.sha256(parent.source_hash().encode()+b''.join(
        str(p.relative_to(ROOT)).encode()+p.read_bytes() for p in files)).hexdigest()


def direction(rule, ret, trend):
    if abs(ret) < D('.0075'):
        return None
    reversal = 'CE' if ret < 0 else 'PE'
    continuation = 'PE' if ret < 0 else 'CE'
    if rule == 'SELLOFF_CALL': return 'CE' if ret < 0 else None
    if rule == 'SELLOFF_PUT': return 'PE' if ret < 0 else None
    if rule == 'RALLY_PUT': return 'PE' if ret > 0 else None
    if rule == 'RALLY_CALL': return 'CE' if ret > 0 else None
    if rule == 'TWO_SIDED_REVERSAL': return reversal
    if rule == 'TWO_SIDED_CONTINUATION': return continuation
    if rule.startswith('TREND_') and trend is None:
        raise ValueError('UNKNOWN_PRIOR_TREND')
    if rule == 'TREND_PULLBACK': return reversal if ret*trend < 0 else None
    if rule == 'TREND_CONTINUATION': return continuation if ret*trend > 0 else None
    raise ValueError('UNKNOWN_RULE')


def prior_trends(rows):
    daily = defaultdict(list)
    for b in map(Bar.parse, rows): daily[b.start.date().isoformat()].append(b)
    days = sorted(daily)
    closes = {d: max(bs, key=lambda b: b.start).close for d, bs in daily.items()}
    return {d: closes[days[i-1]]/closes[days[i-21]]-1 if i >= 21 else None
            for i, d in enumerate(days)}


def order_for(c, known, at, cash, allocation, cap):
    if len(known) != 3 or any(b is None for b in known):
        raise ValueError('UNKNOWN_DECISION_BARS')
    if [b.start for b in known] != [at-timedelta(minutes=i) for i in (3, 2, 1)] or any(b.available > at for b in known):
        raise ValueError('FUTURE_OR_STALE_DECISION_DATA')
    if known[-1].close <= 0 or known[-1].oi < 10*c.lot:
        return None, 'ZERO_PRICE_OR_LOW_OI'
    limit = tick_up(known[-1].close*(1+cap), c.tick)
    capacity = int(D(min(b.volume for b in known))*D('.05'))//c.lot
    high = min(int(cash*allocation/(limit*c.lot)), capacity)
    fees = schedule(at.date().isoformat())
    low = 0
    while low < high:
        n = (low+high+1)//2; q = n*c.lot; turn = q*limit; children = ceil(q/c.freeze)
        cost = turn+fees.buy(turn, children)
        if cost <= cash*allocation and cost+3*fees.sell(D(0), children) <= cash:
            low = n
        else:
            high = n-1
    if low:
        return Order(c, at, limit, low*c.lot, 'FRONTIER', known[-1].close), 'ORDER_CREATED'
    return None, 'UNAFFORDABLE_OR_PAST_CAPACITY'


def select(ds, s, cash, side, allocation, cap, quality):
    raw = ds.contracts.get('|'.join((s['day'], 'NIFTY', s['exit_day'], side)))
    if raw is None or 'error' in raw: raise ValueError('UNKNOWN_CONTRACT_SELECTION')
    trace = []; at = datetime.fromisoformat(s['at'])
    for m in raw['contracts']:
        if 'unresolved_key' in m: raise ValueError('UNKNOWN_EXACT_METADATA')
        c = Contract.parse(m)
        if c.expiry <= s['exit_day'] or c.side != side: raise ValueError('INVALID_CONTRACT')
        rows = ds.rows(s, c, s['day'], quality)
        known = [rows.get(at-timedelta(minutes=i)) for i in (3, 2, 1)]
        o, status = order_for(c, known, at, cash, allocation, cap)
        trace.append({'contract': c.key, 'status': status})
        if o: return o, trace
    return None, trace


def fill(order, rows, delay=1, entry_model='rest'):
    c = order.contract
    arrival = order.decided+timedelta(minutes=delay)
    for minute in range(1 if entry_model == 'open' else 3):
        at = arrival+timedelta(minutes=minute)
        b = rows.get(at)
        if b is None: raise ValueError('UNKNOWN_ENTRY_BAR')
        if entry_model == 'open':
            px = tick_up(b.open*D('1.01'), c.tick)
            crossed = px <= order.limit
        else:
            px = order.limit
            crossed = b.low <= order.limit-2*c.tick
        if not crossed or b.volume == 0: continue
        if D(order.quantity) > D(b.volume)*D('.05'):
            raise ValueError('UNKNOWN_PARTIAL_ENTRY')
        return {'status': 'MODELED_FILL', 'price': px,
                'at': b.start if entry_model == 'open' else b.available,
                'evidence_bar': b.start.isoformat()}
    return {'status': 'LIMIT_DEADLINE_MISS'}


def trade(ds, s, order, quality='reported', delay=1, slip=1, entry_model='rest'):
    c = order.contract
    rows = ds.rows(s, c, s['day'], quality)
    entry = fill(order, rows, delay, entry_model)
    if entry['status'] != 'MODELED_FILL': return entry
    px = entry['price']; when = entry['at']; at = when
    exit_at = datetime.fromisoformat(s['exit_at'])
    remaining = order.quantity; parts = []; pending = False; attempts = 0
    reason = 'TIMED_CLOSE'; trigger = None; worst = px
    current_day = s['day']; end_index = ds.days.index(s['exit_day'])
    while True:
        day = at.date().isoformat()
        if at >= close_time(day):
            i = ds.days.index(day)
            if i >= end_index: raise ValueError('UNKNOWN_EXIT_AFTER_DEADLINE')
            at = stamp(ds.days[i+1], '09:15'); day = at.date().isoformat()
        if day != current_day:
            rows = ds.rows(s, c, day, quality); current_day = day
        b = rows.get(at)
        if b is None: raise ValueError('UNKNOWN_HOLDING_BAR:'+at.isoformat())
        # Resting entry is placed at preceding bar end; this bar is post-fill.
        if entry_model != 'open' or at > when: worst = min(worst, b.low)
        if at >= exit_at:
            attempts += 1
            q = min(remaining, int(D(b.volume)*D('.05'))//c.lot*c.lot)
            if q:
                price = tick_down(b.low*(1-D('.01')*slip), c.tick)
                parts.append({'at': at.isoformat(), 'quantity': q, 'price': str(price)})
                remaining -= q
            if not remaining:
                return {'status': 'RESOLVED', 'entry': str(px), 'entry_at': when.isoformat(),
                        'entry_evidence_bar': entry['evidence_bar'], 'exit_at': b.available.isoformat(),
                        'exit_parts': parts, 'trigger_at': trigger, 'reason': reason, 'worst': str(worst)}
            if attempts >= 3: raise ValueError('UNKNOWN_EXIT_CAPACITY')
        elif not pending and (b.close >= 2*px or b.close <= D('.5')*px):
            proposed = b.available+timedelta(minutes=delay)
            if proposed < exit_at:
                exit_at = proposed; pending = True; trigger = b.available.isoformat()
                reason = 'TARGET_CLOSE' if b.close >= 2*px else 'STOP_CLOSE'
        at += timedelta(minutes=1)


def run(ds, trends, period, rule, allocation, *, quality='reported', delay=1,
        slip=1, entry_model='rest', cap=D('.05'), skip=None):
    cash = parent.START; peak = cash; dd = D(0); busy = ''; counts = Counter()
    ledger = []; unknown = None; best = None; best_pnl = D(0)
    for day, x in sorted(ds.plan.items()):
        if x['partition'] != period: continue
        counts['sessions'] += 1
        if busy and day <= busy: counts['busy'] += 1; continue
        if x['errors']:
            unknown = [day, 'UNKNOWN_SIGNAL_DATA']; break
        s = x.get('potential')
        if s is None: continue  # Last session cannot liquidate within the window.
        try: side = direction(rule, D(s['detail']['session_return']), trends.get(day))
        except ValueError as e: unknown = [day, str(e)]; break
        if side is None: continue
        counts['signals'] += 1
        if day == skip: counts['deleted_best'] += 1; continue
        row = {'day': day, 'side': side, 'signal_at': s['at'], 'cash_before': str(cash)}
        try:
            o, trace = select(ds, s, cash, side, allocation, cap, quality)
            row['selection'] = trace
            if o is None:
                row['status'] = 'NO_AFFORDABLE_CONTRACT'; counts['no_order'] += 1
                ledger.append(row); continue
            c = o.contract
            row.update(contract=c.key, expiry=c.expiry, strike=str(c.strike), quantity=o.quantity,
                       lot=c.lot, freeze=c.freeze, limit=str(o.limit), reference_close=str(o.reference_close))
            result = trade(ds, s, o, quality, delay, slip, entry_model); row.update(result)
            if result['status'] != 'RESOLVED':
                counts['misses'] += 1; ledger.append(row); continue
            buy = D(result['entry'])*o.quantity
            sell = sum((D(p['price'])*p['quantity'] for p in result['exit_parts']), D(0))
            fees = schedule(day).buy(buy, ceil(o.quantity/c.freeze))
            fees += sum((schedule(p['at'][:10]).sell(D(p['price'])*p['quantity'], ceil(p['quantity']/c.freeze))
                         for p in result['exit_parts']), D(0))
            after = cash-buy+sell-fees
            if after < 0: raise ValueError('NEGATIVE_CASH')
            pnl = after-cash
            dd = max(dd, 1-(cash-buy+D(result['worst'])*o.quantity-fees)/peak, 1-after/peak)
            cash = after; peak = max(peak, cash); busy = result['exit_at'][:10]
            counts['trades'] += 1; counts['wins' if pnl > 0 else 'losses'] += 1
            if pnl > best_pnl: best = day; best_pnl = pnl
            row.update(cash_after=str(cash), pnl=str(pnl), fees=str(fees)); ledger.append(row)
        except Exception as e:
            row.update(status='UNKNOWN', error=type(e).__name__+':'+str(e)); ledger.append(row)
            unknown = [day, row['error']]; break
    return {'strategy': rule, 'allocation': str(allocation), 'period': period,
            'provider': ds.provider, 'entry_model': entry_model, 'delay_minutes': delay,
            'cap': str(cap), 'slip_multiplier': slip, 'quality': quality, 'counts': dict(counts),
            'final_bankroll': None if unknown else str(cash.quantize(D('.01'))),
            'resolved_cash': str(cash), 'model_drawdown': str(dd), 'unknown': unknown,
            'best_trade_day': best, 'ledger': ledger}


def main():
    ds = parent.Dataset()
    trends = prior_trends(json.loads((STORE/'spot.json').read_text()))
    runs = []
    for rule in RULES:
        for allocation in ALLOCATIONS:
            for period in PERIODS:
                base = None
                for name, kw in SCENARIOS.items():
                    r = run(ds, trends, period, rule, allocation, **kw); r['scenario'] = name
                    if name == 'rest3': base = r
                    runs.append(r)
                r = run(ds, trends, period, rule, allocation, skip=base['best_trade_day'])
                r['scenario'] = 'delete_best'; runs.append(r)
                print(rule, allocation, period, base['final_bankroll'], base['counts'], base['unknown'], flush=True)
        inputs = ds.used | set((STORE/'official').glob('*.json')) | {STORE/'signals.json', STORE/'contracts.json', STORE/'spot.json'}
        save(OUT/'runs.json', {'source_sha256': digest(), 'runs': runs, 'audits': ds.audits,
             'input_hashes': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(inputs)}})
    print('Completed', len(runs), 'scenario attempts', flush=True)


if __name__ == '__main__': main()
