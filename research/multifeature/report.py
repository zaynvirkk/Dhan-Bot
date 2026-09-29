"""Verify ledger algebra and source hashes, then report evidence limits."""
import csv,hashlib,json
from collections import Counter
from decimal import Decimal as D
from research.gauntlet.data import save
from .providers import STORE,OUT
from .replay import digest,inputs,STRATEGIES

def money(v):return 'UNKNOWN' if v is None else f'{D(v):,.2f}'

def main():
    sh=digest();_,dh,audits=inputs();docs=[];ledgers=[];score=[]
    for period in ('earlier','recent'):
        for quality in ('reported','strict'):
            doc=json.loads((OUT/(period+'_'+quality+'.json')).read_text())
            assert doc['source_hash']==sh and doc['data_hash']==dh,'stale source/input receipt'
            assert doc['calendar_days']==90
            assert len(doc['runs'])==len(STRATEGIES)*2*6
            docs.append(doc)
            for r in doc['runs']:
                cash=D('9411.18')
                for row in r['ledger']:
                    assert D(row['cash_before'])==cash
                    if row['status']=='MODELED_EXIT':
                        assert row['quantity']%row['lot']==0
                        assert D(row['cash_after'])-cash==D(row['pnl'])
                        assert abs((D(row['exit'])-D(row['entry']))*row['quantity']-D(row['fees'])-D(row['pnl']))<D('.00000001')
                        cash=D(row['cash_after'])
                    if r['scenario']=='primary' and quality=='reported':ledgers.append({'period':period,'strategy':r['strategy'],**row})
                if r['final_bankroll'] is not None:assert cash.quantize(D('.01'))==D(r['final_bankroll'])
                if r['scenario']=='primary':
                    lookup={v['scenario']:v for v in doc['runs'] if v['strategy']==r['strategy']}
                    score.append({'period':period,'quality':quality,'strategy':r['strategy'],'calendar_days':90,'sessions':doc['sessions'],'expiry_sessions':doc['expiry_sessions'],
                        'final_bankroll':r['final_bankroll'],'trades':r['counts'].get('trades',0),'signals':r['counts'].get('signals',0),'wins':r['counts'].get('wins',0),
                        'misses':r['counts'].get('misses',0),'max_closed_drawdown':r['closed_drawdown'],'unknown':r['unknown'],
                        **{k:lookup[k]['final_bankroll'] for k in ('delete_best','delay2','delay3','features_lag5','open_plus_1pct')}})
    noise=json.loads((OUT/'noise.json').read_text());assert noise['source_hash']==sh and noise['data_hash']==dh
    noise_by={(r['period'],r['strategy']):r for r in noise['rows']}
    for r in score:
        if r['quality']=='reported':r.update(p_conditional=noise_by[r['period'],r['strategy']]['p_conditional'],adjusted_p=noise_by[r['period'],r['strategy']]['adjusted_p'])
    for filename,rows in [('scoreboard.csv',score),('ledger.csv',ledgers)]:
        keys=list(dict.fromkeys(k for r in rows for k in r))
        with (OUT/filename).open('w') as f:
            w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows([{k:json.dumps(v) if isinstance(v,(list,dict)) else v for k,v in r.items()} for r in rows])
    viable=[]
    for strategy in sorted({r['strategy'] for r in score}):
        rr=[r for r in score if r['strategy']==strategy and r['quality']=='reported']
        if all(r['final_bankroll'] is not None and D(r['final_bankroll'])>D('9411.18') and r['delete_best'] is not None and D(r['delete_best'])>D('9411.18') and r['adjusted_p'] is not None and r['adjusted_p']<.05 for r in rr):viable.append(strategy)
    lines=['# Multi-source NIFTY 90-day experiment','',
        '**Conditional research only. No live winner is certified by candle-model P&L.**','',
        'Each of 64 variants starts independently with INR 9,411.18 in each consecutive 90-calendar-day window: 23 March–20 June and 21 June–18 September 2026. The same dates were previously examined, so these are retrospective comparisons, not untouched holdouts.',
        '',f'Computed {sum(len(d["runs"]) for d in docs)} execution scenarios and {sum(len(r["controls"]) for r in noise["rows"]):,} conditional random-side paths. Raw option contract-day audits: {audits}.',
        '',f'Variants passing both-window profit, best-trade deletion and multiplicity screen: {viable or "none"}. This screen does not verify actual historical fills or account-specific RMS.',
        '', '| Strategy | Earlier cash | Recent cash | Recent trades | Recent without best | Recent +5m feature lag |', '|---|---:|---:|---:|---:|---:|']
    lookup={(r['period'],r['strategy']):r for r in score if r['quality']=='reported'}
    for strategy in sorted({r['strategy'] for r in score}):
        a=lookup['earlier',strategy];b=lookup['recent',strategy]
        lines.append(f'| {strategy} | {money(a["final_bankroll"])} | {money(b["final_bankroll"])} | {b["trades"]} | {money(b["delete_best"])} | {money(b["features_lag5"])} |')
    lines+=['','## Interpretation and remaining evidence','',
        'UNKNOWN is a missing-input or unresolved-execution path, not a cash balance of 9,411 and not a zero-profit result. No-signal/no-fill balances are not evidence of an edge. Reported-candle diagnostics retain source discrepancies; strict paths reject volume mismatches, off-tick OHLC, invalid bounds and duplicate bars. These retrospective audit gates mark a result UNKNOWN; they are not live no-trade signals. No future EOD OHLC/OI, current smartlists, revised fundamentals, or current depth is inserted into historical signals.',
        '', 'Cross-broker checks matched 410,148 minute observations at the inferred same expiry/absolute strike/time; 249,645 close prices differed by more than one tick. Some difference may reflect feed sampling or candle construction; its cause is unresolved. Forty exact-contract days also contain off-tick OHLC prices. These are preserved in reported diagnostics, not silently rounded into valid source trades. See [coverage audit](data_coverage.json) and [price-grid audit](price_grid_audit.json). NSE specifies a [Re 0.05 NIFTY option price step](https://www.nseindia.com/static/products-services/equity-derivatives-nifty50).',
        '', 'Dhan IV comes from rolling strikes re-keyed to absolute strike/time. Its weekly expiry identity is inferred from the request and previous exchange contract schedule, not returned in each row. Premium/OI/IV publication timing remains an assumption, tested with added lag. Upstox PCR/max-pain history is incomplete. Prior-day chain alternatives are separately named and use only the previous published NSE chain.',
        '', 'Broker metadata, fees and the candle execution model constrain affordability; they do not prove historical bid/ask or queue fills. Same-bar ambiguity is adverse. Fees are a conservative current envelope, not reconstructed dated invoices. No position is rescued with added money. A small negative final net cash represents modeled ruin plus fees.',
        '', 'The 64-trial correction understates the entire conversation’s prior strategy search. Random controls test direction conditional on observed candidate times; they are not new independent market observations. Expiry-only strategies have roughly thirteen opportunities per 90-day window, far fewer than ninety independent trading trials.',
        '', 'This expanded batch covers NIFTY expiry and ordinary sessions. It does not claim a 90-day full-universe replay of every earlier event/flow family. Their additional timestamped sources remain separate. CAS IEP/order-book history remains unavailable for a 90-day replay.',
        '', '[Broker field inventory](../../multifeature/CAPABILITIES.md) · [Scoreboard](scoreboard.csv) · [Trade ledger](ledger.csv)',
        '',f'Source SHA-256: `{sh}`',f'Data SHA-256: `{dh}`']
    (OUT/'REPORT.md').write_text('\n'.join(lines)+'\n')
    save(OUT/'decision.json',{'source_hash':sh,'data_hash':dh,'status':'NO_LIVE_CERTIFICATION','research_screen_survivors':viable,'winner':None,'scenarios':sum(len(d['runs']) for d in docs),
        'noise_paths':sum(len(r['controls']) for r in noise['rows']),'audits':audits,'calendar_days_per_strategy_per_window':90})
    print('verified scenarios',sum(len(d['runs']) for d in docs),'ledger rows',len(ledgers),'screen survivors',viable,flush=True)

if __name__=='__main__':main()
