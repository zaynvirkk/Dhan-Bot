"""Exact NIFTY expiry data with prior-session universe and volume receipts."""
import argparse,csv,hashlib,io,json,zipfile
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import date,timedelta
from pathlib import Path
from research.gauntlet.data import CACHE,candles,contracts,public,save
from research.gauntlet.core import Bar,Contract,D
from .signals import spot_signals

STORE=CACHE/'expiry_research'

def partition(day):
    if '2026-07-20'<=day<='2026-09-18':return 'development'
    if '2026-04-01'<=day<='2026-06-30':return 'recent_validation'
    if '2025-10-01'<=day<='2026-03-31':return 'older_validation'
    return None

def official(day):
    name='BhavCopy_NSE_FO_0_0_0_'+day.replace('-','')+'_F_0000.csv.zip'
    raw=public('https://nsearchives.nseindia.com/content/fo/'+name,name)
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        return [r for r in csv.DictReader(io.StringIO(z.read(z.namelist()[0]).decode('utf-8-sig'))) if r['TckrSymb']=='NIFTY' and r['FinInstrmTp']=='IDO']

def setup():
    all_exp=json.loads((STORE/'available_expiries.json').read_text())
    days=[d for d in all_exp if partition(d)]
    file=STORE/'spot.json'
    if not file.exists():
        rows=[];at=date(2025,9,29)
        while at<=date(2026,9,18):
            until=min(at+timedelta(days=27),date(2026,9,18))
            rows.extend(candles('NSE_INDEX|Nifty 50',str(at),str(until)))
            at=until+timedelta(days=1)
        by={}
        for r in rows:
            if r[0] in by and by[r[0]]!=r:raise ValueError('conflicting spot row')
            by[r[0]]=r
        save(file,sorted(by.values()))
    spot=json.loads(file.read_text());trading_days=sorted(set(r[0][:10] for r in spot))
    needed=set(days)|{max(t for t in trading_days if t<d) for d in days}
    def pull(d):
        try:return d,official(d),None
        except Exception as e:return d,[],str(e)
    records={};errors={}
    with ThreadPoolExecutor(max_workers=4) as pool:
        for d,rows,e in pool.map(pull,sorted(needed)):
            if e:errors[d]=e
            else:records[d]=rows
    save(STORE/'official.json',records)
    save(STORE/'calendar.json',{'days':days,'previous':{d:max(t for t in trading_days if t<d) for d in days},'errors':errors})
    print('setup',len(days),'expiries',len(records),'official days','errors',errors,flush=True)

def selected_chain(chain,spot,side):
    rows=sorted([c for c in chain if c.side==side],key=lambda c:c.strike)
    if not rows:return []
    atm=min(rows,key=lambda c:(abs(c.strike-D(str(spot))),c.strike)).strike
    return sorted([c for c in rows if (c.strike>=atm if side=='CE' else c.strike<=atm)],key=lambda c:abs(c.strike-atm))[:4]

def plan():
    cal=json.loads((STORE/'calendar.json').read_text()); off=json.loads((STORE/'official.json').read_text())
    spot=json.loads((STORE/'spot.json').read_text());out={}
    for day in cal['days']:
        if day in out:continue
        try:
            source={r['FinInstrmId']:r for r in off[cal['previous'][day]] if (r.get('FininstrmActlXpryDt') or r['XpryDt'])==day}
            exact=contracts('NSE_INDEX|Nifty 50',day)
            chain=[]; raw={}
            for m in exact:
                k=m['instrument_key'];r=source.get(k.split('|')[1])
                if r is None:continue
                c=Contract.parse(m)
                if c.lot!=int(r['NewBrdLotQty']) or c.strike!=D(r['StrkPric']) or c.side!=r['OptnTp'] or c.expiry!=day or not c.index:raise ValueError('metadata mismatch')
                chain.append(c);raw[k]=m
            if not chain:raise ValueError('no verified contracts')
            bars=[Bar.parse(r) for r in spot if r[0][:10]==day]
            sigs,gaps,anchor=spot_signals(bars,day)
            if anchor is None:raise ValueError('missing 14:45 anchor')
            needed={}
            for s in list(sigs.values())+[{'spot':str(anchor)}]:
                for side in ('CE','PE'):
                    for c in selected_chain(chain,s['spot'],side):needed[c.key]=raw[c.key]
            out[day]={'signals':sigs,'gaps':gaps,'anchor':str(anchor),'contracts':needed,'partition':partition(day),
                      'official':{r['FinInstrmId']:r for r in off[day]},'prior_day':cal['previous'][day]}
        except Exception as e:out[day]={'error':str(e),'partition':partition(day)}
        print('planned',day,len(out[day].get('contracts',{})),'contracts',out[day].get('error',''),flush=True)
    save(STORE/'plan.json',out)
    print('contract days',sum(len(x.get('contracts',{})) for x in out.values()),flush=True)

def option_file(day,key):
    return STORE/'options'/day/(hashlib.sha256(key.encode()).hexdigest()+'.json')

def fetch(day,key,meta,record):
    file=option_file(day,key)
    if file.exists():return json.loads(file.read_text())['audit']
    from research.gauntlet.contracts import instrument_bars
    try:
        rows=instrument_bars(key,day)
        by={}
        for r in rows:
            Bar.parse(r)
            if r[0] in by:raise ValueError('duplicate option candle')
            if r[0][:10]!=day:raise ValueError('wrong option date')
            by[r[0]]=r
        expected=int(record['TtlTradgVol'])*int(record['NewBrdLotQty'])
        actual=sum(int(r[5]) for r in rows)
        audit={'status':'RECONCILED' if expected==actual else 'UNKNOWN_VOLUME_MISMATCH','units':actual,'official_units':expected}
        save(file,{'key':key,'day':day,'metadata':meta,'audit':audit,'bars':sorted(rows),'hash':hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest()})
        return audit
    except Exception as e:
        return {'status':'UNKNOWN_REQUEST','error':str(e)}

def download():
    plan=json.loads((STORE/'plan.json').read_text());jobs=[];receipt={}
    for day,x in plan.items():
        for k,m in x.get('contracts',{}).items():jobs.append((day,k,m,x['official'][k.split('|')[1]]))
    with ThreadPoolExecutor(max_workers=4) as pool:
        fs={pool.submit(fetch,*j):(j[0],j[1]) for j in jobs}
        for i,f in enumerate(as_completed(fs),1):
            d,k=fs[f];receipt[d+' '+k]=f.result()
            if i%25==0 or i==len(jobs):
                save(STORE/'download.json',receipt)
                print('download',i,'/',len(jobs),'unresolved',sum(x['status']!='RECONCILED' for x in receipt.values()),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['setup','plan','download']);a=p.parse_args();globals()[a.stage]()
