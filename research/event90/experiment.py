"""Extend event coverage in an isolated cache while preserving frozen rules."""
import argparse,csv,hashlib,io,json,shutil,zipfile
from collections import Counter,defaultdict
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import date,datetime,timedelta,timezone
from pathlib import Path

from research.gauntlet import data
from research.gauntlet.data import save

BASE=data.CACHE
STORE=BASE/'event90'
OUT=data.ROOT/'research/results/event90'
START=date(2026,6,21);END=date(2026,9,18);WARM=date(2026,5,15)
ENGINES=('EVENT_CONTINUATION','INTRADAY_EVENT')


def configure():
    """Command-local module bindings; no writes to earlier candidate/result files."""
    from research.gauntlet import collect,signals,contracts,prepare,replay,tape,option_history
    from research.noise import compile,paths,filings,content
    for module in (data,collect,signals,contracts,prepare,replay,tape,option_history,compile,paths,filings,content):
        if hasattr(module,'CACHE'):module.CACHE=STORE
        if hasattr(module,'NOISE'):module.NOISE=STORE/'noise'
    collect.START=signals.START=START;collect.END=signals.END=END;collect.WARMUP=WARM
    tape.DB=STORE/'contract_audit.sqlite'
    content.CANDIDATES=STORE/'event_candidates.json'
    for fn in (contracts.exchange_contracts,contracts.previous_session,contracts.eod_contracts,contracts.exact_metadata,compile.underlying):
        fn.cache_clear()


def source_digest():
    from research.gauntlet.provenance import source_manifest
    files=sorted(Path(__file__).parent.glob('*.py'))+[Path(__file__).with_name('PROTOCOL.md')]
    files+=sorted((data.ROOT/'research/noise').glob('*.py'))
    return hashlib.sha256(source_manifest()['sha256'].encode()+b''.join(str(f.relative_to(data.ROOT)).encode()+f.read_bytes() for f in files)).hexdigest()


def setup():
    STORE.mkdir(parents=True,exist_ok=True)
    for name in ('upstox','option_days','rate_limit'):
        dst=STORE/name
        if not dst.exists():dst.symlink_to(BASE/name,target_is_directory=(BASE/name).is_dir())
    for name in ('public','futures','noise/filings','noise/filings_raw','noise/filings_text'):
        (STORE/name).mkdir(parents=True,exist_ok=True)
        for src in (BASE/name).glob('*'):
            dst=STORE/name/src.name
            if src.is_file() and not dst.exists():dst.symlink_to(src)
    for name in ('keys.json','master.json'):
        if not (STORE/name).exists():shutil.copyfile(BASE/name,STORE/name)
    reg=OUT/'registration.json'
    if not reg.exists():save(reg,{'at':datetime.now(timezone.utc).isoformat(),'start':str(START),'end':str(END),'calendar_days':90,'protocol_sha':hashlib.sha256(Path(__file__).with_name('PROTOCOL.md').read_bytes()).hexdigest(),'untouched_holdout':False})


def read_daily(raw,day):
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        rows=list(csv.DictReader(io.StringIO(z.read(z.namelist()[0]).decode('utf-8-sig'))))
    if not rows or {r['TradDt'] for r in rows}!={day}:raise ValueError('wrong or absent archive trade date')
    return rows


def bootstrap():
    setup();configure()
    nifty=json.loads((BASE/'multifeature90/indexes/NIFTY.json').read_text())['bars']
    days=sorted({r[0][:10] for r in nifty if str(WARM)<=r[0][:10]<=str(END)})
    def job(day):
        name='BhavCopy_NSE_FO_0_0_0_'+day.replace('-','')+'_F_0000.csv.zip'
        try:
            rows=read_daily(data.public('https://nsearchives.nseindia.com/content/fo/'+name,name),day)
            return day,{r['TckrSymb']:r['FinInstrmTp'] for r in rows}
        except Exception as e:return day,{'_error':type(e).__name__+':'+str(e)}
    with ThreadPoolExecutor(max_workers=4) as pool:universe=dict(pool.map(job,days))
    save(STORE/'universe.json',universe)
    closes=json.loads((BASE/'cash_closes.json').read_text())
    def cash(day):
        if day in closes:return day,closes[day]
        name='BhavCopy_NSE_CM_0_0_0_'+day.replace('-','')+'_F_0000.csv.zip'
        try:
            rows=read_daily(data.public('https://nsearchives.nseindia.com/content/cm/'+name,name),day)
            return day,{r['TckrSymb']:{'close':r['ClsPric'],'previous':r['PrvsClsgPric'],'isin':r['ISIN']} for r in rows if r['SctySrs']=='EQ'}
        except Exception as e:return day,{'_error':type(e).__name__+':'+str(e)}
    with ThreadPoolExecutor(max_workers=4) as pool:closes.update(dict(pool.map(cash,days)))
    save(STORE/'cash_closes.json',{d:closes[d] for d in days})
    # Resolve symbol identities using published cash ISINs; current master is
    # only a lookup for remaining cases, never historical F&O membership.
    keys=json.loads((STORE/'keys.json').read_text());identity_gaps=[]
    symbols=set().union(*(set(x) for x in universe.values()))-{'_error'}
    for s in symbols:
        isins={closes[d][s]['isin'] for d in days if s in closes[d] and closes[d][s].get('isin')}
        if len(isins)==1:keys[s]='NSE_EQ|'+next(iter(isins))
        elif len(isins)>1:keys[s]=None;identity_gaps.append({'symbol':s,'reason':'MULTIPLE_HISTORICAL_ISINS'})
        elif s not in keys:keys[s]=None;identity_gaps.append({'symbol':s,'reason':'NO_IDENTITY'})
    save(STORE/'keys.json',{s:keys.get(s) for s in sorted(symbols)})
    start,end='15-06-2026','30-06-2026'
    raw=data.public(f'https://www.nseindia.com/api/corporate-announcements?index=equities&from_date={start}&to_date={end}','announcements_'+start+'_'+end+'.json')
    assert isinstance(json.loads(raw),list)
    bans=json.loads((BASE/'ban_lists.json').read_text())
    def ban(day):
        if day in bans:return day,bans[day]
        dt=date.fromisoformat(day);name=f'fo_secban_{dt:%d%m%Y}.csv'
        try:
            body=data.public('https://nsearchives.nseindia.com/content/fo/'+name,name).decode('utf-8-sig')
            if dt.strftime('%d-%b-%Y').upper() not in body.splitlines()[0].upper():raise ValueError('wrong ban trade date')
            names=[r[1].strip() for r in csv.reader(io.StringIO(body)) if len(r)>1 and r[0].strip().isdigit()]
            return day,{'status':'VERIFIED_DATE','symbols':names}
        except Exception as e:return day,{'status':'UNKNOWN','error':type(e).__name__+':'+str(e)}
    with ThreadPoolExecutor(max_workers=4) as pool:bans=dict(pool.map(ban,[d for d in days if str(START)<=d]))
    save(STORE/'ban_lists.json',bans)
    save(OUT/'input_inventory.json',{'sessions':len(bans),'warm_sessions':len(days),'symbols':len(symbols),'identity_gaps':identity_gaps,'universe_gaps':{d:x for d,x in universe.items() if '_error' in x},'cash_gaps':{d:x for d,x in closes.items() if '_error' in x},'ban_gaps':{d:x for d,x in bans.items() if x['status']!='VERIFIED_DATE'}})
    from research.gauntlet.tape import build_audit
    build_audit()
    print('bootstrap',len(bans),'test sessions',len(days),'including warmup',len(symbols),'symbols',flush=True)


def merge_rows(rows):
    from research.gauntlet.core import Bar
    seen={}
    for r in rows:
        Bar.parse(r)
        if r[0] in seen and seen[r[0]]!=r:raise ValueError('conflicting candle')
        seen[r[0]]=r
    return sorted(seen.values(),key=lambda r:r[0])


def parse_ban(body,day):
    dt=date.fromisoformat(day);lines=body.splitlines()
    if not lines or dt.strftime('%d-%b-%Y').upper() not in lines[0].upper():
        raise ValueError('wrong ban trade date')
    names=[]
    for row in csv.reader(io.StringIO(body)):
        if len(row)>1 and row[0].strip().isdigit():names.append(row[1].strip())
    # A correctly dated explicit no-security statement is required for an
    # empty list; a truncated header is not proof that there were no bans.
    if not names and not any(t in body.upper() for t in ('NO SECURITIES','NIL','NO SECURITY')):
        raise ValueError('no explicit ban-list contents')
    return names


def recover_bans():
    """The exchange report endpoint retains some dates absent from archive URLs."""
    import httpx
    bans=json.loads((STORE/'ban_lists.json').read_text());receipts=[]
    for day,state in sorted(bans.items()):
        if state['status']=='VERIFIED_DATE':continue
        dt=date.fromisoformat(day)
        params={'archives':json.dumps([{'name':'F&O - Security in ban period','type':'archives','category':'derivatives','section':'equity'}]),
                'date':dt.strftime('%d-%b-%Y'),'type':'equity','mode':'single'}
        try:
            r=httpx.get('https://www.nseindia.com/api/reports',params=params,timeout=35,
                        headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.nseindia.com/all-reports-derivatives'})
            receipt={'day':day,'url':str(r.url),'http_status':r.status_code,'sha256':hashlib.sha256(r.content).hexdigest()}
            receipt['retrieved_at']=datetime.now(timezone.utc).isoformat()
            raw=STORE/'public'/('ban_report_'+day+'.csv');raw.write_bytes(r.content)
            if r.status_code!=200:raise ValueError('HTTP '+str(r.status_code))
            names=parse_ban(r.text,day)
            bans[day]={'status':'VERIFIED_DATE','symbols':names,'source_url':str(r.url),'raw_sha256':receipt['sha256']}
            receipt['validated']=True;receipts.append(receipt)
        except Exception as e:receipts.append({'day':day,'validated':False,'error':type(e).__name__+':'+str(e)})
    save(STORE/'ban_lists.json',bans);save(OUT/'ban_reports_recovery.json',receipts)
    file=OUT/'input_inventory.json';inventory=json.loads(file.read_text())
    inventory['ban_gaps']={d:x for d,x in bans.items() if x['status']!='VERIFIED_DATE'};save(file,inventory)
    print('recovered bans',sum(r['validated'] for r in receipts),'remaining',len(inventory['ban_gaps']),flush=True)


def market():
    configure()
    from research.gauntlet.signals import announcement_records
    records=announcement_records();keys=json.loads((STORE/'keys.json').read_text())
    old_keys=json.loads((BASE/'keys.json').read_text())
    def job(s):
        file=STORE/'underlying'/(s+'.json')
        if file.exists():return {'symbol':s,'status':'CACHED','rows':len(json.loads(file.read_text()))}
        try:
            if not keys[s]:raise ValueError('missing historical identity')
            old=BASE/'underlying'/(s+'.json')
            rows=json.loads(old.read_text()) if old.exists() and old_keys.get(s)==keys[s] else []
            rows=[r for r in rows if str(WARM)<=r[0][:10]<=str(END)]
            until=date.fromisoformat(min(r[0][:10] for r in rows))-timedelta(days=1) if rows else END
            at=WARM
            while at<=until:
                end=min(at+timedelta(days=27),until);rows+=data.candles(keys[s],str(at),str(end));at=end+timedelta(days=1)
            rows=merge_rows(rows);save(file,rows)
            return {'symbol':s,'status':'DOWNLOADED','rows':len(rows),'first':rows[0][0] if rows else None,'last':rows[-1][0] if rows else None}
        except Exception as e:return {'symbol':s,'status':'UNKNOWN','error':type(e).__name__+':'+str(e)}
    jobs=sorted(set(records)&set(keys));out=[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        for i,r in enumerate(pool.map(job,jobs),1):
            out.append(r);save(STORE/'underlying_download.json',out)
            if i%20==0:print('underlying',i,'/',len(jobs),dict(Counter(x['status'] for x in out)),flush=True)
    print('underlying finished',len(out),dict(Counter(x['status'] for x in out)),flush=True)


def filings():
    configure()
    from research.noise.filings import run
    run(workers=8)


def signals():
    configure()
    from research.gauntlet import signals as rules
    from research.noise.content import content_records,scan
    from research.gauntlet.prepare import future_job
    docs=json.loads((STORE/'noise/filings.json').read_text())
    records=content_records(rules.announcement_records(),docs['records'])
    rows=scan(records)
    pending=sorted({(s['symbol'],s['at'][:10]) for s in rows if s['futures_confirmation']=='PENDING'})
    with ThreadPoolExecutor(max_workers=3) as pool:receipts=list(pool.map(lambda x:future_job(*x),pending))
    save(STORE/'futures_download.json',receipts)
    if pending:rows=scan(records)
    print('first signals',dict(Counter(s['engine'] for s in rows)),'materiality',dict(Counter(s['materiality'] for s in rows)),flush=True)


def compile():
    configure()
    from research.noise import compile as compiler
    from research.gauntlet.provenance import source_manifest,digest
    from research.gauntlet.contracts import option_candidates,exact_signal_contract
    from research.gauntlet.core import D
    from research.gauntlet.option_history import day_path,plan_ranges,fetch_range
    rows=json.loads((STORE/'event_candidates.json').read_text());jobs={};errors=[]
    for s in rows:
        if s['materiality']!='QUALIFYING_TEXT':continue
        try:
            for side in ('CE','PE'):
                for c in option_candidates(s['symbol'],s['at'][:10],D(s['spot']),side):
                    if not day_path(c.key,s['at'][:10]).exists():jobs[c.key,s['at'][:10]]={'contract_key':c.key,'day':s['at'][:10]}
        except Exception as e:errors.append({'id':s['id'],'error':type(e).__name__+':'+str(e)})
    ranges=plan_ranges(list(jobs.values()));save(STORE/'option_collection_plan.json',{'jobs':list(jobs.values()),'ranges':ranges,'errors':errors})
    print('option requests',len(ranges),'days',len(jobs),flush=True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        for i,f in enumerate(as_completed([pool.submit(fetch_range,r) for r in ranges]),1):
            try:f.result()
            except Exception as e:print('range failure',type(e).__name__,flush=True)
            if i%40==0:print('requests',i,'/',len(ranges),flush=True)
    for engine in ENGINES:
        signals=sorted([r for r in rows if r['engine']==engine],key=lambda r:(r['at'],r['symbol'],r['side']))
        with ThreadPoolExecutor(max_workers=3) as pool:
            observations=list(pool.map(compiler.compile_one,[(s,side) for s in signals for side in ('CE','PE')]))
        save(STORE/'noise'/(engine+'_compiled.json'),{'engine':engine,'signals':signals,'observations':observations,'source_sha':source_manifest()['sha256'],'input_sha':digest(STORE/'event_candidates.json'),'compiler_sha':digest(compiler.__file__),'ban_sha':digest(STORE/'ban_lists.json')})
        print('compiled',engine,len(signals),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['bootstrap','recover_bans','market','filings','signals','compile']);a=p.parse_args();globals()[a.stage]()
