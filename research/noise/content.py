"""Full-attachment event variant; preserves the original discovery inputs/results."""
import json
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from decimal import Decimal as D
from research.gauntlet import signals as rules
from research.gauntlet import replay as original_replay
from research.gauntlet.data import CACHE,save
from research.gauntlet.prepare import future_job
from research.gauntlet.provenance import digest,source_manifest
from research.noise.compile import NOISE,compile_one
from research.noise.paths import Runner
from research.noise.universe import relevant

CANDIDATES=NOISE/'content_event_candidates.json'

def content_records(records,documents):
    byurl={x['url']:x for x in documents}
    out={}
    for symbol,rows in records.items():
        out[symbol]=[]
        for original in rows:
            r=dict(original)
            if relevant(r):
                document=byurl.get(r['url'],{})
                r['quality']=('QUALIFYING_TEXT' if document.get('status')=='CATEGORY_MATCH' else
                              'OTHER' if document.get('status')=='OWNERSHIP_NOTICE' else 'UNKNOWN_MATERIALITY')
                r['category']='ATTACHMENT:'+','.join(document.get('categories',[]))
            out[symbol].append(r)
    return out

def scan(records):
    def capture(file,value):
        target={'event_candidates.json':CANDIDATES,'event_gaps.json':NOISE/'content_event_gaps.json'}
        if file.name not in target:raise ValueError('Unexpected scan output '+str(file))
        save(target[file.name],value)
    old_records=rules.announcement_records;old_save=rules.save
    try:
        rules.announcement_records=lambda:records;rules.save=capture;rules.scan_events()
    finally:rules.announcement_records=old_records;rules.save=old_save
    return json.loads(CANDIDATES.read_text())

def reference_replay(engine):
    """Use the original full engine, redirect only input and output paths."""
    saved=original_replay.SOURCES[engine];writer=original_replay.save
    def capture(file,result):
        if file.parent.name=='history':return
        save(NOISE/(engine+'_content_reference.json'),result)
    try:
        original_replay.SOURCES[engine]=str(CANDIDATES.relative_to(CACHE))
        original_replay.save=capture
        return original_replay.replay(engine)
    finally:
        original_replay.SOURCES[engine]=saved;original_replay.save=writer

def run():
    from research.noise import compile as compiler,filings,universe
    docs=json.loads((NOISE/'filings.json').read_text())
    assert docs['classifier_sha']==digest(filings.__file__)
    assert docs['universe_sha']==digest(universe.__file__)
    assert docs['total']==len(docs['records'])==3413
    records=content_records(rules.announcement_records(),docs['records'])
    candidates=scan(records)
    pending=sorted(set((s['symbol'],s['at'][:10]) for s in candidates if s['futures_confirmation']=='PENDING'))
    with ThreadPoolExecutor(max_workers=3) as pool:
        results=list(pool.map(lambda args:future_job(*args),pending))
    save(NOISE/'content_futures.json',results)
    if pending:candidates=scan(records)
    print('CONTENT_CANDIDATES',dict(Counter(s['engine'] for s in candidates)),flush=True)
    summaries=[]
    for engine in ('EVENT_CONTINUATION','INTRADAY_EVENT'):
        signals=sorted([s for s in candidates if s['engine']==engine],key=lambda s:(s['at'],s['symbol'],s['side']))
        with ThreadPoolExecutor(max_workers=3) as pool:
            observations=[]
            for i,x in enumerate(pool.map(compile_one,[(s,side) for s in signals for side in ('CE','PE')]),1):
                observations.append(x)
                if i%40==0:print('CONTENT_COMPILE',engine,i,'/',len(signals)*2,flush=True)
        file=NOISE/(engine+'_content_compiled.json')
        save(file,{'engine':engine,'signals':signals,'observations':observations,
            'source_sha':source_manifest()['sha256'],'input_path':str(CANDIDATES.relative_to(CACHE)),
            'input_sha':digest(CANDIDATES),'compiler_sha':digest(compiler.__file__),'ban_sha':digest(CACHE/'ban_lists.json')})
        r=Runner(engine,file);base=r.run();ref=reference_replay(engine)
        assert len(base['ledger'])==len(ref['ledger'])
        for a,b in zip(base['ledger'],ref['ledger']):
            assert (a['status'],a['cash_before'],a.get('cash_after'))==(b['status'],b['cash_before'],b.get('cash_after'))
        assert base['last_resolved_cash']==ref['last_resolved_cash']
        paths=[]
        for seed in range(999):
            path=r.run(seed);path.pop('ledger');paths.append(path)
            if (seed+1)%200==0:print('CONTENT_CONTROLS',engine,seed+1,flush=True)
        complete=[D(p['terminal_conditional_cash']) for p in paths if not p['stopped']]
        unknown=len(paths)-len(complete);rank=None
        if base['terminal_conditional_cash'] is not None:
            beaten=sum(v>=D(base['terminal_conditional_cash']) for v in complete)
            rank={'lower':(beaten+1)/1000,'upper':(beaten+unknown+1)/1000}
        save(NOISE/(engine+'_content_paths.json'),paths)
        summary={'engine':engine,'variant':'ORIGINAL_ATTACHMENT_CATEGORY_MATCH','baseline':base,'strict':r.run(strict=True),
            'signals':len(signals),'materiality_counts':dict(Counter(s['materiality'] for s in signals)),
            'reference_parity_passed':True,'reference_sha':digest(NOISE/(engine+'_content_reference.json')),
            'compiled_sha':digest(file),'input_sha':digest(CANDIDATES),'runner_sha':digest('research/noise/paths.py'),
            'content_script_sha':digest(__file__),'filings_sha':digest(NOISE/'filings.json'),
            'random_paths':len(paths),'unresolved_random_paths':unknown,'rank_bounds':rank,
            'random_terminal_percentiles':None if not complete else {str(p):str(sorted(complete)[int((len(complete)-1)*p)]) for p in (.05,.5,.95)},
            'random_profitable_completed_paths':sum(v>D('9411.18') for v in complete),
            'paths_sha':digest(NOISE/(engine+'_content_paths.json'))}
        save(NOISE/(engine+'_content.json'),summary);summaries.append(summary)
        print('CONTENT_REPLAY',engine,{k:v for k,v in base.items() if k!='ledger'},flush=True)
        r.outcome.cache_clear()
    save(NOISE/'content_summary.json',{'engines':summaries,'generated_at':datetime.now(timezone.utc).isoformat(),
        'filings_counts':docs['counts'],'full_family_winner':None,
        'limitations':['Remaining unselected subject categories stay outside variant','Unparsed or ambiguous documents remain UNKNOWN',
            'Original attachment URL and dissemination time are the publication-vintage assumption',
            'Same discovery period; no independent validation; bar fills and historical RMS remain conditional']})

if __name__=='__main__':run()
