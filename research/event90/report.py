"""Replay frozen event variants and publish conditional, source-bound results."""
import hashlib,json
from collections import Counter
from datetime import datetime,timezone
from decimal import Decimal as D
from pathlib import Path
from urllib.parse import urlsplit

from research.event90.experiment import STORE,OUT,START,END,ENGINES,configure,source_digest
from research.gauntlet.data import save
from research.gauntlet.provenance import digest


def assert_parity(reference,fast):
    if len(reference['ledger'])!=len(fast['ledger']):raise ValueError('Ledger length differs')
    for a,b in zip(reference['ledger'],fast['ledger']):
        if a['signal']['id']!=b['id']:raise ValueError('Signal identity differs')
        if (a['status'],a['cash_before'],a.get('cash_after'))!=(b['status'],b['cash_before'],b.get('cash_after')):
            raise ValueError('Reference/compiled replay mismatch: '+b['id'])
    if reference['last_resolved_cash']!=fast['last_resolved_cash']:raise ValueError('Cash differs')


def rank_bounds(base,paths):
    """Unresolved paths may beat the observed result; never discard them."""
    if base is None or not paths:return None
    resolved=[D(p['terminal_conditional_cash']) for p in paths if p['terminal_conditional_cash'] is not None]
    beaten=sum(x>=D(base) for x in resolved)
    return {'lower':(1+beaten)/(1+len(paths)),
            'upper':(1+beaten+len(paths)-len(resolved))/(1+len(paths)),
            'meaning':'Conditional matched-time random-side rank bounds, not a clean-universe significance test'}


def manifest():
    files=[]
    for name in ('keys.json','universe.json','cash_closes.json','ban_lists.json','event_candidates.json','noise/filings.json','noise/content_event_gaps.json'):
        files.append(STORE/name)
    for folder in ('underlying','futures'):
        files+=list((STORE/folder).glob('*.json'))
    files+=[p for p in (STORE/'public').glob('announcements_*.json') if 'receipt' not in p.name]
    files+=list((STORE/'noise').glob('*_compiled.json'))
    entries={str(p.relative_to(STORE)):digest(p) for p in sorted(files)}
    return {'files':entries,'sha256':hashlib.sha256(json.dumps(entries,sort_keys=True).encode()).hexdigest()}


def audit():
    from research.gauntlet.signals import announcement_records
    records=announcement_records();universe=json.loads((STORE/'universe.json').read_text())
    calendar=sorted(universe);missing=[];malformed=[];minutes=0;days_count=0
    for s in sorted(set(json.loads((STORE/'keys.json').read_text()))&set(records)):
        file=STORE/'underlying'/(s+'.json')
        rows=json.loads(file.read_text()) if file.exists() else []
        byday={}
        for r in rows:byday.setdefault(r[0][:10],[]).append(r)
        for i,day in enumerate(calendar):
            if not str(START)<=day<=str(END) or i==0 or s not in universe[calendar[i-1]]:continue
            bars=byday.get(day,[]);days_count+=1;minutes+=len(bars)
            if not bars:missing.append({'symbol':s,'day':day,'reason':'MISSING_SESSION'});continue
            if bars[0][0][11:16]!='09:15':malformed.append({'symbol':s,'day':day,'reason':'MISSING_OPEN'})
            starts=[datetime.fromisoformat(r[0]) for r in bars]
            # Audit the signal/execution window, not post-close/session-regime bars.
            relevant=[t for t in starts if '09:15'<=t.strftime('%H:%M')<='15:17']
            holes=sum(max(0,int((b-a).total_seconds()/60)-1) for a,b in zip(relevant,relevant[1:]))
            if holes:malformed.append({'symbol':s,'day':day,'reason':'MISSING_MINUTES','count':holes})
    source_rows=[];seen=set()
    for file in sorted((STORE/'public').glob('announcements_*.json')):
        if 'receipt' in file.name:continue
        for row in json.loads(file.read_text()):
            key=row.get('seq_id')
            if key in seen:continue
            seen.add(key);source_rows.append(row)
    gaps=json.loads((STORE/'noise/content_event_gaps.json').read_text())
    docs=json.loads((STORE/'noise/filings.json').read_text())
    verified_documents=0
    for doc in docs['records']:
        if not doc.get('raw_sha') or not doc.get('text_sha'):continue
        key=hashlib.sha256(doc['url'].encode()).hexdigest()
        suffix='.zip' if urlsplit(doc['url']).path.lower().endswith('.zip') else '.pdf'
        raw=STORE/'noise/filings_raw'/(key+suffix)
        text=STORE/'noise/filings_text'/(key+'.txt')
        if digest(raw)!=doc['raw_sha'] or digest(text)!=doc['text_sha']:
            raise ValueError('Original attachment changed: '+key)
        verified_documents+=1
    answer={'filings':docs['total'],'filing_statuses':docs['counts'],'downloaded_announcement_rows':len(source_rows),
            'missing_dissemination_times':sum(not r.get('exchdisstime') for r in source_rows),
            'symbol_sessions':days_count,'minute_rows':minutes,'missing_sessions':missing,'incomplete_sessions':malformed,
            'signal_gaps':dict(Counter(g['reason'] for g in gaps)),
            'exchange_inventory':json.loads((OUT/'input_inventory.json').read_text()),
            'verified_attachment_source_hashes':verified_documents,'full_universe_complete':False,
            'limitations':['Downloaded NSE announcement archive is not a proof of full public information coverage.',
                'Attachment category matching is a frozen textual proxy, not a full materiality assessment.',
                'Current original attachments are assumed to preserve their publication vintage; revisions are not reconstructed.',
                'No historical bid/ask, queue position, second-level latency or complete Dhan RMS archive.',
                'Seven-day stock delivery buffer restricts the strategy universe; this does not reject all near-expiry stock strategies.',
                'July–September discovery data is reused; this is not independent validation.']}
    save(OUT/'coverage.json',answer);return answer


def run():
    configure()
    from research.gauntlet.replay import replay
    from research.noise.paths import Runner
    source_before=source_digest();inputs_before=manifest();save(OUT/'input_manifest.json',inputs_before)
    coverage=audit();summaries=[]
    for engine in ENGINES:
        runner=Runner(engine);base=runner.run();references={}
        audits={}
        for observation in runner.source['observations']:
            for contract in observation['contracts']:
                audits[(contract['key'],observation['signal']['at'][:10])]=contract.get('audit',{'status':contract.get('skip','UNKNOWN_METADATA')})
        audit_counts=dict(Counter(a.get('status','UNKNOWN_METADATA') for a in audits.values()))
        for seed in (None,0,1,2,3,4):
            reference=replay(engine,control='random' if seed is not None else None,seed=seed or 0)
            assert_parity(reference,runner.run(seed))
            references[str(seed)]=reference
        scenarios={}
        for label,delay,adverse in [('primary',1,True),('delay_2',2,True),('delay_3',3,True),('open_plus_1pct',1,False)]:
            ref=references['None'] if label=='primary' else replay(engine,delay=delay,adverse=adverse)
            fast=runner.run(delay=delay,adverse=adverse);assert_parity(ref,fast)
            ref['research_variant']='ORIGINAL_ATTACHMENT_CATEGORY_MATCH_90D_SEVEN_DAY_DELIVERY_BUFFER'
            save(OUT/(engine+'_'+label+'_ledger.json'),ref)
            scenarios[label]={k:v for k,v in fast.items() if k!='ledger'}
            scenarios[label]['full_family_final_bankroll']=None
            scenarios[label]['status_counts']=dict(Counter(r['status'] for r in fast['ledger']))
        trades=[r for r in references['None']['ledger'] if r['status']=='MODELED_ROUND_TRIP']
        winners=[r for r in trades if D(r['net_pnl'])>0]
        deletion=None
        if winners:
            best=max(winners,key=lambda r:D(r['net_pnl']))
            ref=replay(engine,skip_id=best['signal']['id'])
            ref['research_variant']='ORIGINAL_ATTACHMENT_CATEGORY_MATCH_90D_SEVEN_DAY_DELIVERY_BUFFER'
            save(OUT/(engine+'_delete_best_ledger.json'),ref)
            deletion={'deleted_id':best['signal']['id'],'terminal_conditional_cash':ref['final_cash'],
                      'last_resolved_cash':ref['last_resolved_cash'],'reference_status':ref['status'],
                      'full_family_final_bankroll':None,'trades':ref['trades']}
        strict=runner.run(strict=True);save(OUT/(engine+'_strict_ledger.json'),strict)
        paths=[]
        for seed in range(999):
            path=runner.run(seed);path.pop('ledger');paths.append(path)
            if (seed+1)%200==0:print(engine,'random paths',seed+1,flush=True)
        save(OUT/(engine+'_random_paths.json'),paths)
        summary={'engine':engine,'signals':len(runner.source['signals']),'materiality_counts':dict(Counter(s['materiality'] for s in runner.source['signals'])),
                 'scenarios':scenarios,'strict':{k:v for k,v in strict.items() if k!='ledger'},'delete_best':deletion,
                 'random_paths':len(paths),'random_paths_resolved':sum(p['terminal_conditional_cash'] is not None for p in paths),
                 'rank_bounds':rank_bounds(base['terminal_conditional_cash'],paths),'parity_checked_paths':9,
                 'contract_days':len(audits),'contract_audit_counts':audit_counts,
                 'parity_passed':True,'is_champion_eligible':False,'full_family_final_bankroll':None}
        summaries.append(summary);save(OUT/(engine+'_summary.json'),summary)
        runner.outcome.cache_clear()
    source_after=source_digest();inputs_after=manifest()
    if source_before!=source_after or inputs_before!=inputs_after:raise ValueError('Source or input drift during replay')
    summary={'generated_at':datetime.now(timezone.utc).isoformat(),'start':str(START),'end':str(END),'calendar_days':90,
             'trading_sessions':coverage['exchange_inventory']['sessions'],'start_cash':'9411.18','source_sha256':source_after,
             'input_sha256':inputs_after['sha256'],'engines':summaries,'winner':None,'deployment_ready':False,
             'status':'CONDITIONAL_RESEARCH_ONLY','coverage_sha256':digest(OUT/'coverage.json')}
    save(OUT/'summary.json',summary)
    lines=['# Event strategies: ninety-day extension','',f'Period: {START} to {END}; 90 calendar days, {summary["trading_sessions"]} sessions. Each bot starts with INR 9,411.18 independently.','',
           'No live candidate is established. The figures below are conditional bar-model paths, not fully verified executable bankrolls. UNKNOWN observations and missing source coverage prevent a whole-family performance claim.','',
           '| Engine | Scenario | Resolved trades | Conditional ending cash | Last resolved cash |','|---|---|---:|---:|---:|']
    for s in summaries:
        for name,x in s['scenarios'].items():
            lines.append(f'| {s["engine"]} | {name} | {x["trades"]} | {x["terminal_conditional_cash"] or "UNKNOWN"} | {x["last_resolved_cash"]} |')
    lines+=['','Strict coverage replays, complete ledgers, all 1,998 random-side controls and coverage gaps are adjacent JSON artifacts. Independent full-engine/compiled-engine parity passed for nine paths per engine.','',
            'Rank intervals retain unresolved random paths. They are descriptive diagnostics; no significance or superiority is claimed after this continuing strategy search. No profitable-trade deletion is reported when there are no profitable trades.','',
            f'Original attachments: {coverage["filings"]}; status counts: `{coverage["filing_statuses"]}`.',
            f'Underlying sessions missing: {len(coverage["missing_sessions"])}; incomplete: {len(coverage["incomplete_sessions"])}. Signal gap counts: `{coverage["signal_gaps"]}`.','']
    lines+=['- '+x for x in coverage['limitations']]
    lines+=['',f'Source SHA-256: `{source_after}`',f'Input SHA-256: `{inputs_after["sha256"]}`','']
    (OUT/'FINDINGS.md').write_text('\n'.join(lines))
    print('COMPLETE',[(x['engine'],x['scenarios']['primary']['terminal_conditional_cash']) for x in summaries],flush=True)


if __name__=='__main__':run()
