"""Date controls matched using only information available before each entry."""
import hashlib
import json
import random
from collections import Counter, defaultdict
from functools import lru_cache
from statistics import pstdev

from research.gauntlet.core import D
from research.gauntlet.data import ROOT, save
from .data import STORE, OUT, NAME, PERIODS, calendar
from . import replay


def matched_groups(plan, raw_spot, contract_map):
    closes = {}
    for r in sorted(raw_spot):
        closes[r[0][:10]] = D(str(r[4]))
    days = sorted(closes)
    vols = {}
    groups = {}
    errors = {}
    for i, day in enumerate(days):
        if i >= 21:
            # The current session's close is explicitly excluded.
            past = [closes[d] for d in days[i-21:i]]
            vol = pstdev(float(b/a-1) for a, b in zip(past, past[1:]))
            prior = [vols[d] for d in days[max(0, i-60):i] if d in vols]
            vols[day] = vol
            if day not in plan or 'potential' not in plan[day]:
                continue
            if not prior:
                errors[day] = 'MISSING_PRIOR_VOLATILITY_BUCKET'
                continue
            # Rolling past-only tercile rank, no full-sample quantiles.
            bucket = min(2, sum(v <= vol for v in prior)*3//len(prior))
            s = plan[day]['potential']
            raw = contract_map.get('|'.join((day, 'NIFTY', s['exit_day'], 'CE')))
            if not raw or 'error' in raw or not raw['contracts'] or 'expiry' not in raw['contracts'][0]:
                errors[day] = 'UNKNOWN_CONTROL_CONTRACT'
                continue
            from datetime import date
            expiry = raw['contracts'][0]['expiry']
            dte = (date.fromisoformat(expiry)-date.fromisoformat(day)).days
            groups[day] = (plan[day]['partition'], dte, bucket)
    return groups, errors


def sample_dates(groups, signal_days, seed):
    pool = defaultdict(list)
    for day, group in sorted(groups.items()):
        pool[group].append(day)
    counts = Counter(groups[d] for d in signal_days)
    rng = random.Random(seed)
    selected = []
    for group, n in sorted(counts.items()):
        if len(pool[group]) < n:
            raise ValueError('INSUFFICIENT_MATCHED_DATE_POOL')
        selected += rng.sample(pool[group], n)
    return set(selected)


def main():
    ds = replay.Dataset()
    observed = {r['period']: r for r in json.loads((OUT/'upstox.json').read_text())['runs'] if r['scenario'] == 'primary'}
    groups, errors = matched_groups(ds.plan, json.loads((STORE/'spot.json').read_text()), ds.contracts)
    save(OUT/'control_design.json', {'matching': '15:10, exact calendar DTE, past-only rolling 20-session volatility tercile',
         'groups': groups, 'errors': errors, 'seeds': [0, 998], 'outcome_independent_pool': True})
    original_trade = replay.trade

    @lru_cache(maxsize=40000)
    def cached(encoded, o, quality, delay, slip, entry_model):
        return original_trade(ds, json.loads(encoded), o, quality, delay, slip, entry_model)

    def fast_trade(dataset, s, o, quality='reported', delay=1, slip=1, entry_model='high'):
        assert dataset is ds
        return dict(cached(json.dumps(s, sort_keys=True), o, quality, delay, slip, entry_model))

    results = []
    for part in PERIODS:
        base = replay.run(ds, part)
        assert base['ledger'] == observed[part]['ledger']
        replay.trade = fast_trade
        assert replay.run(ds, part) == base
        signals = [d for d, x in ds.plan.items() if x['partition'] == part and NAME in x['signals']]
        missing = [d for d, x in ds.plan.items() if x['partition'] == part and 'potential' in x and d not in groups]
        if missing:
            results.append({'period': part, 'status': 'UNKNOWN_MATCHING_COVERAGE', 'dates': missing})
            replay.trade = original_trade
            continue
        local_groups = {d: g for d, g in groups.items() if g[0] == part}
        paths = []
        for seed in range(999):
            dates = sample_dates(local_groups, signals, seed)
            r = replay.run(ds, part, selected_days=dates)
            paths.append({'seed': seed, 'dates': sorted(dates), 'final_bankroll': r['final_bankroll'],
                          'unknown': r['unknown'], 'trades': r['counts'].get('trades', 0)})
            if (seed+1) % 100 == 0:
                print(part, 'date controls', seed+1, flush=True)
                save(OUT/'controls_progress.json', {'period': part, 'paths': paths})
        unknown = sum(p['final_bankroll'] is None for p in paths)
        better = sum(p['final_bankroll'] is not None and base['final_bankroll'] is not None and
                     D(p['final_bankroll']) >= D(base['final_bankroll']) for p in paths)
        results.append({'period': part, 'status': 'CONDITIONAL_MATCHED_DATE_RANDOMIZATION',
                        'observed': base['final_bankroll'], 'paths': paths, 'unknown': unknown,
                        'at_least_observed': better, 'tail_lower': (better+1)/1000 if base['final_bankroll'] else None,
                        'tail_upper': (better+unknown+1)/1000 if base['final_bankroll'] else None,
                        'adjusted_144_upper': min(1, 144*(better+unknown+1)/1000) if base['final_bankroll'] else None})
        replay.trade = original_trade
        save(OUT/'controls.json', {'source_sha256': replay.source_hash(), 'results': results,
             'input_hashes': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(ds.used)}})
    replay.trade = original_trade


if __name__ == '__main__':
    main()
