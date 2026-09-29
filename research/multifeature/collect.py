"""Collect all pre-decision inputs before retrieving outcome option tapes."""
import argparse,csv,hashlib,io,json,time,zipfile
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import date,datetime,timedelta,timezone
from urllib.parse import quote
from research.gauntlet.data import CACHE,save,candles,contracts,public,upstox
from research.gauntlet.core import Bar,Contract,D
from research.expiry.collect import STORE as OLD, selected_chain,fetch,option_file
from .providers import STORE,OUT,dhan_token,rolling,request

BEGIN=date(2026,3,23);END=date(2026,9,18);WARM=date(2026,3,19)
WINDOWS={'earlier':('2026-03-23','2026-06-20'),'recent':('2026-06-21','2026-09-18')}

def partition(day):return 'earlier' if day<='2026-06-20' else 'recent'

def chunks(begin=WARM,end=END):
    at=begin
    while at<=end:
        until=min(at+timedelta(days=27),end)
        yield str(at),str(until)
        at=until+timedelta(days=1)

def registration():
    f=OUT/'registration.json'
    if not f.exists():save(f,{'registered_at':datetime.now(timezone.utc).isoformat(),'windows':WINDOWS,
        'protocol_sha256':hashlib.sha256(__import__('pathlib').Path(__file__).with_name('PROTOCOL.md').read_bytes()).hexdigest(),
        'retrospective':True,'start_bankroll':'9411.18','live_orders':False})

def indexes():
    registration()
    keys={'NIFTY':'NSE_INDEX|Nifty 50','BANK':'NSE_INDEX|Nifty Bank','IT':'NSE_INDEX|Nifty IT',
          'VIX':'NSE_INDEX|India VIX','GIFT':'GLOBAL_INDEX|SGX NIFTY'}
    for symbol,key in keys.items():
        f=STORE/'indexes'/(symbol+'.json')
        if f.exists():continue
        rows=[];errors=[]
        if symbol=='NIFTY':rows=[r for r in json.loads((OLD/'spot.json').read_text()) if str(WARM)<=r[0][:10]<=str(END)]
        else:
            for start,end in chunks():
                try:rows+=candles(key,start,end)
                except Exception as e:errors.append({'start':start,'end':end,'error':str(e)})
        by={}
        for r in rows:
            Bar.parse(r)
            if r[0] in by and r!=by[r[0]]:raise ValueError('conflicting index timestamp')
            by[r[0]]=r
        save(f,{'key':key,'bars':sorted(by.values()),'errors':errors})
        print('index',symbol,'rows',len(by),'errors',errors,flush=True)

def dhan():
    registration();access=dhan_token();receipts=[]
    jobs=[]
    for start,end in chunks(BEGIN):
        exclusive=str(date.fromisoformat(end)+timedelta(days=1))
        for offset in range(-3,4):
            for side in ('CE','PE'):
                jobs.append((start,exclusive,offset,side))
    def pull(j):
        start,end,offset,side=j;r=rolling(start,end,offset,side,access)
        x=(r.get('body',{}).get('data') or {}).get('ce' if side=='CE' else 'pe') or {}
        return {'start':start,'end':end,'side':side,'offset':offset,'status':r['status'],
                'rows':len(x.get('timestamp',[])),'fields':list(x),'request':r.get('request')}
    with ThreadPoolExecutor(max_workers=4) as pool:
        for f in as_completed([pool.submit(pull,j) for j in jobs]):
            receipts.append(f.result());save(STORE/'dhan_download.json',receipts)
            if len(receipts)%10==0 or len(receipts)==len(jobs):print('Dhan requests',len(receipts),'/',len(jobs),'successful',sum(r['status']==200 for r in receipts),'rows',sum(r['rows'] for r in receipts),flush=True)

def nse(day):
    name='BhavCopy_NSE_FO_0_0_0_'+day.replace('-','')+'_F_0000.csv.zip'
    raw=public('https://nsearchives.nseindia.com/content/fo/'+name,name)
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        return [r for r in csv.DictReader(io.StringIO(z.read(z.namelist()[0]).decode('utf-8-sig'))) if r['TckrSymb']=='NIFTY']

def instruments():
    indexes()
    spot=json.loads((STORE/'indexes/NIFTY.json').read_text())['bars'];trading=sorted(set(r[0][:10] for r in spot))
    days=[d for d in trading if str(BEGIN)<=d<=str(END)]
    prev={d:max(t for t in trading if t<d) for d in days};off={};errors={}
    def job(d):
        try:return d,nse(d),None
        except Exception as e:return d,[],str(e)
    with ThreadPoolExecutor(max_workers=4) as pool:
        for d,rows,e in pool.map(job,sorted(set(days)|set(prev.values()))):
            if e:errors[d]=e
            else:off[d]=rows
    save(STORE/'official.json',off)
    plan={}
    for day in days:
        try:
            rows=off[prev[day]]
            expiry=min((r.get('FininstrmActlXpryDt') or r['XpryDt']) for r in rows if r['FinInstrmTp']=='IDO' and (r.get('FininstrmActlXpryDt') or r['XpryDt'])>=day)
            source={r['FinInstrmId']:r for r in rows if r['FinInstrmTp']=='IDO' and (r.get('FininstrmActlXpryDt') or r['XpryDt'])==expiry}
            exact=contracts('NSE_INDEX|Nifty 50',expiry) if expiry<'2026-09-19' else upstox('/v2/option/contract?instrument_key=NSE_INDEX%7CNifty%2050&expiry_date='+expiry)
            chain={}
            for m in exact:
                c=Contract.parse(m);r=source.get(c.key.split('|')[1])
                if r is None:continue
                if c.lot!=int(r['NewBrdLotQty']) or c.strike!=D(r['StrkPric']) or c.side!=r['OptnTp'] or c.expiry!=expiry:raise ValueError('contract metadata conflict')
                chain[c.key]=m
            if not chain:raise ValueError('no prior listed contracts')
            future=min((r for r in rows if r['FinInstrmTp']=='IDF' and r['XpryDt']>=day),key=lambda r:r['XpryDt'])
            exp=future['XpryDt'];key='NSE_FO|'+future['FinInstrmId']
            if exp<'2026-09-19':key+='|'+date.fromisoformat(exp).strftime('%d-%m-%Y')
            plan[day]={'partition':partition(day),'prior_day':prev[day],'expiry':expiry,'expiry_day':expiry==day,'chain':chain,
                'future_key':key,'future_lot':int(future['NewBrdLotQty']),'official':{r['FinInstrmId']:r for r in off[day]}}
        except Exception as e:plan[day]={'partition':partition(day),'error':str(e)}
    save(STORE/'instruments.json',plan)
    print('instrument days',len(plan),'errors',sum('error' in x for x in plan.values()),'official errors',errors,flush=True)

def futures():
    plan=json.loads((STORE/'instruments.json').read_text());jobs={}
    for d,x in plan.items():
        if 'error' not in x:jobs.setdefault(x['future_key'],[]).append(d)
    for key,days in jobs.items():
        f=STORE/'futures'/(hashlib.sha256(key.encode()).hexdigest()+'.json')
        if f.exists():continue
        rows=[];errors=[]
        for start,end in chunks(date.fromisoformat(min(days)),date.fromisoformat(max(days))):
            try:rows+=candles(key,start,end,len(key.split('|'))==3)
            except Exception as e:errors.append(str(e))
        save(f,{'key':key,'bars':sorted(rows),'errors':errors})
        print('future',key,'rows',len(rows),'errors',errors,flush=True)

def outcomes():
    plan=json.loads((STORE/'signals.json').read_text());inst=json.loads((STORE/'instruments.json').read_text());jobs={}
    for day,x in plan.items():
        if 'error' in inst[day]:continue
        chain=[Contract.parse(m) for m in inst[day]['chain'].values()]
        # Include alternate feature reporting-lag signals in the same input plan.
        for sig in list(x['signals'].values())+list(x['lag5_signals'].values())+(list(x['old_signals'].values())+[{'spot':x['anchor']}] if inst[day]['expiry_day'] and x['anchor'] else []):
            for side in ('CE','PE'):
                for c in selected_chain(chain,D(sig['spot']),side):
                    jobs[day,c.key]=(day,c.key,inst[day]['chain'][c.key],inst[day]['official'].get(c.key.split('|')[1]))
    receipt={}
    from research.gauntlet.option_history import plan_ranges,day_path,fetch_range
    pending=[{'contract_key':k,'day':d} for d,k in jobs if not option_file(d,k).exists() and not day_path(k,d).exists()]
    ranges=plan_ranges(pending)
    print('exact option day requests',len(jobs),'batched missing requests',len(ranges),flush=True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        fs=[pool.submit(fetch_range,r) for r in ranges]
        for i,f in enumerate(as_completed(fs),1):
            try:f.result()
            except Exception as e:print('range request error',str(e),flush=True)
            if i%25==0:print('range requests completed',i,'/',len(fs),flush=True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        fs={pool.submit(fetch,*j):k for k,j in jobs.items() if j[3] is not None}
        for i,f in enumerate(as_completed(fs),1):
            day,key=fs[f];receipt[day+' '+key]=f.result()
            if i%40==0 or i==len(fs):
                save(STORE/'options_download.json',receipt)
                print('option outcomes',i,'/',len(fs),'nonreconciled',sum(r['status']!='RECONCILED' for r in receipt.values()),flush=True)
    save(STORE/'option_jobs.json',[{'day':d,'key':k} for d,k in jobs])

def market():
    inst=json.loads((STORE/'instruments.json').read_text());receipts=[]
    for day,x in inst.items():
        if 'error' in x:continue
        for endpoint in ('pcr','max-pain'):
            path=f'/v2/market/{endpoint}?instrument_key=NSE_INDEX%7CNifty%2050&expiry={x["expiry"]}&date={day}&bucket_interval=5'
            r=request('upstox',path);receipts.append({'day':day,'endpoint':endpoint,'status':r['status'],'insights':len((r.get('body',{}).get('data') or {}).get('insights',[]))})
            time.sleep(1.05)
        if len(receipts)%20==0:save(STORE/'market_download.json',receipts);print('market history',len(receipts),'/',len(inst)*2,flush=True)
    for start in ('2026-04-01','2026-05-01','2026-06-01','2026-07-01','2026-08-01','2026-09-01','2026-09-18'):
        for endpoint,kind in [('fii','NSE_FO%7CINDEX_FUTURES'),('dii','NSE_EQ%7CCASH')]:
            r=request('upstox',f'/v2/market/{endpoint}?data_type={kind}&interval=1D&from={start}')
            print('institutional',endpoint,start,r['status'],flush=True);time.sleep(1.05)
    save(STORE/'market_download.json',receipts)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['indexes','dhan','instruments','futures','outcomes','market']);a=p.parse_args();globals()[a.stage]()
