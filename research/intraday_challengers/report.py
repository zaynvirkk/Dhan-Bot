"""Reconcile every resolved ledger row before producing the comparison."""
import csv
import hashlib
import json
from collections import Counter
from datetime import datetime
from math import ceil
from pathlib import Path
from .experiment import OUT,STORE,START,NAMES,EXITS,D,FeeSchedule,source_hash,load

def main():
    raw=json.loads((OUT/'results.json').read_text());controls=json.loads((OUT/'controls.json').read_text());days,datahash,audit=load()
    assert raw['source_sha256']==controls['source_sha256']==source_hash()
    assert raw['input_sha256']==controls['input_sha256']==datahash
    reg=json.loads((OUT/'registration.json').read_text())
    assert reg['protocol_sha256']==hashlib.sha256(Path(__file__).with_name('PROTOCOL.md').read_bytes()).hexdigest()
    index={};rows=[];ledger=[];validated=0;fees=FeeSchedule()
    for r in raw['runs']:
        key=(r['strategy'],r['period'],r['scenario']);assert key not in index;index[key]=r
        cash=START;last='';n=0
        for row in r['ledger']:
            assert row['day']>last;last=row['day'];assert D(row['cash_before'])==cash
            if row['status']=='MODELED_EXIT':
                c=next(c for c in days[row['day']]['chain'] if c.key==row['contract'])
                q=row['quantity'];buy=D(row['entry'])*q
                sell=sum((D(p['price'])*p['quantity'] for p in row['exit_parts']),D(0))
                cost=fees.buy(buy,ceil(q/c.freeze))+sum((fees.sell(D(p['price'])*p['quantity'],ceil(p['quantity']/c.freeze)) for p in row['exit_parts']),D(0))
                assert cost==D(row['fees'])
                assert cash-buy+sell-cost==D(row['cash_after'])==cash+D(row['pnl'])
                assert q>0 and q%c.lot==0 and sum(p['quantity'] for p in row['exit_parts'])==q
                assert all(p['quantity']>0 and p['quantity']%c.lot==0 for p in row['exit_parts'])
                assert D(row['entry'])<=D(row['limit'])
                bound=D(row['limit'])*q
                assert bound+fees.buy(bound,ceil(q/c.freeze))<=cash*D('.95')
                assert row['signal_at']<row['entry_at']<row['exit_at']
                assert all(p['at']>row['entry_at'] for p in row['exit_parts'])
                tape={b.start.isoformat():b for b in days[row['day']]['bars'][c.key]}
                assert D(q)<=D(tape[row['entry_at']].volume)*D('.05')
                assert all(D(p['quantity'])<=D(tape[p['at']].volume)*D('.05') for p in row['exit_parts'])
                cash=D(row['cash_after']);assert cash>=0;validated+=1;n+=1
            ledger.append({**{k:r[k] for k in ('strategy','period','scenario','quality')},**row})
        assert n==r['counts'].get('trades',0)
        assert cash.quantize(D('.01'))==D(r['resolved_cash'])
        assert (r['final_bankroll'] is None)==(r['unknown'] is not None)
        if r['final_bankroll'] is not None:assert D(r['final_bankroll'])==cash.quantize(D('.01'))
        rows.append({**{k:r[k] for k in ('strategy','period','scenario','quality','final_bankroll','resolved_cash','unknown','model_drawdown')},**r['counts']})
    assert len(index)==360
    for name in NAMES:
        for style in EXITS:
            for period in ('earlier','recent'):
                for scenario in ('primary','delay2','delay3','open_plus_1pct','delete_best','strict'):
                    assert (name+'_'+style,period,scenario) in index
    with (OUT/'scoreboard.csv').open('w') as f:
        writer=csv.DictWriter(f,fieldnames=sorted(set().union(*(r.keys() for r in rows))));writer.writeheader();writer.writerows(rows)
    (OUT/'ledger.json').write_text(json.dumps(ledger,separators=(',',':')))
    def amount(r):return 'UNKNOWN' if r['final_bankroll'] is None else f"{D(r['final_bankroll']):,.2f}"
    primary=[r for r in raw['runs'] if r['scenario']=='primary' and r['period']=='recent']
    primary.sort(key=lambda r:D(r['final_bankroll'] or '-1'),reverse=True)
    beat=[r for r in primary if r['final_bankroll'] is not None and D(r['final_bankroll'])>D('11908.11')]
    assert {r['strategy'] for r in beat}=={r['strategy'] for r in controls['results']}
    both=[r['strategy'] for r in primary if r['final_bankroll'] is not None and D(r['final_bankroll'])>START and
          index[r['strategy'],'earlier','primary']['final_bankroll'] is not None and D(index[r['strategy'],'earlier','primary']['final_bankroll'])>START]
    robust=[]
    for r in primary:
        required=[index[r['strategy'],period,scenario] for period in ('earlier','recent') for scenario in ('primary','delay2','delay3','delete_best','strict')]
        if all(v['final_bankroll'] is not None and D(v['final_bankroll'])>START for v in required):robust.append(r['strategy'])
    lines=['# Intraday challengers — one new recent-period leader','',
           'Completed 27 September 2026. Eight new signals plus the two original signal benchmarks, '
           'each with three frozen exits: **30 variants / 360 scenario paths**. '
           'Each starts independently with **INR 9,411.18**. Windows are **23 March–20 June** and '
           '**21 June–18 September 2026**, 90 calendar days each, with 46/50 ordinary NIFTY sessions. '
           'Both periods have already been used for research; neither is a holdout.','',
           '**GAP_FADE_DOUBLE reaches INR 12,566.43 (+33.53%) in the recent window, beating the '
           'previous INR 11,908.11 best by INR 658.32.** It has five signals, four modeled trades, '
           'three wins, one loss and one limit miss. This is a conditional historical-model leader; '
           'it does not qualify for funded trading.','',
           'The rule waits for a gap of at least 0.5% from the previous close, then 25–100% retracement '
           'toward the gap fill, three persistent minute closes and matching futures direction. '
           'It buys the closest affordable weekly option from ATM through three OTM strikes. '
           'The exit triggers at a completed 2x premium close, a 50% loss, or scheduled close; '
           'processing delay and adverse liquidation can reduce the realized payoff.','',
           '| Variant | Earlier final INR | Recent final INR | Recent trades / wins | Recent delete-best INR |',
           '|---|---:|---:|---:|---:|']
    for r in primary:
        n=r['strategy'];e=index[n,'earlier','primary'];delete=index[n,'recent','delete_best']
        lines.append(f"| {n} | {amount(e)} | {amount(r)} | {r['counts'].get('trades',0)} / {r['counts'].get('wins',0)} | {amount(delete)} |")
    lines+=['','## Does the new leader survive?','',
            '| Check | GAP_FADE_DOUBLE final INR |','|---|---:|']
    for period,scenario in [('earlier','primary'),('recent','primary'),('recent','delay2'),('recent','delay3'),('recent','open_plus_1pct'),('recent','delete_best'),('recent','strict')]:
        lines.append(f"| {period} / {scenario} | {amount(index['GAP_FADE_DOUBLE',period,scenario])} |")
    lines+=['','The extra-minute results change both which orders fill and later bankroll-dependent '
            'sizing. The seemingly more favorable open-plus-1% model fills a losing trade missed '
            'by the adverse-high model; adverse individual prices do not guarantee a lower '
            'whole-strategy result when limit misses select different trades.','',
            'Recent modeled mark drawdown is 45.85%. Deleting the best profitable day reruns '
            'the full chronological path, including changed strike choice and size, rather than '
            'subtracting one P&L. Earlier primary loses money. The +33.53% result is not robust.','',
            '## Noise controls','']
    for c in controls['results']:
        assert c['controls']==999 and len(c['paths'])==999
        assert [p['seed'] for p in c['paths']]==list(range(999))
        resolved=[D(p['final_bankroll']) for p in c['paths'] if p['final_bankroll'] is not None]
        assert sum(v>=D(c['observed']) for v in resolved)==c['at_least_observed']
        lines.append(f"{c['strategy']}: **{c['at_least_observed']} of 999 matched-time random-side paths "
                     f"do at least as well**; {c['unknown']} unresolved. Smoothed randomization tail "
                     f"probability {c['p_upper']:.3f}; conservative correction across at least 118 "
                     f"tested variants: {c['bonferroni_118_upper']:.3f}. This test does not establish an edge.")
    lines+=['','TREND_PULLBACK_FAST is the only primary variant positive in both reused windows: '
            'INR 9,623.88 / INR 9,500.24, with just one filled trade in each. Its earlier delay '
            'and alternative-entry paths lose money; deleting each sole winner returns the start. '
            'It is not evidence of a repeatable profitable strategy.','',
            'Benchmark comparison: SKEW_UNWIND_DOUBLE still gives INR 11,908.11. '
            'CHAIN_UNWIND_DOUBLE gives INR 10,603.30 under this completed-close exit model '
            '(the previous resting-target result was INR 10,843.71). All candidates within this '
            'experiment use the same execution rules.','',
            '## Data and verification','',
            'Fetched 34 additional read-only historical API batches. Replayed 838 exact option '
            'contract-days: 607 match NSE daily volume, 231 differ; 18 contain off-tick prices '
            '(overlapping categories), leaving 599 without either issue. No mismatch was repaired '
            'or silently treated as no-trade. All 60 primary reported-candle paths resolve; '
            '54 of 60 strict paths are UNKNOWN. Of the six resolved strict paths, three '
            'FIRST_LAST exit variants lose money in the earlier window and three SKEW_UNWIND '
            'variants have no fills there. Historical bid/ask/depth and exact fill probability '
            'remain unavailable.','',
            f'Validated {validated} resolved scenario-trade rows for cash continuity, exact charges, '
            'whole lots, entry budgets, fixed limits, participation and chronological timestamps. '
            'Eight new deterministic tests cover future-data invariance, paid partial exits, '
            'target delay, entry-bar ordering, missing data and fee reserves. Tests prove simulator '
            'behavior, not market profitability.','',
            f'Primary positive in both windows: {", ".join(both) or "none"}. '
            f'Candidates surviving all registered profitability/quality gates: {", ".join(robust) or "none"}. '
            'No funded orders, cloud deployment or account changes were made.','',
            '[Frozen rules](../../intraday_challengers/PROTOCOL.md) · [Reproduce](../../intraday_challengers/README.md) · '
            '[All scenarios](scoreboard.csv) · [Ledger](ledger.json) · [Controls](controls.json)','',
            f"Source SHA-256: `{raw['source_sha256']}`",f"Input SHA-256: `{raw['input_sha256']}`",'']
    (OUT/'REPORT.md').write_text('\n'.join(lines))
    print(json.dumps({'scenarios':len(index),'validated_trade_rows':validated,'recent_beats':[r['strategy'] for r in beat],'positive_both':both,'robust':robust}))

if __name__=='__main__':main()
