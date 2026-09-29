"""Verify the additional replay and publish the selection failure explicitly."""
import csv,hashlib,json
from decimal import Decimal as D
from pathlib import Path
from research.expiry.replay import START,digest,dataset
from .check import OUT,inputs

def main():
    x=json.loads((OUT/'results.json').read_text())
    assert x['source_hash']==digest()
    assert x['extension_source_hash']==hashlib.sha256(Path(__file__).with_name('check.py').read_bytes()).hexdigest()
    assert x['data_hash']==inputs('reported')[1]
    assert x['original_data_hash']==dataset('reported')[1]
    ledger=[]
    for r in x['runs']:
        cash=START
        for row in r['ledger']:
            assert D(row['cash_before'])==cash
            if 'cash_after' in row:
                assert row['quantity']%row['lot']==0
                assert D(row['cash_after'])-cash==D(row['pnl'])
                assert D(row['pnl'])==(D(row['exit'])-D(row['entry']))*row['quantity']-D(row['fees'])
                assert row['entry_at']>row['at'] and row['exit_at']>row['entry_at']
                cash=D(row['cash_after'])
            if r['scenario']=='primary':ledger.append({'variant':r['strategy'],'period':r['period'],'quality':r['quality'],**row})
        assert cash.quantize(D('.01'))==D(r['resolved_cash'])
        assert (r['final_bankroll'] is None)==bool(r['unknown'])
    keys=sorted(set().union(*(set(r) for r in ledger)))
    with (OUT/'ledger.csv').open('w') as h:
        w=csv.DictWriter(h,fieldnames=keys);w.writeheader();w.writerows(ledger)
    lines=['# Additional NIFTY expiry validation','',
        '**No live-qualified strategy.** The unchanged 14:45 trend candidate failed its additional-year check. All amounts below are conditional reported-candle model balances, not actual executions.', '',
        '| Variant | Additional 53 expiries | Full 101-expiry chronology | Full path deleting best trade |',
        '|---|---:|---:|---:|']
    for style in ('TARGET','TRAIL'):
        vals=[]
        for period,scenario in [('extension','primary'),('all','primary'),('all','delete_best')]:
            r=next(r for r in x['runs'] if r['quality']=='reported' and r['strategy']=='TREND1445_'+style and r['period']==period and r['scenario']==scenario)
            vals.append('UNKNOWN' if r['final_bankroll'] is None else f"{D(r['final_bankroll']):,.2f}")
        lines.append('| '+style+' | '+' | '.join(vals)+' |')
    lines+=['','Initial cash: INR 9,411.18. Extra period: 1 October 2024–30 September 2025; full path appends the original 48 expiries, retaining its predeclared July 1–19 exclusion. There are five signals and three closed trades on the full primary path. No bankroll resets, hindsight replacement of missed orders or borrowing a later winner to repair an earlier loss.', '',
        '| Conditional random-side comparison | Raw tail probability | Twelve-trial bound |',
        '|---|---:|---:|']
    for n in x['noise']:
        lines.append('| '+n['period']+' '+n['strategy']+' | '+str(n['p_conditional'])+' | '+str(n['twelve_trial_bound'])+' |')
    lines+=['', 'Each row uses 999 simulations, not 999 independent market histories. These preserve signal times and test direction/selection conditionally. The candidate was chosen after the original twelve tests; selection is disclosed and the twelve-trial bound is retained.', '',
        'The full trailing path remains positive under the modeled delay scenarios, but that does not repair the concentration in one January 20 trade or the negative additional-year result. Only three trades over 101 expiries cannot establish repeatability. Strict reconciled paths remain UNKNOWN because the relevant option archives differ from official daily volume. Minute bars do not establish historical depth, actual fills or second-level latency.', '',
        'No strategy parameters were changed. The two exit styles are the original registered alternatives. Raw results include every execution scenario, quality policy and control; ledger.csv records the full primary cash paths. No real orders were submitted.', '',
        f"Base source SHA-256: `{x['source_hash']}`.",f"Additional data SHA-256: `{x['data_hash']}`."]
    (OUT/'REPORT.md').write_text('\n'.join(lines)+'\n')
    print('Verified',len(x['runs']),'additional scenarios;',len(ledger),'ledger rows;',sum(len(n['controls']) for n in x['noise']),'controls')

if __name__=='__main__':main()
