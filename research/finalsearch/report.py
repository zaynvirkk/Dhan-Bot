"""Validate replay accounting, then emit an auditable bounded-search report."""
import csv, hashlib, json
from collections import Counter
from datetime import datetime, timezone
from math import ceil
from .experiment import OUT, STORE, START, NAMES, D, FeeSchedule, source_hash, load

def main():
    doc = json.loads((OUT / 'results.json').read_text())
    assert doc['source_sha256'] == source_hash(), 'Source changed: rerun experiment'
    assert doc['input_sha256'] == load()[5], 'Inputs changed: rerun experiment'
    registration = json.loads((OUT / 'registration.json').read_text())
    from pathlib import Path
    assert registration['protocol_sha256'] == hashlib.sha256(Path(__file__).with_name('PROTOCOL.md').read_bytes()).hexdigest()
    counts = Counter(); ledger_rows = []; summary = []; primary = {}; fee = FeeSchedule()
    for r in doc['runs']:
        cash = START; last = ''; trades = 0
        for row in r['ledger']:
            assert row['day'] >= last; last = row['day']; assert D(row['cash_before']) == cash
            if row['status'] == 'RESOLVED':
                buys = sum((D(f['price']) * f['quantity'] for f in row['fills']), D(0))
                sells = sum((D(p['price']) * p['quantity'] for p in row['parts']), D(0))
                assert cash - buys + sells - D(row['costs']) == D(row['cash_after'])
                assert cash + D(row['pnl']) == D(row['cash_after'])
                assert datetime.fromisoformat(row['entry_at']) > datetime.fromisoformat(row['signal_at'])
                assert row['exit_at'] > row['entry_at']
                for f in row['fills']:
                    assert f['quantity'] > 0 and f['quantity'] % f['lot'] == 0
                    assert D(f['price']) <= D(f['limit'])
                    parts = [p for p in row['parts'] if p['key'] == f['key']]
                    assert sum(p['quantity'] for p in parts) == f['quantity']
                    assert all(p['quantity'] % f['lot'] == 0 for p in parts)
                cash = D(row['cash_after']); assert cash >= 0
                counts['validated_resolved_trades'] += 1; trades += 1
            ledger_rows.append({**{k: r[k] for k in ('strategy', 'period', 'scenario', 'quality')}, **row})
        assert r['counts'].get('trades', 0) == trades
        assert cash == D(r['last_resolved_bankroll'])
        assert (r['final_bankroll'] is None) == (r['unknown'] is not None)
        if r['final_bankroll'] is not None: assert cash == D(r['final_bankroll'])
        summary.append({**{k: r[k] for k in ('strategy', 'period', 'scenario', 'quality', 'final_bankroll', 'last_resolved_bankroll', 'unknown', 'max_drawdown', 'first_double_date')}, **r['counts']})
        if r['scenario'] == 'primary': primary[r['quality'], r['period'], r['strategy']] = r
    groups = {}
    for r in doc['runs']:
        if r['quality'] == 'reported': groups.setdefault((r['strategy'], r['scenario']), {})[r['period']] = r
    positive = [(n, s) for (n, s), rs in groups.items() if len(rs) == 2 and all(r['final_bankroll'] is not None and D(r['final_bankroll']) > START for r in rs.values())]
    assert not positive, 'Positive candidate must receive registered controls before final decision'
    with (OUT / 'scoreboard.csv').open('w') as f:
        writer = csv.DictWriter(f, fieldnames=sorted(set().union(*(r.keys() for r in summary))))
        writer.writeheader(); writer.writerows(summary)
    (OUT / 'ledger.json').write_text(json.dumps(ledger_rows, separators=(',', ':')))
    def cashstr(v): return 'UNKNOWN' if v is None else f'{D(v):,.2f}'
    lines = ['# Final bounded F&O search — no funded candidate', '',
        'Completed 26–27 September 2026. **No strategy is recommended for live trading.**', '',
        'This pass reviews the major economic families, checks actual current Dhan capital requirements, '
        'and adds eight registered NIFTY late-expiry/long-volatility variants. It does not claim exhaustive '
        'testing of every strategy or completed coverage of all earlier nine broad families.', '',
        'Each variant starts independently with **INR 9,411.18** in **23 March–20 June** and '
        '**21 June–18 September 2026**, two 90-calendar-day windows (59/63 sessions, 13 expiries each). '
        'Both windows were already used in research and are not independent holdouts.', '',
        '| Variant | Earlier bankroll | Recent bankroll | Recent trades / wins | Recent max drawdown |',
        '|---|---:|---:|---:|---:|']
    for n in NAMES:
        e, r = (primary['reported', p, n] for p in ('earlier', 'recent'))
        lines.append(f"| {n} | {cashstr(e['final_bankroll'])} | {cashstr(r['final_bankroll'])} | {r['counts'].get('trades', 0)} / {r['counts'].get('wins', 0)} | {D(r['max_drawdown'])*100:.1f}% |")
    lines += ['', '**These are conditional reported-candle simulations, not actual executions.** '
        'All 16 primary strict-source paths remain UNKNOWN where an input fails audit. '
        'Unchanged balances in the conditional table have no filled trades and supply no profit evidence.', '',
        f"Computed **{len(doc['runs'])} scenarios**: primary, two-/three-minute delay, next-open-plus-1%, "
        'extra exit slippage and best-trade deletion, plus separate strict primary paths. '
        'No same variant/scenario grows cash in both windows. No primary variant doubles its bankroll. '
        'Time-to-doubling is therefore not reached, not zero. The conditional control screen failed '
        'before its registered 999-path noise test; no new p-value or significance claim is made.', '',
        'The largest alternative-model balance is INR 10,753.76 for the cheap-straddle rule in the '
        'earlier window with next-open-plus-1% entries. It does not survive as a winner in the recent '
        'window. This isolated result is retained in scoreboard.csv, not used to change the rule.', '',
        'Many adverse-model pair entries fill only one leg. Those attempts incur a paid unwind; '
        'they are not discarded as no-trades. Minute highs and traded volumes cannot establish '
        'the exact probability of such fills. The alternative entry model also has no two-window winner.', '',
        'Data: 341 exact option contract-days, 11 additional API request batches. Of these, 243 '
        'match NSE daily volume and 98 do not; 12 contain off-tick prices (categories overlap). '
        '239 have neither type of issue. Warm-up uses only earlier index history. No source mismatch '
        'is repaired by future outcomes. Historical queue, spread, depth and subminute latency are absent.', '',
        'The final code reserves exit charges even at tiny remaining cash, latches exit orders, '
        'caps liquidation attempts at three minutes, and makes unresolved holdings UNKNOWN. '
        'See [implementation notes](../../finalsearch/NOTES.md) for accounting corrections discovered '
        'during verification. Fixed strategy thresholds and clocks were not optimized.', '',
        '## Fresh account and capital checks', '',
        'Authenticated read-only Dhan calls verify INR 9,411.18 available and zero positions. '
        'The market was closed; the returned quotes are from 25 September and displayed quantities '
        'are zero. No order was submitted, and the calls do not establish fills or live latency.', '',
        '| Current example, one lot | Indicative margin (INR) | Fits INR 9,411.18? |',
        '|---|---:|---|']
    capital = json.loads((OUT / 'capital.json').read_text())
    for c in capital['checks']:
        margin = D(str(c['margin']['totalMargin']))
        lines.append(f"| {c['name']} | {margin:,.2f} | {'Yes, before buffers' if margin < START else 'No'} |")
    lines += ['', 'The small net debit or maximum payoff loss of a spread is **not** its broker margin. '
        'These are specific current-session examples, not historical margin or proof about every '
        'possible spread. Gold Petal is an affordable futures exception; it has no validated '
        'strategy result or confirmed commodity-account eligibility in this pass.', '',
        '## Decision and scope', '',
        'The prior 80 NIFTY variants and two 90-day event variants still have no qualified winner. '
        'The eight additions do not supply one. Stop this rapid all-in multiplication search '
        'without arming the funded account. This decision does not assert that every F&O strategy '
        'is unprofitable; larger-capital carry/volatility/trend strategies and untested families '
        'have different evidence and requirements.', '',
        '[Full mechanism review and primary sources](../../finalsearch/RESEARCH.md) · '
        '[Frozen protocol](../../finalsearch/PROTOCOL.md) · [Reproduce](../../finalsearch/README.md) · '
        '[All scenarios](scoreboard.csv) · [Trade ledger](ledger.json) · [Capital receipts](capital.json)', '',
        f"Validated resolved trade rows across scenarios: {counts['validated_resolved_trades']}. "
        'Tests demonstrate accounting and information boundaries, not real-market profitability.', '',
        f"Source SHA-256: `{doc['source_sha256']}`", f"Input SHA-256: `{doc['input_sha256']}`", '']
    # Adjacent literal strings above remain ordinary prose, not injected output.
    (OUT / 'REPORT.md').write_text('\n'.join(lines))
    print(json.dumps({'scenarios': len(doc['runs']), 'positive_both': positive, **counts,
                      'source_sha256': doc['source_sha256'], 'input_sha256': doc['input_sha256']}))

if __name__ == '__main__': main()
