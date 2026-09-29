"""Publish derived research results only; never turn missing coverage into P&L.

The report refuses partial/stale sweeps. Licensed market history remains private.
Run after the bounded sweep: python -m research.report
"""
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal as D
from pathlib import Path

from research.gauntlet.data import CACHE, ROOT, save
from research.gauntlet.provenance import source_manifest, digest
from research.gauntlet.replay import SOURCES

OUT = ROOT / 'research/results'
START = D('9411.18')
SCOPES = {
    'EVENT_CONTINUATION': 'NSE disclosure-metadata classifier; seven-day stock expiry buffer',
    'INTRADAY_EVENT': 'NSE intraday disclosure metadata; same expiry buffer',
    'NONEXPIRY_FORCED_FLOW': '21,415 NSE exact-contract days; persistent spot strike crossings',
    'EXPIRY_FORCED_FLOW': 'NSE index expiry spot crossings; excludes auction indicative-index signals',
    'PASSIVE_FLOW': 'August MSCI Standard additions/deletions only',
    'SCHEDULED_EVENT_VOL': 'August RBI decision; NIFTY/BANKNIFTY straddle filter only',
    'BLOCK_OFS_DISLOCATION': 'Disclosed LICI OFS only',
    'SECTOR_SHOCK_LAG': 'Bank and software index leads; graph fitted before July 20',
    'CROSS_MARKET_LEAD_LAG': 'GIFT-to-NIFTY only; assumed two-minute feed delay',
}

def read(name):
    return json.loads((CACHE / name).read_text())

def money(value):
    return f'{D(value):,.2f}' if value is not None else 'UNKNOWN'

def unresolved_path(result):
    terminal = result['ledger'][-1] if result['ledger'] else {}
    status = terminal.get('status','')
    return (status in ('UNKNOWN_ENTRY_BAR','UNKNOWN_HOLDING_BAR','UNKNOWN_EXIT_CAPACITY',
                       'UNKNOWN_EXIT','UNKNOWN_FUTURE_CONFIRMATION') or
            (status=='UNKNOWN_DATA_ERROR' and terminal.get('entry',{}).get('status')=='MODELED_FILL'))

def balance_label(row):
    return money(row['conditional_cash']) + (' *stopped*' if row['unresolved_path'] else '')

def current_result(path, source_sha):
    result = json.loads(path.read_text())
    if (result['execution_revision'] != 5 or result['source_drift_during_run'] or
            result['source_manifest']['sha256'] != source_sha or
            result['signal_input_sha256'] != digest(CACHE / SOURCES[result['engine']]) or
            result['ban_lists_sha256'] != digest(CACHE / 'ban_lists.json')):
        raise ValueError('Stale result: ' + path.name)
    return result

def audit_ledger(result):
    cash = START
    last_exit = None
    for row in result['ledger']:
        if D(row['cash_before']) != cash:
            raise ValueError('Cash chronology failed: ' + row['signal']['id'])
        if row['status'] != 'MODELED_ROUND_TRIP':
            continue
        order, entry, exit_ = row['order'], row['entry'], row['exit']
        if order['quantity'] % order['lot']:
            raise ValueError('Fractional lot')
        if not order['decided'] < entry['time'] < exit_['time']:
            raise ValueError('Noncausal execution timestamps')
        if last_exit is not None and order['decided'] <= last_exit:
            raise ValueError('Overlapping positions')
        expected = cash + (D(exit_['price']) - D(entry['price'])) * order['quantity'] - D(row['fees'])
        if abs(expected - D(row['cash_after'])) > D('.00000001'):
            raise ValueError('Trade cash reconciliation failed')
        cash = D(row['cash_after'])
        last_exit = exit_['time']
    if cash != D(result['last_resolved_cash']):
        raise ValueError('Terminal conditional cash reconciliation failed')

def write_ledger(result):
    fields = ['signal_id','symbol','side','signal_time','event_time','event_url','status',
              'cash_before','contract','expiry','strike','lot','quantity','limit',
              'entry_time','entry_price','exit_time','exit_price','exit_reason','fees',
              'net_pnl','cash_after','premium_multiple','rejected_contracts','error']
    path = OUT / 'ledgers' / (result['engine'] + '.csv')
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in result['ledger']:
            s, o, en, ex = (row.get(k,{}) for k in ('signal','order','entry','exit'))
            writer.writerow({
                'signal_id':s.get('id'),'symbol':s.get('symbol'),'side':s.get('side'),
                'signal_time':s.get('at'),'event_time':s.get('event_at'),'event_url':s.get('event_url'),
                'status':row['status'],'cash_before':row['cash_before'],'contract':o.get('key'),
                'expiry':o.get('expiry'),'strike':o.get('strike'),'lot':o.get('lot'),
                'quantity':o.get('quantity'),'limit':o.get('limit'),'entry_time':en.get('time'),
                'entry_price':en.get('price'),'exit_time':ex.get('time'),'exit_price':ex.get('price'),
                'exit_reason':ex.get('reason'),'fees':row.get('fees'),'net_pnl':row.get('net_pnl'),
                'cash_after':row.get('cash_after'),'premium_multiple':row.get('premium_multiple'),
                'rejected_contracts':json.dumps(row.get('rejected_contracts',[]),separators=(',',':')),
                'error':row.get('error'),
            })

def main():
    suite = read('suite_progress.json')
    if suite['status'] != 'COMPLETED_DISCOVERY_SWEEP' or len(suite['completed_engines']) != 9:
        raise RuntimeError('Nine bounded experiments have not finished')
    sha = source_manifest()['sha256']
    results, scenarios, scoreboard = {}, [], []
    OUT.mkdir(parents=True, exist_ok=True)
    for engine in SOURCES:
        files = sorted((CACHE/'results').glob('v5_' + engine + '_*.json'))
        variants = [current_result(p,sha) for p in files]
        for r in variants:
            audit_ledger(r)
            scenarios.append({
                'engine':engine,'delay_bars':r['delay_bars'],'entry_model':r['entry_model'],
                'control':r['control'],'control_seed':r['control_seed'],
                'best_trade_deleted':any(x['status']=='BEST_TRADE_DELETED' for x in r['ledger']),
                'status':r['status'],'trades':r['trades'],'targets':r['targets'],
                'conditional_cash':r['last_resolved_cash'],'coverage_gaps':len(r['coverage_gaps']),
                'unresolved_path':unresolved_path(r),
                'full_family_bankroll':None,
            })
        r = current_result(CACHE/'results'/('v5_'+engine+'_1_high.json'),sha)
        results[engine] = r
        write_ledger(r)
        trades = [x for x in r['ledger'] if x['status']=='MODELED_ROUND_TRIP']
        row = {'engine':engine,'scope':SCOPES[engine],'signals':r['signals'],
               'trades':r['trades'],'wins':r['wins'],'targets':r['targets'],
               'conditional_cash':r['last_resolved_cash'],
               'conditional_return_pct':str((D(r['last_resolved_cash'])/START-1)*100),
               'closed_trade_drawdown_pct':str(D(r['closed_trade_max_drawdown'])*100),
               'half_premium_losses':r['half_losses'],'replay_status':r['status'],
               'coverage_gap_records':len(r['coverage_gaps']),
               'signals_examined':len(r['ledger']),'unresolved_path':unresolved_path(r),
               'conditional_terminal_cash':None if unresolved_path(r) else r['last_resolved_cash'],
               'trade_dates':len(set(t['signal']['at'][:10] for t in trades)),
               'trade_underlyings':len(set(t['signal']['symbol'] for t in trades)),
               'full_family_bankroll':None,'champion_eligible':False,
               'outcomes':dict(Counter(x['status'] for x in r['ledger']))}
        scoreboard.append(row)
    reconciliation = read('nonexpiry_reconciliation.json')
    expected=len(SOURCES)+sum((8 if r['signals'] else 0)+(1 if r['trades'] else 0) for r in results.values())
    if len(scenarios)!=expected:
        raise RuntimeError(f'Expected {expected} distinct scenarios; found {len(scenarios)}')
    underlying_counts={p.stem:len(json.loads(p.read_text())) for p in (CACHE/'underlying').glob('*.json')}
    expiry = read('expiry_scan.json')
    cross = read('cross_broker_audit.json')
    condition_cross = read('forced_cross_broker_conditions.json')
    report = {
        'generated_at':datetime.now(timezone.utc).isoformat(),
        'status':'BOUNDED_DISCOVERY_COMPLETE_FULL_GAUNTLET_INCOMPLETE',
        'window':['2026-07-20','2026-09-18'],'start_cash_each':str(START),
        'source_sha256':sha,'suite':suite,'winner':None,
        'full_family_bankrolls_available':0,'validated_families':0,
        'underlying_files':len(underlying_counts),'underlying_bars':sum(underlying_counts.values()),
        'scoreboard':scoreboard,'scenarios':scenarios,
        'nonexpiry_reconciliation':reconciliation,'expiry_audit':expiry,
        'cross_broker_prices':cross,'cross_broker_necessary_conditions':condition_cross,
        'noise_verdict':'INCONCLUSIVE: five random-side controls cannot establish 5% significance; no untouched holdout.',
        'cash_interpretation':'Conditional on observed inputs and assumed bar fills; unknown trades can change all subsequent bankrolls.',
        'remaining':[
            'Full event-content classification, not disclosure subject-line matching.',
            'Resolve 2,188 non-expiry contract-day volume mismatches and per-replay missing history/metadata.',
            'Full-family inputs: auction IEP sequence, wider event calendars, index weights/flow estimates, block announcements and external/exposure graph coverage.',
            'Historical broker-specific RMS and actual bid/ask/depth, OI publication and feed/decision/order latency.',
            'Untouched holdout and clustered, selection-adjusted statistical validation.',
        ],
    }
    save(OUT/'scoreboard.json',report)
    fields=[k for k in scoreboard[0] if k!='outcomes']
    with (OUT/'scoreboard.csv').open('w',newline='') as handle:
        w=csv.DictWriter(handle,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(scoreboard)
    with (OUT/'execution_scenarios.csv').open('w',newline='') as handle:
        w=csv.DictWriter(handle,fieldnames=list(scenarios[0]));w.writeheader();w.writerows(scenarios)

    lines=[
        '# Nine-bot discovery results — 19 September 2026','',
        '**The bounded current-data experiments are finished. No bot has earned selection. '
        'The requested full-universe, executable and statistically validated gauntlet remains incomplete.**','',
        'Each bot starts independently with INR 9,411.18 on July 20 and runs through September 18 '
        '(61 calendar days, 44 sessions). Rules were influenced by the supplied historical examples; '
        'this period is discovery, not holdout. No live orders were submitted.','',
        '**These are conditional model balances, not verified executable bankrolls.** '
        'Missing inputs could change earlier trades and every subsequent order. Zero-signal variants '
        'retain cash only within their stated scope; they cannot be ranked as winning full strategy families.','',
        '| Bot | Signals | Closed trades | Wins | 2x targets | Cash after resolved trades (INR) | Replay gap records |',
        '|---|---:|---:|---:|---:|---:|---:|',
    ]
    for row in scoreboard:
        lines.append(f"| {row['engine']} | {row['signals']} | {row['trades']} | {row['wins']} | {row['targets']} | {balance_label(row)} | {row['coverage_gap_records']} |")
    lines += ['', 'Gap records above concern entry/exit replay. Additional signal-cohort gaps and scope '
              'exclusions apply even when that column is zero. Full-family bankroll is **UNKNOWN for all nine**. '
              '*Stopped* means an unresolved position or missing input halted the path; its displayed amount '
              'is the balance before that unresolved trade, not final equity or current free cash.', '',
              '| Bot | Precisely tested scope |','|---|---|']
    lines += [f"| {r['engine']} | {r['scope']} |" for r in scoreboard]
    lines += ['', '**Execution sensitivity and controls**','',
              'Every strategy with signals was rerun with 1/2/3-minute entry delay, an alternative '
              'next-bar open plus 1% entry, and five matched-time random-side controls. Strategies with '
              'closed trades were rerun after deleting the highest-P&L trade. Deletion repeats '
              'chronological contract selection and sizing; it does not simply subtract a profit.', '',
              'If all closed baseline trades lose, "best" means the least-negative trade. '
              'In EVENT_CONTINUATION, deleting the losing L&T July 29 trade changes the later '
              'path and produces INR 13,865.97 in the conditional scenario, with 136 coverage '
              'gap records. This is a retrospective perturbation, not a tradable instruction '
              'to skip L&T or evidence that the original bot earned that amount.', '',
              '| Bot | 1-min high | 2-min high | 3-min high | Open +1% | Delete best | Five random-side balances |',
              '|---|---:|---:|---:|---:|---:|---|']
    for engine,r in results.items():
        if not r['signals']:continue
        ss=[s for s in scenarios if s['engine']==engine]
        def val(delay=1,opening=False,delete=False):
            found=next((s for s in ss if s['delay_bars']==delay and s['best_trade_deleted']==delete and
                        not s['control'] and ('open' in s['entry_model'])==opening),None)
            return balance_label(found) if found else 'n/a'
        randoms=sorted([s for s in ss if s['control']],key=lambda x:x['control_seed'])
        lines.append(f"| {engine} | {val()} | {val(2)} | {val(3)} | {val(opening=True)} | {val(delete=True)} | "+
                     '; '.join(balance_label(s) for s in randoms)+' |')
    lines += ['', 'All sensitivity balances retain the same conditional-data limitation. If a path stops '
              'with an unknown holding/exit, the CSV labels it and cash is only the last resolved cash. '
              'Closed-trade drawdown omits intratrade drawdown and is not an executable liquidation bound.', '',
              'Five random paths are diagnostic only: even outranking all five gives a smallest '
              'plus-one randomization rank of 1/6, before accounting for nine tested families. The controls '
              'also condition on event times selected by the strategy. No significant edge, causal proof, '
              'family-adjusted p-value, or out-of-sample validation is claimed.', '',
              '**What was actually acquired and checked**','',
              f"- {sum(underlying_counts.values()):,} underlying minute bars across {len(underlying_counts)} files, with warm-up history; 68 daily exchange contract files and 44 dated F&O ban lists.",
              '- 47,097 exchange announcement records downloaded; original dissemination timestamps gate the metadata variant.',
              f"- All {reconciliation['contract_days']:,} planned non-expiry option contract-days collected: "
              f"{reconciliation['counts'].get('CHECKED_RECONCILED',0):,} match official traded units exactly; "
              f"{reconciliation['counts'].get('UNKNOWN_VOLUME_RECONCILIATION',0):,} remain unknown.",
              f"- Expiry: {expiry['crossings']} persistent strike-cross prospects, {expiry['signals']} observed signals, "
              f"{len(expiry['gaps'])} unresolved audit records; historical CAS indicative-index paths absent.",
              '- Four NIFTY signal-minute comparisons with Dhan found close-price differences of +0.95, -0.30, -0.20 and +0.15 rupees. OI also differs in three of four. The premium-rise and OI-fall necessary conditions survive all four cross-checks; the complete signal, denominator and fills are not independently certified.',
              '- Dhan read-only account access confirms the derivatives segment is active. Account approval does not validate a trading rule.', '',
              '**How fills and information were modeled**','',
              'Completed minute bars only; historical membership from the prior exchange file; 20 prior '
              'sessions for same-time RVOL; event availability from dissemination timestamps. Exact '
              'contract identity, historical lot size and metadata are resolved before selection. '
              'Each order fixes whole-lot quantity, a last-price-plus-5% limit and cash including fees '
              'before looking at arrival bars. At most 95% of cash is deployed. Both prior liquidity '
              'and arrival volume limit modeled participation to 5%. No order is resized using future affordability.', '',
              'Adverse entry uses the next eligible full bar high only within the fixed limit. '
              'Targets require a later bar trading 2% beyond twice entry; entry-bar targets are excluded. '
              'Invalidations use delayed adverse exits; unresolved holdings stop the path. Scheduled '
              'liquidation is 15:10–15:17, with partial fills and fees retained. Stock contracts within '
              'seven calendar days of expiry are excluded, changing the original near-expiry stock thesis. '
              'This conservative bar scenario still cannot establish historical bid/ask, queue position '
              'or 1/3/5-second execution. Costs use the documented conservative Dhan/NSE fee envelope.', '',
              '**Interpretation and remaining work**','',
              'The earlier EVENT_CONTINUATION leadership claim is withdrawn: anecdotes did not establish '
              'a winning strategy. Its implemented metadata classifier can mistake takeover/ownership '
              'disclosures mentioning acquisition for a material business acquisition. That is a '
              'measured specification weakness; fixing it after observing outcomes creates another '
              'discovery variant and requires separate validation.', '',
              'Concrete execution failure: the event baseline reached a WAAREEENER August 25 '
              '2200 PE entry on July 30 at 09:20, one 175-unit lot modeled at INR 10.85. '
              'The planned exit could not liquidate that lot within the frozen 5% participation '
              'limit by 15:17. The path stops there. INR 2,574.15 is the cash before this '
              'unresolved trade, not a September ending balance. This is why daily volume '
              'and an affordable entry are insufficient evidence of executable compounding.', '',
              'The famous examples were not credited retrospectively. Solar generates a September '
              '15 09:20 put candidate, but the event bankroll path had already stopped at the '
              'unresolved July 30 position. KFin generates a July 27 09:26 call candidate; its '
              'board-outcome metadata is ambiguous, so it is outside this narrow metadata variant '
              '(not evidence that the actual announcement was immaterial). Coforge on July 28 '
              'and Bandhan on July 22 reach the selector with only INR 4,632.84 remaining; none '
              'of the reached eligible contracts passes the affordability/past-capacity gate. '
              'No qualifying Kaynes July 29 signal appears in this exact exchange-metadata rule.', '',
              'OI decline with a premium rise is a positioning proxy. It does not identify which side '
              'initiated trades or establish that writers were forced out. Likewise, large daily volume '
              'does not prove a one-lot fill at the desired timestamp.', '',
              'Remaining requirements are concrete: complete primary-event content and the missing '
              'family-specific datasets; reconcile uncertain option histories and historical RMS; '
              'obtain quote/depth and availability-time evidence; then freeze a surviving candidate '
              'and test an untouched period with enough independent event/day observations. '
              'No amount of additional in-sample threshold tuning substitutes for those checks.', '',
              'Reproduce with `.venv/bin/python -m research.run_suite --wait-for-reconciliation`, then '
              '`.venv/bin/python -m research.report`. The focused suite is '
              '`.venv/bin/python -m pytest tests/test_gauntlet.py -q`. '
              'Its tests cover information boundaries, whole lots, fees, capacity, ambiguous exits '
              'and missing data; they do not prove market profitability.', '',
              'Derived [scoreboard](scoreboard.csv), [scenario results](execution_scenarios.csv), '
              'and per-bot [ledgers](ledgers/) include rejected signals as well as trades. '
              'Raw licensed data and provider receipts stay in the ignored private artifact directory.','',
              f'Source digest: `{sha}`. Report generated {report["generated_at"]}.', '',
              'Primary source references: [Upstox expired candles](https://upstox.com/developer/api-documentation/get-expired-historical-candle-data/), '
              '[Dhan expired options](https://dhanhq.co/docs/v2/expired-options-data/), '
              '[Dhan RMS](https://dhan.co/risk-management-policy/), '
              '[MSCI changes](https://www.msci.com/eqb/gimi/stdindex/MSCI_Aug26_STPublicList.pdf), '
              '[RBI calendar](https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=62422), '
              '[LICI OFS](https://nsearchives.nseindia.com/corporate/tchari_03082026210047_LICI_OFSNOTICE.pdf).',
    ]
    (OUT/'GAUNTLET.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({'status':report['status'],'scenarios':len(scenarios),'winner':None,'source_sha':sha}))

if __name__ == '__main__':
    main()
