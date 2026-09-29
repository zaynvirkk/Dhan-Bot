"""Validate provenance/arithmetic and export an auditable expiry comparison."""
import csv,hashlib,json
from decimal import Decimal as D
from .replay import RESULTS,START,digest,dataset
from .collect import STORE

def main():
    days,dh=dataset();allruns=[];summaries=[]
    for period,quality in [(p,q) for p in ('development','recent_validation','older_validation','all') for q in ('strict','reported')]:
        f=RESULTS/(period+'_'+quality+'.json')
        if not f.exists():continue
        raw=json.loads(f.read_text())
        assert raw['source_hash']==digest() and raw['data_hash']==dh,'stale replay'
        for r in raw['runs']:
            r['quality']=quality
            cash=START
            for row in r['ledger']:
                assert D(row['cash_before'])==cash,'broken cash chronology'
                if 'quantity' in row:assert row['quantity']%row['lot']==0
                if 'cash_after' in row:
                    assert D(row['cash_after'])-cash==D(row['pnl'])
                    assert D(row['pnl'])==(D(row['exit'])-D(row['entry']))*row['quantity']-D(row['fees'])
                    assert row['entry_at']>row['at'] and row['exit_at']>row['entry_at']
                    cash=D(row['cash_after'])
            assert cash.quantize(D('.01'))==D(r['resolved_cash'])
            assert (r['final_bankroll'] is None)==bool(r['unknown'])
        allruns+=raw['runs']
        nf=RESULTS/(period+'_'+quality+'_noise.json')
        if nf.exists():
            nr=json.loads(nf.read_text());assert nr['source_hash']==digest() and nr['data_hash']==dh
            summaries+=nr['summary']
    fields=['strategy','period','quality','scenario','final_bankroll','resolved_cash','unknown','signals','trades','wins','losses','targets','misses','unaffordable','closed_drawdown','intrabar_mark_drawdown']
    with (RESULTS/'scoreboard.csv').open('w') as h:
        w=csv.DictWriter(h,fieldnames=fields);w.writeheader()
        for r in allruns:
            row={k:r.get(k) for k in fields};c=r['counts'];row.update(signals=c.get('signals',0),trades=c.get('trades',0),wins=c.get('wins',0),losses=c.get('losses',0),targets=c.get('TARGET_2X',0),misses=c.get('misses',0),unaffordable=c.get('unaffordable_or_liquidity',0));w.writerow(row)
    ledger=[]
    for r in allruns:
        if r['scenario']=='primary':
            for row in r['ledger']:ledger.append({'variant':r['strategy'],'period':r['period'],'quality':r['quality'],**row})
    lf=sorted(set().union(*(set(r) for r in ledger))) if ledger else []
    with (RESULTS/'ledger.csv').open('w') as h:
        w=csv.DictWriter(h,fieldnames=lf);w.writeheader();w.writerows(ledger)
    lines=['# NIFTY expiry — bounded research results','',
        'Each variant starts independently with INR 9,411.18. These are minute-bar model results, not actual historical fills or a live-profitability claim.',
        '', 'Twelve registered variants; 48 expiries across three periods. Development was already contaminated by earlier research. Two retrospective validation blocks were opened after tests, without retuning. They precede CAS and cannot validate that new regime.', '',
        'The table is the **reported-candles diagnostic**: volume discrepancies remain disclosed and unresolved. Strict reconciled results are in scoreboard.csv, with UNKNOWN terminal wealth wherever a discrepancy affects the path.', '',
        '| Strategy | Development (9 expiries) | Apr–Jun validation (13) | Oct–Mar validation (26) | Entire chronology |',
        '|---|---:|---:|---:|---:|']
    names=sorted(set(r['strategy'] for r in allruns))
    for name in names:
        values=[]
        for period in ('development','recent_validation','older_validation','all'):
            r=next((x for x in allruns if x['strategy']==name and x['period']==period and x['scenario']=='primary' and x['quality']=='reported'),None)
            values.append('NOT RUN' if r is None else ('UNKNOWN' if r['final_bankroll'] is None else f"{D(r['final_bankroll']):,.2f} ({r['counts'].get('trades',0)} trades)"))
        lines.append('| '+name+' | '+' | '.join(values)+' |')
    audits=json.loads((STORE/'download.json').read_text())
    counts={s:sum(x['status']==s for x in audits.values()) for s in set(x['status'] for x in audits.values())}
    lines += ['', '## Execution and uncertainty','',
        'The primary entry is the next full minute high after a one-minute delay, bounded by the submitted limit. Stops/timed exits use low minus 1%; simultaneous stop/target bars resolve against the trade. Alternate open-plus-1%, two/three-minute delays and full best-trade-deletion replays appear in scoreboard.csv. Targets require trade-through. Each order uses fixed whole lots, current conservative taxes/brokerage and a 5% volume participation cap.',
        '', 'Archive audit counts: `'+json.dumps(counts,sort_keys=True)+'`. Missing data or unresolved positions yield UNKNOWN terminal wealth. No-trade is reserved for an observed rule failure or a modeled limit/capacity rejection.',
        '', 'A reconciliation is a completeness check, not proof of bid/ask availability. Historical spread, depth, queue priority and second-level latency remain unknown. Earlier periods use the current conservative cost envelope, not historically exact invoices. Drawdowns include separate closed-trade and adverse intrabar marks.',
        '', '## Signal versus noise','',
        'Matched random-side paths preserve signal times, whole-lot contract selection and independent bankroll compounding. They test incremental direction/selection conditional on those times; they do not prove timing predictability. Holm adjustment covers all twelve variants. An unresolved randomization makes its p-value UNKNOWN. Simulations are not additional independent market observations.',
        '', 'See *_noise.json for the full controls, ledger.csv for entries and exits, and PROTOCOL.md for frozen definitions. No threshold revision or profitable-strategy promotion follows from this report.',
        '', f'Source SHA-256: `{digest()}`. Dataset SHA-256: `{dh}`.']
    (RESULTS/'REPORT.md').write_text('\n'.join(lines)+'\n')
    print('verified',len(allruns),'replay scenarios;',len(ledger),'primary ledger rows;',len(summaries),'noise summaries')

if __name__=='__main__':main()
