"""Re-execute retained candle scenarios on current kernels without rewriting history.

Cached inputs only. No broker API, downloads, orders, deployment or hash bypass.
Noise controls and the production quote/OMS policy are not recreated here.
"""
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'research/results'
KEYS = ('final_bankroll', 'resolved_cash', 'unknown', 'counts', 'ledger')


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def compare(old, new):
    differences = [key for key in KEYS if old.get(key) != new.get(key)]
    return {'strategy': old['strategy'], 'period': old['period'],
            'quality': old.get('quality'), 'scenario': old['scenario'],
            'matches_retained_path': not differences, 'different_fields': differences,
            'retained_cash': old['final_bankroll'], 'rechecked_cash': new['final_bankroll'],
            'rechecked_unknown': new['unknown'],
            'retained_path_sha256': digest({k: old.get(k) for k in KEYS}),
            'rechecked_path_sha256': digest({k: new.get(k) for k in KEYS})}


def intraday():
    from research.intraday_challengers.experiment import load, run, source_hash
    old = json.loads((OUT / 'intraday_challengers/results.json').read_text())
    days, data_hash, _ = load()
    if data_hash != old['input_sha256']:
        raise ValueError('intraday input drift; do not compare different tapes')
    bases = {(r['strategy'], r['period']): r for r in old['runs'] if r['scenario'] == 'primary'}
    rows = []
    for r in old['runs']:
        name, style = r['strategy'].rsplit('_', 1)
        new = run(days, name, style, r['period'], quality=r['quality'], delay=r['delay'], adverse=r['adverse'],
                  skip=bases[r['strategy'], r['period']]['best_trade_day'] if r['scenario'] == 'delete_best' else None)
        rows.append(compare(r, new))
    return {'old_source': old['source_sha256'], 'current_source': source_hash(), 'data_hash': data_hash, 'rows': rows}


def candle_batch(batch):
    from research.expiry.replay import run
    if batch == 'readiness':
        from research.readiness.experiment import inputs, digest as source_hash
        documents = [dict(json.loads((OUT / batch / (q + '.json')).read_text()), quality=q)
                     for q in ('reported', 'strict')]
    else:
        from research.multifeature.replay import inputs, digest as source_hash
        documents = [json.loads((OUT / 'multifeature90' / (p + '_' + q + '.json')).read_text())
                     for p in ('earlier', 'recent') for q in ('reported', 'strict')]
    rows = []
    input_hashes = {}
    for quality in ('reported', 'strict'):
        days, data_hash, _ = inputs(quality)
        input_hashes[quality] = data_hash
        delayed = None
        for doc in documents:
            if doc['quality'] != quality:
                continue
            if data_hash != doc['data_hash']:
                raise ValueError(batch + ' input drift; do not compare different tapes')
            bases = {(r['strategy'], r['period']): r for r in doc['runs'] if r['scenario'] == 'primary'}
            for r in doc['runs']:
                if r['scenario'] == 'features_lag5' and delayed is None:
                    delayed, _, _ = inputs(quality, True)
                name, style = r['strategy'].rsplit('_', 1)
                view = delayed if r['scenario'] == 'features_lag5' else days
                new = run(view, name, style, r['period'], delay=r['delay'], adverse=r['adverse'],
                          skip=bases[r['strategy'], r['period']]['best_trade_day'] if r['scenario'] == 'delete_best' else None)
                rows.append(compare(r, new))
    return {'old_source': documents[0]['source_hash'], 'current_source': source_hash(),
            'input_hashes': input_hashes, 'rows': rows}


def profit_exits():
    from research.expiry.replay import run
    from research.multifeature.replay import inputs, digest as source_hash
    from research.profit_exits import protected_liquidate
    old = json.loads((OUT / 'profit_exits/comparison.json').read_text())
    rows = []
    for quality in ('reported', 'strict'):
        days, data_hash, _ = inputs(quality)
        if data_hash != old['data_hashes'][quality]:
            raise ValueError('profit-exit input drift')
        relevant = [r for r in old['runs'] if r['quality'] == quality]
        bases = {(r['strategy'], r['period']): r for r in relevant if r['scenario'] == 'primary'}
        for r in relevant:
            name, style = r['strategy'].rsplit('_', 1)
            new = run(days, name, style, r['period'], delay=r['delay'], adverse=r['adverse'],
                      skip=bases[r['strategy'], r['period']]['best_trade_day'] if r['scenario'] == 'delete_best' else None,
                      liquidator=protected_liquidate)
            rows.append(compare(r, new))
    exit_source = sha256((ROOT / 'research/profit_exits.py').read_bytes() + (ROOT / 'dhan_cas_bot/profit_exit.py').read_bytes()).hexdigest()
    return {'old_source': old['source_hash'], 'current_source': source_hash(),
            'old_exit_source': old['exit_source_hash'], 'current_exit_source': exit_source, 'rows': rows}


def legacy_expiry():
    from research.expiry.replay import dataset, run, digest as source_hash
    rows = []
    old_source = None
    for quality in ('reported', 'strict'):
        days, data_hash = dataset(quality)
        for period in ('development', 'recent_validation', 'older_validation', 'all'):
            doc = json.loads((OUT / 'expiry' / (period + '_' + quality + '.json')).read_text())
            old_source = doc['source_hash']
            if doc['data_hash'] != data_hash:
                raise ValueError('legacy expiry input drift')
            bases = {r['strategy']: r for r in doc['runs'] if r['scenario'] == 'primary'}
            for r in doc['runs']:
                name, style = r['strategy'].rsplit('_', 1)
                new = run(days, name, style, period, delay=r['delay'], adverse=r['adverse'],
                          skip=bases[r['strategy']]['best_trade_day'] if r['scenario'] == 'delete_best' else None)
                rows.append(compare(dict(r, quality=quality), new))
    return {'old_source': old_source, 'current_source': source_hash(), 'rows': rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('batch', choices=('intraday', 'multifeature90', 'readiness', 'profit_exits', 'legacy_expiry'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    function = {'intraday': intraday, 'profit_exits': profit_exits, 'legacy_expiry': legacy_expiry}.get(args.batch,
                lambda: candle_batch(args.batch))
    result = function()
    rows = result['rows']
    result['summary'] = {'batch': args.batch, 'scenarios_reexecuted': len(rows),
                         'matched': sum(r['matches_retained_path'] for r in rows),
                         'different': sum(not r['matches_retained_path'] for r in rows),
                         'unresolved': sum(r['rechecked_unknown'] is not None for r in rows),
                         'periods': dict(Counter(r['period'] for r in rows)),
                         'input_hashes_checked': True, 'new_noise_controls': False,
                         'exact_live_policy_quote_replay': False}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result['summary']), flush=True)
    if result['summary']['different']:
        raise SystemExit(2)


if __name__ == '__main__':
    main()
