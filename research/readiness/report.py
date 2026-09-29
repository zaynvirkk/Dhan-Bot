"""Audit the frozen replay and export individual bankrolls, never live approval."""
import csv
import json
from decimal import Decimal as D

from research.gauntlet.data import save
from .experiment import OUT, STRATEGIES, digest, inputs

START = D('9411.18')


def money(value):
    return 'UNKNOWN' if value is None else f'{D(value):,.2f}'


def main():
    source = digest()
    days, data, audits = inputs()
    noise = json.loads((OUT/'noise.json').read_text())
    assert (noise['source_hash'], noise['data_hash']) == (source, data)
    controls = {(r['period'], r['strategy']): r for r in noise['rows']}
    scores, ledgers, scenarios = [], [], 0
    for quality in ('reported', 'strict'):
        doc = json.loads((OUT/(quality+'.json')).read_text())
        assert (doc['source_hash'], doc['data_hash']) == (source, data)
        assert doc['calendar_days_per_window'] == 90
        assert len(doc['runs']) == len(STRATEGIES)*2*2*5
        scenarios += len(doc['runs'])
        lookup = {(r['period'], r['strategy'], r['scenario']): r for r in doc['runs']}
        for r in doc['runs']:
            cash = START
            for row in r['ledger']:
                assert D(row['cash_before']) == cash
                if row['status'] == 'MODELED_EXIT':
                    assert row['quantity'] % row['lot'] == 0
                    assert D(row['cash_after'])-cash == D(row['pnl'])
                    assert abs((D(row['exit'])-D(row['entry']))*row['quantity']-D(row['fees'])-D(row['pnl'])) < D('.00000001')
                    cash = D(row['cash_after'])
                if quality == 'reported' and r['scenario'] == 'primary':
                    ledgers.append({'period': r['period'], 'strategy': r['strategy'], **row})
            if r['final_bankroll'] is not None:
                assert cash.quantize(D('.01')) == D(r['final_bankroll'])
            if r['scenario'] != 'primary':
                continue
            scores.append({
                'period': r['period'], 'quality': quality, 'strategy': r['strategy'],
                'calendar_days': 90, 'final_bankroll': r['final_bankroll'],
                'signals': r['counts'].get('signals', 0), 'trades': r['counts'].get('trades', 0),
                'wins': r['counts'].get('wins', 0), 'misses': r['counts'].get('misses', 0),
                'unknown': r['unknown'], 'max_closed_drawdown': r['closed_drawdown'],
                'intrabar_mark_drawdown': r['intrabar_mark_drawdown'],
                **{s: lookup[r['period'], r['strategy'], s]['final_bankroll']
                   for s in ('delay2', 'delay3', 'open_plus_1pct', 'delete_best')},
                'conditional_direction_p': controls[r['period'], r['strategy']]['p'] if quality == 'reported' else None,
                'adjusted_p': controls[r['period'], r['strategy']]['adjusted_p'] if quality == 'reported' else None,
            })
    for name, rows in [('scoreboard.csv', scores), ('ledger.csv', ledgers)]:
        keys = list(dict.fromkeys(k for row in rows for k in row))
        with (OUT/name).open('w') as stream:
            writer = csv.DictWriter(stream, fieldnames=keys)
            writer.writeheader()
            writer.writerows([{k: json.dumps(v) if isinstance(v, (list, dict)) else v for k, v in row.items()} for row in rows])
    by = {(r['period'], r['strategy']): r for r in scores if r['quality'] == 'reported'}
    strict = {(r['period'], r['strategy']): r for r in scores if r['quality'] == 'strict'}
    positive, survivors = [], []
    for strategy in sorted({r['strategy'] for r in scores}):
        pair = [by[p, strategy] for p in ('earlier', 'recent')]
        if all(r['final_bankroll'] is not None and D(r['final_bankroll']) > START for r in pair):
            positive.append(strategy)
        if all(all(r[s] is not None and D(r[s]) > START for s in ('final_bankroll', 'delete_best', 'delay2', 'delay3'))
               and r['adjusted_p'] is not None and r['adjusted_p'] < .05 for r in pair):
            if all(strict[p, strategy]['final_bankroll'] is not None and D(strict[p, strategy]['final_bankroll']) > START for p in ('earlier', 'recent')):
                survivors.append(strategy)
    counts = {p: {'sessions': sum(x['partition'] == p for x in days.values()),
                  'expiries': sum(x['partition'] == p and x.get('expiry_day', False) for x in days.values())}
              for p in ('earlier', 'recent')}
    ncontrols = sum(len(r['controls']) for r in noise['rows'])
    save(OUT/'decision.json', {
        'status': 'NO_LIVE_CERTIFICATION', 'winner': None, 'source_hash': source, 'data_hash': data,
        'scenarios': scenarios, 'noise_paths': ncontrols, 'positive_both_windows': positive,
        'research_screen_survivors': survivors, 'audits': audits, 'session_counts': counts,
        'calendar_days_per_strategy_per_window': 90,
        'notes': ['Retrospective same dates; no new holdout.', 'Model P&L does not prove bid/ask fills.',
                  'Missing paths remain UNKNOWN.', 'No order or deployment approval is generated.'],
    })
    lines = ['# Additional NIFTY reversal and breakout experiment', '',
        'Every variant starts independently with **INR 9,411.18** in each 90-calendar-day window: '
        '**23 March–20 June** and **21 June–18 September 2026**. Earlier/recent session counts are '
        f'{counts["earlier"]["sessions"]}/{counts["recent"]["sessions"]}, with '
        f'{counts["earlier"]["expiries"]}/{counts["recent"]["expiries"]} expiries. These dates have '
        'already been examined; this is retrospective research, not a new holdout.', '',
        f'Computed **{scenarios} execution scenarios** and **{ncontrols:,} random-direction paths**. '
        'Verified whole-lot and cash/P&L algebra for every resolved ledger row.', '',
        f'Positive in both reported-candle windows: **{positive or "none"}**. '
        f'Passing the stricter profit, delayed-fill, best-trade-deletion, data-quality and '
        f'multiplicity screen: **{survivors or "none"}**. No live strategy is certified.', '',
        '| Variant | Earlier bankroll | Recent bankroll | Recent trades | Recent without best | Recent +2-minute delay |',
        '|---|---:|---:|---:|---:|---:|']
    for strategy in sorted({r['strategy'] for r in scores}):
        a, b = by['earlier', strategy], by['recent', strategy]
        lines.append(f'| {strategy} | {money(a["final_bankroll"])} | {money(b["final_bankroll"])} | '
                     f'{b["trades"]} | {money(b["delete_best"])} | {money(b["delay3"])} |')
    lines += ['', '## Evidence limits', '',
        'The table is conditional on reported provider candles. Strict results and all misses are in '
        '[scoreboard.csv](scoreboard.csv) and [ledger.csv](ledger.csv). UNKNOWN is an unresolved '
        'path, not a no-trade day or an unchanged bankroll. A known unchanged balance with zero '
        'fills also provides no evidence of profit.', '',
        f'Exact-contract-day audits for this batch, including reused tapes: `{audits}`. '
        'Source disagreement, off-tick prices and missing order-time data are preserved; strict '
        'audit failures cannot be used to skip a historical loss and continue compounding.', '',
        'Only completed bars enter signals. The first signal is fixed before collecting its '
        'option outcomes. ATM-relative rows are matched by absolute strike before computing OI '
        'changes. The bounded same-strike data does not establish historical publication latency '
        'or dealer positioning. Present depth cannot fill missing historical books.', '',
        'Orders use a precommitted limit and whole-lot size, a fee reserve, adverse minute bars '
        'and 5% volume participation; fills and target touches remain assumptions. One-, two- '
        'and three-minute delays do not measure one-second execution. Current fee envelopes '
        'are conservative approximations, not historical broker invoices.', '',
        'Random-direction controls condition on the observed first-signal timestamps. Holm '
        'correction counts at least 80 variants, while the wider conversation contains more '
        'research choices. It cannot transform a reused period into independent validation.', '',
        'This batch extends NIFTY expiry and ordinary-session research. It does not complete '
        'all nine earlier full-universe strategies. The event families still need complete '
        'timestamped disclosures, and CAS requires indicative-price and book histories.', '',
        '[Frozen rules](../../readiness/PROTOCOL.md) · '
        '[Previous 64-variant experiment](../multifeature90/FINDINGS.md)', '',
        f'Source SHA-256: `{source}`', f'Data SHA-256: `{data}`']
    (OUT/'REPORT.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({'scenarios': scenarios, 'noise_paths': ncontrols, 'positive_both': positive,
                      'screen_survivors': survivors, 'ledger_rows': len(ledgers)}), flush=True)


if __name__ == '__main__':
    main()
