"""Read-only point-in-time data for the locked rebound validation."""
import argparse
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from functools import lru_cache

from research.gauntlet.core import Bar, Contract, D
from research.gauntlet.data import CACHE, ROOT, candles, contracts, public, save
from research.gauntlet.contracts import metadata
from research.gauntlet.option_history import day_path, fetch_range
from research.broader.prepare import raw_rows
from research.expiry.signals import stamp

STORE = CACHE / 'rebound_validation'
OUT = ROOT / 'research/results/rebound_validation'
NAME = 'NIFTY_SELLOFF_REBOUND_FULL_SESSION_V2'
PERIODS = {'validation': ('2025-12-23', '2026-03-22'),
           'earlier': ('2026-03-23', '2026-06-20'),
           'recent': ('2026-06-21', '2026-09-18')}


def close_time(day):
    return stamp(day, '15:40' if day >= '2026-08-03' else '15:30')


def partition(day):
    return next((p for p, (a, b) in PERIODS.items() if a <= day <= b), None)


def prepare_spot():
    """Collect declared period plus past-only volatility warm-up, never fit."""
    dest = STORE / 'spot.json'
    if dest.exists():
        return
    existing = json.loads((CACHE / 'expiry_research/spot.json').read_text())
    rows = [r for r in existing if r[0][:10] >= '2025-11-01']
    # Overlap is validated, not silently overwritten.
    end = min(r[0][:10] for r in rows)
    start = date(2025, 11, 1)
    while start.isoformat() < end:
        stop = min(start + timedelta(days=27), date.fromisoformat(end) - timedelta(days=1))
        rows += candles('NSE_INDEX|Nifty 50', start.isoformat(), stop.isoformat())
        print('underlying block', start, stop, flush=True)
        start = stop + timedelta(days=1)
    by = {}
    for r in rows:
        Bar.parse(r)
        if r[0] in by and by[r[0]] != r:
            raise ValueError('CONFLICTING_SPOT')
        by[r[0]] = r
    save(dest, sorted(by.values()))


@lru_cache(maxsize=1)
def calendar():
    return sorted({r[0][:10] for r in json.loads((STORE / 'spot.json').read_text())})


@lru_cache(maxsize=12)
def exchange(day):
    name = f'BhavCopy_NSE_FO_0_0_0_{day.replace("-", "")}_F_0000.csv.zip'
    path = CACHE / 'public' / name
    if not path.exists():
        old = CACHE / 'event90/public' / name
        if old.exists():
            path = old
        else:
            public('https://nsearchives.nseindia.com/content/fo/' + name, name)
    rows = raw_rows(path)
    if not rows or {r['TradDt'] for r in rows} != {day}:
        raise ValueError('OFFICIAL_DATE_MISMATCH')
    save(STORE/'official'/f'{day}.json', {
        'day': day, 'source_path': str(path.relative_to(ROOT)),
        'source_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'nifty_options': [r for r in rows if r['TckrSymb'] == 'NIFTY' and r['FinInstrmTp'] == 'IDO']})
    return rows


def signal(day, bars, next_day):
    """Decision uses completed data only; independent of future option tape."""
    at = stamp(day, '15:10')
    op = bars.get(stamp(day, '09:15'))
    last = bars.get(at - timedelta(minutes=1))
    if op is None or last is None or last.available > at or op.open <= 0:
        raise ValueError('UNKNOWN_SIGNAL_BAR')
    ret = last.close / op.open - 1
    return {'name': NAME, 'at': at.isoformat(), 'day': day, 'side': 'CE',
            'symbol': 'NIFTY', 'key': 'NSE_INDEX|Nifty 50', 'spot': str(last.close),
            'exit_day': next_day, 'exit_at': stamp(next_day, '15:10').isoformat(),
            'mode': 'INDEX', 'detail': {'session_return': str(ret)},
            'fires': ret <= D('-.0075')}


def prepare_plan():
    prepare_spot()
    bars = {b.start: b for b in map(Bar.parse, json.loads((STORE / 'spot.json').read_text()))}
    days = calendar()
    plan = {}
    for i, day in enumerate(days):
        part = partition(day)
        if not part:
            continue
        x = {'partition': part, 'signals': {}, 'errors': {}}
        if i + 1 < len(days) and days[i+1] <= PERIODS[part][1]:
            try:
                s = signal(day, bars, days[i+1])
                x['potential'] = s
                if s['fires']:
                    x['signals'][NAME] = s
            except ValueError as e:
                x['errors'][NAME] = str(e)
        plan[day] = x
    save(STORE / 'signals.json', plan)
    print('sessions', {p: sum(x['partition'] == p for x in plan.values()) for p in PERIODS},
          'signals', {p: sum(x['partition'] == p and NAME in x['signals'] for x in plan.values()) for p in PERIODS}, flush=True)


@lru_cache(maxsize=128)
def exact(expiry):
    return {m['instrument_key']: m for m in contracts('NSE_INDEX|Nifty 50', expiry)}


def candidates(s, side='CE'):
    days = calendar()
    prior = days[days.index(s['day'])-1]
    eligible = [metadata(r) for r in exchange(prior)
                if r['TckrSymb'] == 'NIFTY' and r['FinInstrmTp'] == 'IDO'
                and r['OptnTp'] == side and (r.get('FininstrmActlXpryDt') or r['XpryDt']) > s['exit_day']]
    if not eligible:
        return []
    expiry = min(c.expiry for c in eligible)
    chain = [c for c in eligible if c.expiry == expiry]
    spot = D(s['spot'])
    atm = min(chain, key=lambda c: (abs(c.strike-spot), c.strike)).strike
    chain = sorted([c for c in chain if (c.strike >= atm if side == 'CE' else c.strike <= atm)],
                   key=lambda c: abs(c.strike-atm))[:4]
    out = []
    for c in chain:
        # The dated NSE row can have been cached while a contract was active.
        # Upstox now returns the expired key for the same exchange token/expiry.
        m = next((v for k, v in exact(expiry).items()
                  if k.split('|')[1] == c.key.split('|')[1] and v['expiry'] == c.expiry), None)
        if m is None:
            out.append({'unresolved_key': c.key})
            continue
        parsed = Contract.parse(m)
        if (parsed.expiry, parsed.lot, parsed.side, parsed.strike) != (c.expiry, c.lot, c.side, c.strike):
            raise ValueError('CONTRACT_DISAGREEMENT')
        out.append(m)
    return out


def prepare_contracts(all_dates=False):
    plan = json.loads((STORE / 'signals.json').read_text())
    dest = STORE / 'contracts.json'
    out = json.loads(dest.read_text()) if dest.exists() else {}
    jobs = [x['potential'] for x in plan.values() if 'potential' in x and (all_dates or x['potential']['fires'])]
    for i, s in enumerate(jobs):
        for side in ('CE', 'PE'):
            key = '|'.join((s['day'], 'NIFTY', s['exit_day'], side))
            if key in out and 'error' not in out[key]:
                continue
            try:
                out[key] = {'contracts': candidates(s, side)}
            except Exception as e:
                out[key] = {'error': type(e).__name__ + ':' + str(e)}
        save(dest, out)
        print('contracts', i+1, '/', len(jobs), s['day'], flush=True)


def raw_option(c, day, network=True):
    p = day_path(c.key, day)
    if not p.exists() and network:
        fetch_range({'key': c.key, 'days': [day]})
    if not p.exists():
        raise ValueError('MISSING_OPTION_DAY')
    x = json.loads(p.read_text())
    if x['key'] != c.key or x['day'] != day:
        raise ValueError('TAPE_IDENTITY_MISMATCH')
    return [Bar.parse(r) for r in x['bars']], p


def audit(c, day, bars):
    row = next((r for r in exchange(day) if r['FinInstrmId'] == c.key.split('|')[1]), None)
    if row is None:
        raise ValueError('MISSING_OFFICIAL_CONTRACT')
    if metadata(row).expiry != c.expiry or D(row['StrkPric']) != c.strike or row['OptnTp'] != c.side:
        raise ValueError('OFFICIAL_CONTRACT_IDENTITY')
    issues = []
    expected = int(row['TtlTradgVol']) * int(row['NewBrdLotQty'])
    actual = sum(b.volume for b in bars)
    if actual != expected:
        issues.append('VOLUME_MISMATCH')
    if any(getattr(b, p) % c.tick for b in bars for p in ('open', 'high', 'low', 'close')):
        issues.append('OFF_TICK')
    if not bars:
        issues.append('EMPTY_TAPE')
    elif any(b.volume for b in bars) and (max(b.high for b in bars if b.volume) > D(row['HghPric'])+c.tick or min(b.low for b in bars if b.volume) < D(row['LwPric'])-c.tick):
        issues.append('OFFICIAL_RANGE_MISMATCH')
    return {'issues': issues, 'expected_volume': expected, 'actual_volume': actual,
            'official_high': row['HghPric'], 'official_low': row['LwPric'], 'rows': len(bars)}


def normalize(c, day, bars, receipt):
    by = {}
    for b in bars:
        if b.start.date().isoformat() != day:
            raise ValueError('WRONG_TAPE_DAY')
        if b.start in by and b != by[b.start]:
            raise ValueError('CONFLICTING_DUPLICATE_BAR')
        by[b.start] = b
    if receipt['actual_volume'] != receipt['expected_volume']:
        return by
    last = None
    at = stamp(day, '09:15')
    while at < close_time(day):
        if at in by:
            last = by[at]
        elif last is not None:
            # Actual no-trade observation; zero capacity. No future backfill.
            by[at] = Bar(at, last.close, last.close, last.close, last.close, 0, last.oi)
        at += timedelta(minutes=1)
    return by


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('stage', choices=['plan', 'contracts', 'all_contracts'])
    a = p.parse_args()
    if a.stage == 'plan':
        prepare_plan()
    else:
        prepare_contracts(a.stage == 'all_contracts')
