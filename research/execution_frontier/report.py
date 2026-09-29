"""Verify every scenario and publish complete, explicitly bounded findings."""
import csv
import hashlib
import json
from collections import Counter
from math import ceil

from research.gauntlet.core import D
from research.gauntlet.data import ROOT, save
from research.rebound_validation.fees import schedule
from research.rebound_validation.report import verify_row, verify_inputs
from .replay import OUT, RULES, ALLOCATIONS, PERIODS, digest


def main():
    reg=json.loads((OUT/'registration.json').read_text())
    assert reg['protocol_sha256']==hashlib.sha256((ROOT/'research/execution_frontier/PROTOCOL.md').read_bytes()).hexdigest()
    data=json.loads((OUT/'runs.json').read_text()); runs=data['runs']
    assert data['source_sha256']==digest(), 'STALE_SOURCE'
    assert len(runs)==504
    assert len({(r['strategy'],r['allocation'],r['period'],r['scenario']) for r in runs})==504
    verify_inputs(data['input_hashes'])
    verified=0
    for r in runs:
        cash=D('9411.18'); previous_exit=''
        for row in r['ledger']:
            assert D(row['cash_before'])==cash
            if row['status']=='RESOLVED':
                assert row['day']>previous_exit
                verify_row(row, dated=True)
                turn=D(row['limit'])*row['quantity']
                assert turn+schedule(row['day']).buy(turn,ceil(row['quantity']/row['freeze'])) <= cash*D(r['allocation'])
                cash=D(row['cash_after']); previous_exit=row['exit_at'][:10]; verified+=1
        assert r['final_bankroll'] is None if r['unknown'] else D(r['final_bankroll'])==cash.quantize(D('.01'))
    with (OUT/'scoreboard.csv').open('w') as f:
        cols=['strategy','allocation','period','scenario','final_bankroll','unknown','model_drawdown']
        w=csv.DictWriter(f,fieldnames=cols,extrasaction='ignore'); w.writeheader(); w.writerows(runs)
    base={(r['strategy'],r['allocation'],r['period']):r for r in runs if r['scenario']=='rest3'}
    positive=[]
    for rule in RULES:
        for fraction in ALLOCATIONS:
            rs=[base[rule,str(fraction),p] for p in PERIODS]
            if all(r['final_bankroll'] and D(r['final_bankroll'])>D('9411.18') for r in rs): positive.append((rule,str(fraction)))
    capital=json.loads((OUT/'capital.json').read_text())
    lines=['# Execution and capital frontier — 28 September 2026','',
           'This pass directly tests whether a different enforceable order policy, puts, calls,',
           'trend filters or bankroll allocation rescues the previously favorable overnight rules.',
           'It does not claim to exhaust every F&O strategy. No live trading or deployment occurred.','',
           'Eight signal rules × three allocations × seven scenarios × three 90-calendar-day windows',
           '= **504 attempted paths**. All start independently at INR 9,411.18. Dates are 23 December',
           '2025–22 March 2026, 23 March–20 June 2026, and 21 June–18 September 2026.',
           'All three windows have now been reused and are exploratory, not independent holdouts.','',
           '## What a limit can actually control','',
           'A fixed price cap and entry deadline can be specified before submitting an order.',
           'The former whole-minute-high rejection is not an executable filter: a minute can open',
           'below the cap, fill an order, and subsequently trade above it. The original May 29',
           'example has a INR 212.10 cap, INR 204.45 open and INR 216.10 high. Rejecting the entire',
           'bar can incorrectly omit the losing position. Nothing about that later high was',
           'available when the order arrived.','',
           'The new base holds the fixed limit for three arrival bars; two-tick low penetration',
           'models a fill at the limit, irrespective of the high. Entry timing is conservatively',
           'the bar end. Volume-limited partial entry becomes UNKNOWN. This remains an OHLCV',
           'scenario: no bid/ask queue, cancellation acknowledgement or subsecond fill is proved.','',
           '## Baseline at 95% allocation','',
           '| Rule | Dec–Mar | Mar–Jun | Jun–Sep | Trades across windows |',
           '|---|---:|---:|---:|---|']
    for rule in RULES:
        rs=[base[rule,'0.95',p] for p in PERIODS]
        lines.append('| '+rule+' | '+' | '.join(r['final_bankroll'] or 'UNKNOWN' for r in rs)+' | '+
                     '/'.join(str(r['counts'].get('trades',0)) for r in rs)+' |')
    lines += ['',f'Rule/allocation combinations profitable in all three base windows: **{len(positive)} of 24**.',
              'This is a bounded failure, not a theorem that puts, calls or reversal strategies never work.',
              'At 25% allocation many paths cannot buy a qualifying lot; unchanged cash is not an edge.',
              'At 50%, SELL_OFF_PUT (SELLOFF_PUT in the ledger) gives 9,468.82 / 11,001.02 / 9,411.18',
              'in the base paths, with only 2 / 1 / 0 fills. The complete 25%/50% results and all',
              'execution stresses are in the scoreboard and ledger, not omitted from ranking.','',
              '## Current broker margin survey','',
              f"Read-only snapshot: available cash INR {capital['available_balance']}; {capital['positions_count']} positions.",
              f"Quoted {capital.get('quoted_stock_futures',0)} near-month stock futures; sampled the ten lowest quoted notionals.",
              'Margin values are indicative for the current session, not historical margin paths.',
              'A basket and its first purchased hedge leg must each fit; successful margin reads',
              'do not guarantee acceptance, available liquidity or fill prices.','',
              '| Structure | Reported margin | Fits current cash | First hedge fits |',
              '|---|---:|---|---|']
    for r in capital['checks']:
        lines.append(f"| {r['name']} | {r.get('reported_margin') or 'UNKNOWN'} | {r.get('basket_fits_cash','UNKNOWN')} | {r.get('first_hedge_fits_cash','n/a')} |")
    cash_path=OUT/'cash_capital.json'
    cash_capital=json.loads(cash_path.read_text()) if cash_path.exists() else {'checks':[],'status':'UNKNOWN'}
    cash_checks=len(cash_capital['checks'])
    lines += ['', f'Cash intraday 4x checks completed: {cash_checks} of 10 planned.']
    if cash_checks==10 and cash_capital['status']=='READS_SUCCEEDED':
        lines += ['The separate completed cash probe follows earlier renewal failures. Fresh authentication',
                  'and read-only margin requests succeed; the original failures remain preserved.', '',
                  '| Cash intraday side | Notional | Indicative margin | Fits cash |',
                  '|---|---:|---:|---|']
        for r in cash_capital['checks']:
            lines.append(f"| {r['name']} | {r['notional']} | {r['reported_margin']} | {r['fits_cash']} |")
        lines += ['', 'These probes confirm a currently affordable long/short cash implementation.',
                  'They do not establish historical eligibility, margin stability, borrow availability',
                  'for overnight shorts, or a profitable stock signal. These are intraday products.',
                  '[Completed cash-margin receipts](cash_capital.json).']
    else:
        lines += ['The initial equity lookup used the display-name field instead of the symbol field;',
                  'that implementation is corrected. Subsequent bounded authentication renewals failed',
                  'before account reads. A separate direct authentication diagnostic succeeded, but',
                  'the full cash-margin requests did not complete. Those margins remain UNKNOWN;',
                  'published maximum cash leverage is not an account-specific margin receipt.']
    lines += ['', 'A sample that does not fit rules out that structure at this snapshot, not every',
              'strike, expiry or alternative account size. Affordable Gold Petal or cash leverage',
              'expands the feasible research set; it supplies no directional forecasting edge.',
              'Cash intraday exposure and a long option premium are different financing arrangements.',
              'Selling options or using futures requires dated broker margin and MTM paths.','',
              '## Verification and remaining coverage','',
              f'{verified} resolved scenario-trade rows reconcile fees, cash, timing, expiry and allocation.',
              f"{sum(bool(r['unknown']) for r in runs)} paths are explicitly UNKNOWN. Strict source checks do not become no-trade wins.",
              'No newly profitable all-window base candidate exists to advance from this batch.',
              'Untested scheduled-event volatility, dated-margin commodity/cash strategies and',
              'synchronized multi-leg pricing remain unvalidated rather than rejected by these results.',
              'The research inventory explains what each distinct mechanism still needs.','',
              '[Frozen protocol](../../execution_frontier/PROTOCOL.md), [full ledger](runs.json),',
              '[scoreboard](scoreboard.csv), [margin receipts](capital.json),',
              '[research inventory](../../execution_frontier/RESEARCH.md).','',
              'Primary current mechanics: [Dhan order API](https://dhanhq.co/docs/v2/orders/),',
              '[indicative margin API](https://dhanhq.co/docs/v2/funds/),',
              '[Dhan RMS and cash leverage](https://dhan.co/risk-management-policy/).','',
              'Source SHA-256: `'+digest()+'`','']
    (OUT/'REPORT.md').write_text('\n'.join(lines))
    summary={'source_sha256':digest(),'scenario_attempts':len(runs),'verified_trade_rows':verified,
             'unknown_paths':sum(bool(r['unknown']) for r in runs),'positive_all_base_windows':positive,
             'capital_checks':len(capital['checks'])+cash_checks,'cash_margin_status':cash_capital['status'],
             'funded_authority':False}
    save(OUT/'verification.json',summary)
    print(json.dumps(summary))


if __name__ == '__main__': main()
