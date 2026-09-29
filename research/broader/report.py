"""Independent ledger arithmetic and evidence checks, then public comparisons."""
import csv,hashlib,json
from collections import Counter
from datetime import datetime
from pathlib import Path
from research.gauntlet.core import Contract,D
from research.gauntlet.data import ROOT,CACHE,save
from .prepare import OUT,STORE
from .replay import Dataset,START,NAMES,digest,fee

def main():
    batches=[json.loads((OUT/(g+'.json')).read_text()) for g in ('cash','options')]
    reg=json.loads((OUT/'registration.json').read_text())
    assert reg['protocol_sha256']==hashlib.sha256(Path(__file__).with_name('PROTOCOL.md').read_bytes()).hexdigest()
    ds=Dataset(network=False);index={};ledger=[];validated=0;hashes={};audit={}
    for batch in batches:
        assert batch['source_sha256']==digest()
        for p,h in batch['input_hashes'].items():
            assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h,p
            assert p not in hashes or hashes[p]==h
            hashes[p]=h
        audit.update(batch['audit'])
        for r in batch['runs']:
            key=r['strategy'],r['period'],r['scenario'];assert key not in index;index[key]=r
            cash=START;last='';busy='';n=0
            for row in r['ledger']:
                assert row['day']>last and row['day']>busy
                assert D(row['cash_before'])==cash;last=row['day']
                if row['status']=='RESOLVED':
                    s=ds.plan[row['day']]['signals'][r['strategy']];iscash=s['mode'].startswith('CASH')
                    if iscash:c=Contract(s['key'],s['symbol'],'','EQ',D(0),1,D('.1'),100000,False)
                    else:
                        selection=ds.contracts['|'.join((row['day'],s['symbol'],s['exit_day'],row['side']))]['contracts']
                        c=Contract.parse(next(m for m in selection if m.get('instrument_key')==row['contract']))
                    q=row['quantity'];buy=D(row['entry'])*q
                    sell=sum((D(p['price'])*p['quantity'] for p in row['exit_parts']),D(0))
                    cost=fee(buy,'BUY',c,iscash,q)+sum((fee(D(p['price'])*p['quantity'],'SELL',c,iscash,p['quantity'],dp=j==0) for j,p in enumerate(row['exit_parts'])),D(0))
                    assert cost==D(row['fees']) and cash-buy+sell-cost==D(row['cash_after'])==cash+D(row['pnl'])
                    assert q>0 and q%c.lot==0 and sum(p['quantity'] for p in row['exit_parts'])==q
                    bound=D(row['limit'])*q
                    assert bound+fee(bound,'BUY',c,iscash,q)<=cash*D('.95')
                    assert D(row['entry'])<=D(row['limit']) and D(row['entry'])%c.tick==0
                    assert row['signal_at']<row['entry_at']<row['exit_at']
                    assert len(row['exit_parts'])<=3
                    participation=D('.01') if iscash else D('.05')
                    at=datetime.fromisoformat(row['entry_at']);tape=ds.rows(s,c,at.date().isoformat(),'reported')
                    assert D(q)<=D(tape[at].volume)*participation
                    for p in row['exit_parts']:
                        assert p['at']>row['entry_at'] and p['quantity']>0 and p['quantity']%c.lot==0
                        assert D(p['price'])>=0 and D(p['price'])%c.tick==0
                        at=datetime.fromisoformat(p['at']);tape=ds.rows(s,c,at.date().isoformat(),'reported')
                        assert D(p['quantity'])<=D(tape[at].volume)*participation
                    cash=D(row['cash_after']);busy=row['exit_at'][:10];assert cash>=0;n+=1;validated+=1
                ledger.append({**{k:r[k] for k in ('strategy','period','scenario','quality')},**row})
            assert n==r['counts'].get('trades',0) and cash==D(r['resolved_cash'])
            assert (r['final_bankroll'] is None)==(r['unknown'] is not None)
            if not r['unknown']:assert D(r['final_bankroll'])==cash.quantize(D('.01'))
    for name in NAMES:
        for period in ('earlier','recent'):
            for scenario in ('primary','delay3','slippage2','delete_best','strict'):assert (name,period,scenario) in index
    assert len(index)==260
    parity=0
    old=json.loads((OUT/'options_before_expiry_route_reconciliation.json').read_text())
    for r in old['runs']:
        if r['period']=='recent' and r['strategy'].startswith('NIFTY_'):continue
        assert index[r['strategy'],r['period'],r['scenario']]==r
        parity+=1
    old=json.loads((OUT/'cash_before_source_reconciliation.json').read_text())
    for r in old['runs']:
        if r['period']=='earlier' and r['strategy'].startswith('OI_SQUEEZE_'):continue
        assert index[r['strategy'],r['period'],r['scenario']]==r
        parity+=1
    rows=[{**{k:r[k] for k in ('strategy','period','scenario','quality','final_bankroll','resolved_cash','unknown','model_drawdown')},**r['counts']} for r in index.values()]
    with (OUT/'scoreboard.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=sorted(set().union(*(r.keys() for r in rows))));w.writeheader();w.writerows(rows)
    save(OUT/'ledger.json',ledger)
    def amount(r):return 'UNKNOWN' if r['final_bankroll'] is None else f"{D(r['final_bankroll']):,.2f}"
    primary=[index[n,'recent','primary'] for n in NAMES];primary.sort(key=lambda r:D(r['final_bankroll'] or '-1'),reverse=True)
    beat=[r for r in primary if r['final_bankroll'] and D(r['final_bankroll'])>D('12566.43')]
    both=[n for n in NAMES if all(index[n,p,'primary']['final_bankroll'] and D(index[n,p,'primary']['final_bankroll'])>START for p in ('earlier','recent'))]
    robust=[n for n in NAMES if all(index[n,p,s]['final_bankroll'] and D(index[n,p,s]['final_bankroll'])>START for p in ('earlier','recent') for s in ('primary','delay3','slippage2','delete_best','strict'))]
    sourceaudit=Counter(v for issues in audit.values() for v in issues)
    controls=json.loads((OUT/'controls.json').read_text());assert controls['source_sha256']==digest()
    for p,h in {**controls['base_input_hashes'],**controls['control_input_hashes']}.items():
        assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h,p
    expected={(r['strategy'],r['period']) for r in index.values() if r['scenario']=='primary' and '_CASH' not in r['strategy'] and r['final_bankroll'] and D(r['final_bankroll'])>D('12566.43')}
    assert {(r['strategy'],r['period']) for r in controls['results']}==expected
    lines=['# Broader search: overnight, stock selection and holding periods','',
      '26 frozen variants, 260 scenario paths attempted. Each independently starts with **INR 9,411.18**. '
      'Both **23 March–20 June** and **21 June–18 September 2026** span 90 calendar days '
      '(59 and 63 trading sessions). These periods have already been used for discovery; they are not holdouts. '
      'UNKNOWN means the path cannot be scored, not that it stayed at the starting balance.','',
      'Universe: 146 official NSE archive sessions including warm-up, historical F&O membership '
      '(221 stocks in the dated union), 214 distinct stocks meeting at least one past-only selector '
      'and minute history for the 151 stocks selected by a top rank. The ranked stock is fixed before '
      'its option affordability is known; an expensive top pick cannot be replaced with a later winner.','',
      '| Strategy | Earlier final INR | Recent final INR | Recent trades / wins | Recent delete-best INR |',
      '|---|---:|---:|---:|---:|']
    for r in primary:
        n=r['strategy'];lines.append(f"| {n} | {amount(index[n,'earlier','primary'])} | {amount(r)} | {r['counts'].get('trades',0)} / {r['counts'].get('wins',0)} | {amount(index[n,'recent','delete_best'])} |")
    lines+=['','## Interpretation','',
      'Recent primary strategies exceeding the prior INR 12,566.43 benchmark: '+(', '.join(r['strategy'] for r in beat) or 'none')+'.',
      'Primary profit in both reused windows: '+(', '.join(both) or 'none')+'.',
      'Positive in both windows under every registered stress and strict data check: '+(', '.join(robust) or 'none')+'.','',
      'A favorable final balance is conditional on a minute-bar model. No strategy here has historical '
      'order-book execution receipts, and repeated use of the same windows prevents an independent '
      'validation claim. Best-trade deletion reruns the full chronology and bankroll-dependent selection. '
      'All comparisons use whole shares/lots, costs and cash left by earlier trades. No capital reset after losses.','',
      '## Overnight rebound candidate','',
      'At 15:10, use the last completed NIFTY bar. If it is at least 0.75% below the '
      '09:15 session open, choose a call in the nearest expiry strictly after the next '
      'trading session. Search ATM through three OTM strikes for the closest affordable '
      'liquid whole lot. Size at most 95% including entry fees and reserve exit charges. '
      'Keep a fixed +5% limit; simulate entry one full minute later. Exit by the next '
      'session at 15:10, or after a completed premium close reaches 2x / loses 50%, '
      'with delayed adverse liquidation. The target and stop are not guaranteed fills.','',
      '| Check | Earlier INR | Recent INR |','|---|---:|---:|']
    for scenario in ('primary','delay3','slippage2','delete_best','strict'):
        lines.append(f"| {scenario} | {amount(index['NIFTY_SELLOFF_REBOUND_1510','earlier',scenario])} | {amount(index['NIFTY_SELLOFF_REBOUND_1510','recent',scenario])} |")
    lines+=['','The earlier/recent base paths have four/five filled trades. Positive reported '
      'stress paths are encouraging, but the small number of events, repeated search '
      'over these periods and unresolved strict data audit prevent a live-profit claim. '
      'The next-morning version is a separate frozen variant; the earlier window loses.','',
      '## Execution assumptions and limits','',
      'A fixed limit and quantity are chosen from completed bars before entry. Entry occurs after one '
      'full minute (three in stress), using a later adverse high; exits use later adverse lows and '
      'bounded partial liquidation. A completed premium close, not a future candle high, triggers '
      'the target. An overnight gap can pass a stop and lose much more. Monitoring ends at 15:15 '
      'and resumes with completed bars next session, as registered; this is not a full-session live design. '
      'A pessimistic individual price is not a guaranteed lower bound on strategy returns: limit misses '
      'change which trades occur. Minute volume does not establish available ask/bid or queue priority.','',
      'Cash delivery is unleveraged and includes taxes and DP fees; sale proceeds are not recycled on the same day. '
      'CALL5 avoids stock delivery-margin windows using the frozen seven-calendar-day buffer beyond '
      'planned exit. Current ban-list uncertainty stops a stock-option path. Missing holding/exit data '
      'also stops a path. Corporate-action adjustments are not manufactured. Mark drawdown is a '
      'modeled adverse mark relative to resolved equity peaks, not tick-exact account drawdown.','',
      '## Evidence quality','',
      f'Inspected {len(audit)} stock/option session tapes. Issue counts overlap: `{dict(sourceaudit)}`. '
      'Reported scenarios relax only the specified source volume/tick reconciliation; strict scenarios '
      'stop at those failures. Neither label establishes true historical spread or fillability.','',
      '| Strategy / period | Unresolved primary boundary |','|---|---|']
    for r in index.values():
        if r['scenario']=='primary' and r['unknown']:lines.append(f"| {r['strategy']} / {r['period']} | {str(r['unknown']).replace('|','/')} |")
    lines+=['','## Noise checks','',
      'The 999 paths per case are seeded Monte Carlo direction assignments on the same '
      'historical signal dates, not 999 independent market events. Small signal counts '
      'produce repeated direction patterns. These controls test the direction choice '
      'conditional on the registered event clock; they do not establish that the event '
      'timing beats matched random trading times or validate the strategy out of sample.','']
    for c in controls['results']:
        if c['status']!='CONDITIONAL_RANDOMIZATION':
            lines.append(f"{c['strategy']} / {c['period']}: random qualifying-stock controls UNKNOWN; no significance claim.");continue
        assert len(c['paths'])==999 and [p['seed'] for p in c['paths']]==list(range(999))
        assert sum(p['final_bankroll'] is None for p in c['paths'])==c['unknown']
        assert sum(p['final_bankroll'] is not None and D(p['final_bankroll'])>=D(c['observed']) for p in c['paths'])==c['at_least_observed']
        lines.append(f"{c['strategy']} / {c['period']}: {c['at_least_observed']}/999 random-side paths meet or exceed INR {c['observed']}; "
                     f"{c['unknown']} unresolved controls. Tail probability bounded by [{c['p_lower']:.3f}, {c['p_upper']:.3f}], "
                     f"conservative multiplicity correction over at least 144 variants: {c['adjusted_144_upper']:.3f}.")
    if not controls['results']:
        lines.append('No new primary variant exceeds the registered benchmark, so the contingent 999-path test was not invoked. '
                     'There is no newly established statistical edge. The stock rule positive in both windows still fails '
                     'best-trade deletion, earlier slippage stress and strict data validation.')
    crossfile=OUT/'crosscheck.json'
    if crossfile.exists():
        cross=json.loads(crossfile.read_text());cr=cross['rows'];matched=[r for r in cr if r['dhan'] is not None]
        for p,h in cross['receipt_hashes'].items():assert hashlib.sha256((CACHE/p).read_bytes()).hexdigest()==h,p
        agrees=[r for r in matched if all(D(r['differences'][p])==0 for p in ('open','high','low','close'))]
        lines+=['',f'Dhan cross-check: {len(matched)}/{len(cr)} selected decision/entry/final-exit minutes '
                f'match timestamp and strike; {len(agrees)} have identical OHLC across feeds. '
                'Expiry uses the prior published contract calendar and the requested Dhan weekly expiry code. '
                'This bounded comparison does not repair full-session volume discrepancies or prove fills. '
                '[Cross-broker details](crosscheck.json).']
        entries=[r for r in cr if r['label']=='entry'];executable=[r for r in cr if r['label'] in ('entry','exit')]
        lines.append(f"Dhan's high stays below the fixed entry limit in {sum(r.get('dhan_high_below_submitted_limit',False) for r in entries)}/{len(entries)} entry snapshots; "
                     f"{sum(r.get('dhan_snapshot_capacity_pass',False) for r in executable)}/{len(executable)} entry/final-exit snapshots meet the modeled 5% volume cap. "
                     f"Maximum observed absolute close difference is INR {cross['max_absolute_differences']['close']}. "
                     'These checks do not establish same quotes, targets or intervening holding paths. '
                     'One initial authentication attempt failed; a bounded retry succeeded.')
    lines+=['','## Source corrections preserved','',
      'The initial cash snapshot is retained as `cash_before_source_reconciliation.json`. NSE circular '
      '[CMTR73856](https://nsearchives.nseindia.com/content/circulars/CMTR73856.pdf), published 22 April, '
      'scheduled VEDL special pre-open until 10:00 on 30 April. Its missing 09:15–09:29 bars are therefore '
      'a known unavailable 09:30 entry, not an unexplained missing-data gain/loss. No replacement stock '
      'is chosen. Missing metadata on a farther option is now evaluated only if deterministic selection '
      'reaches that strike; nearer known contracts are not invalidated by unused farther data. '
      'A further data-routing correction requests the same exchange token and expiry from the '
      'expired-history endpoint when cached active metadata predates expiry. The first option run '
      'is retained as `options_before_expiry_route_reconciliation.json`. All corrections were '
      'replayed under unchanged signal/exit thresholds.','',
      '## Other economic mechanisms','',
      'The [mechanism review](../../broader/RESEARCH.md) also covers short volatility, spreads, carry, '
      'auction flows, cross-market signals and commodity micro contracts. Dhan returned **55,598 actual '
      'Gold Petal minute bars** for the recent window. The tested Upstox expired commodity lookup '
      'returned HTTP 400 UDAPI100011. Historical margin paths, exact active/front-contract coverage, '
      'MCX daily-volume reconciliation and account eligibility remain unverified. Gold Petal is '
      '**unscored**, not rejected as unprofitable. Current initial margin cannot be applied retroactively.','',
      '## Reproducibility','',
      f'Validated {validated} resolved scenario trade rows: chronological bankroll, fees, whole lots, '
      '95% pre-entry budgets, fixed limits, timestamps and observed volume participation. '
      f'{parity} unaffected scenario paths exactly match their retained pre-correction runs. '
      'All source/input hashes and the original registration hash are checked by report generation. '
      'Software tests do not prove a market edge. No live orders, deployment or spending occurred.','',
      '[Frozen protocol](../../broader/PROTOCOL.md) · [Reproduction](../../broader/README.md) · '
      '[All 260 paths](scoreboard.csv) · [Ledger](ledger.json) · [Controls](controls.json)','',
      f'Source SHA-256: `{digest()}`','']
    (OUT/'REPORT.md').write_text('\n'.join(lines))
    summary={'source_sha256':digest(),'input_sha256':hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest(),
      'scenarios':len(index),'validated_trades':validated,'unchanged_path_parity':parity,'recent_beats':[r['strategy'] for r in beat],
      'both_profitable':both,'robust':robust,'audit_sessions':len(audit),'audit_issues':dict(sourceaudit),
      'primary_unknown':sum(r['scenario']=='primary' and bool(r['unknown']) for r in index.values()),
      'strict_unknown':sum(r['scenario']=='strict' and bool(r['unknown']) for r in index.values())}
    save(OUT/'verification.json',summary);print(json.dumps(summary))

if __name__=='__main__':main()
