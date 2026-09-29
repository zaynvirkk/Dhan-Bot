"""Published-session ranks and bounded historical market reads."""
import argparse,csv,hashlib,io,json,zipfile
from collections import Counter,defaultdict
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import date,timedelta
from decimal import Decimal as D
from statistics import median,pstdev
from functools import lru_cache
from research.gauntlet.data import ROOT,CACHE,save,public,candles
from research.gauntlet.core import Bar
from research.expiry.signals import stamp
STORE=CACHE/'broader';OUT=ROOT/'research/results/broader'
STOCK=('MOMENTUM20','SMOOTH_MOMENTUM','TREND_DIP','VOLUME_BREAKOUT','OI_SQUEEZE','OI_BUILD')
NIFTY=('UNCONDITIONAL','SELLOFF_REBOUND','DAY_CONTINUATION','TREND_ALIGNMENT')

def known_late_open(symbol,day,at):
    # NSE/CMTR/73856, published 22 April: VEDL is in special pre-open until
    # 10:00 on 30 April. The frozen 09:30 / 15 completed-minute rule cannot fire.
    return (symbol=='VEDL' and day=='2026-04-30' and
            stamp('2026-04-23','00:00')<at<stamp(day,'10:00'))

def part(day):
    if '2026-03-23'<=day<='2026-06-20':return 'earlier'
    if '2026-06-21'<=day<='2026-09-18':return 'recent'
    return None

def raw_rows(path):
    with zipfile.ZipFile(path) as z:return list(csv.DictReader(io.StringIO(z.read(z.namelist()[0]).decode('utf-8-sig'))))

@lru_cache(maxsize=1)
def calendar():
    return sorted({r[0][:10] for r in json.loads((CACHE/'expiry_research/spot.json').read_text()) if '2026-02-16'<=r[0][:10]<='2026-09-18'})

def archives():
    days=calendar();(STORE/'daily').mkdir(parents=True,exist_ok=True)
    def fetch(day):
        dest=STORE/'daily'/f'{day}.json'
        if dest.exists():return day,'CACHED'
        records={};hashes={}
        for segment in ('FO','CM'):
            name=f'BhavCopy_NSE_{segment}_0_0_0_{day.replace("-", "")}_F_0000.csv.zip'
            file=CACHE/'public'/name
            if not file.exists():
                old=CACHE/'event90/public'/name
                if old.exists():file=old
                else:public('https://nsearchives.nseindia.com/content/'+segment.lower()+'/'+name,name)
            rows=raw_rows(file);hashes[segment]=hashlib.sha256(file.read_bytes()).hexdigest()
            if not rows or {r['TradDt'] for r in rows}!={day}:raise ValueError('archive date mismatch '+day)
            records[segment]=rows
        universe={r['TckrSymb'] for r in records['FO'] if r['FinInstrmTp'] in ('STF','STO')}
        cash={r['TckrSymb']:{k:r[k] for k in ('ISIN','OpnPric','HghPric','LwPric','ClsPric','PrvsClsgPric','TtlTradgVol','TtlTrfVal')} for r in records['CM'] if r['SctySrs']=='EQ'}
        futures={}
        for r in records['FO']:
            if r['FinInstrmTp']=='STF':futures.setdefault(r['TckrSymb'],[]).append({k:r[k] for k in ('FinInstrmId','XpryDt','OpnIntrst','ClsPric')})
        save(dest,{'day':day,'universe':sorted(universe),'cash':cash,'futures':futures,'hashes':hashes})
        return day,'DOWNLOADED'
    results=[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        fs={pool.submit(fetch,d):d for d in days}
        for i,f in enumerate(as_completed(fs),1):
            try:d,s=f.result();results.append({'day':d,'status':s})
            except Exception as e:results.append({'day':fs[f],'status':'UNKNOWN','error':str(e)})
            if i%20==0:print('archives',i,'/',len(days),dict(Counter(r['status'] for r in results)),flush=True)
    save(STORE/'archives.json',results)

def selectors(history,day):
    if any(x['day']>=day for x in history):raise ValueError('future session in ranking input')
    out={n:[] for n in STOCK}
    if len(history)<21:raise ValueError('insufficient warmup')
    previous=history[-1];past=history[-21:]
    for s in previous['universe']:
        rs=[x['cash'].get(s) for x in past]
        if any(r is None for r in rs) or len({r['ISIN'] for r in rs})!=1:continue
        closes=[D(r['ClsPric']) for r in rs]
        if min(closes)<=0 or any(D(r['PrvsClsgPric'])<=0 for r in rs):continue
        if any(abs(closes[i-1]/D(rs[i]['PrvsClsgPric'])-1)>D('.005') for i in range(1,21)):continue
        returns=[float(b/a-1) for a,b in zip(closes,closes[1:])]
        if max(map(abs,returns))>.2:continue
        if median(D(r['TtlTrfVal']) for r in rs[-20:])<D('100000000'):continue
        momentum=closes[-1]/closes[0]-1;last=D(str(returns[-1]));base=median(D(r['TtlTradgVol']) for r in rs[:-1]);vr=D(rs[-1]['TtlTradgVol'])/base if base else D(0)
        details={'symbol':s,'key':'NSE_EQ|'+rs[-1]['ISIN'],'momentum20':str(momentum),'last_return':str(last),'volume_ratio':str(vr),'reference':str(closes[-1])}
        def add(n,score):out[n].append({**details,'score':str(score)})
        if momentum>=D('.10'):
            add('MOMENTUM20',momentum);sd=pstdev(returns)
            if sd:add('SMOOTH_MOMENTUM',momentum/D(str(sd)))
        if momentum>0 and last<=D('-.03'):add('TREND_DIP',-last)
        if closes[-1]>max(D(r['HghPric']) for r in rs[:-1]) and vr>=2:add('VOLUME_BREAKOUT',vr)
        if last>=D('.02') and vr>=2:
            fut=[r for r in previous['futures'].get(s,[]) if r['XpryDt']>=day]
            if fut:
                f=min(fut,key=lambda r:r['XpryDt']);old=next((r for r in history[-2]['futures'].get(s,[]) if r['FinInstrmId']==f['FinInstrmId']),None)
                if old and int(old['OpnIntrst'])>0:
                    change=D(f['OpnIntrst'])/D(old['OpnIntrst'])-1
                    if change<=D('-.05'):add('OI_SQUEEZE',last)
                    if change>=D('.05'):add('OI_BUILD',last)
    return {n:sorted(rs,key=lambda r:(-D(r['score']),r['symbol'])) for n,rs in out.items()}

def rank():
    days=calendar();history=[];out={}
    for d in days:
        if part(d):out[d]={'partition':part(d),'ranks':selectors(history,d)}
        file=STORE/'daily'/f'{d}.json'
        if not file.exists():raise ValueError('UNKNOWN_ARCHIVE:'+d)
        history.append(json.loads(file.read_text()))
    save(STORE/'ranks.json',out)
    print('ranked',len(out),'sessions','signals',dict(Counter(n for x in out.values() for n,rs in x['ranks'].items() if rs)),flush=True)

def stock_history():
    ranks=json.loads((STORE/'ranks.json').read_text());jobs=defaultdict(list)
    for day,x in ranks.items():
        for rs in x['ranks'].values():
            if rs:jobs[rs[0]['key']].append((day,rs[0]['symbol']))
    days=calendar()
    def pull(item):
        key,needed=item;symbol=needed[0][1];file=STORE/'underlying'/(symbol+'.json')
        if file.exists():return symbol,'CACHED'
        end=days[min(len(days)-1,days.index(max(d for d,s in needed))+5)];start=min(d for d,s in needed)
        old=CACHE/'event90/underlying'/(symbol+'.json');rows=json.loads(old.read_text()) if old.exists() else []
        oldkeys=json.loads((CACHE/'event90/keys.json').read_text())
        if oldkeys.get(symbol)!=key:rows=[]
        covered={r[0][:10] for r in rows};missing=[d for d in days if start<=d<=end and d not in covered];blocks=[]
        for d in missing:
            if not blocks or (date.fromisoformat(d)-date.fromisoformat(blocks[-1][0])).days>=28:blocks.append([d])
            else:blocks[-1].append(d)
        for block in blocks:rows+=candles(key,block[0],block[-1])
        by={}
        for r in rows:
            if start<=r[0][:10]<=end:
                Bar.parse(r)
                if r[0] in by and by[r[0]]!=r:raise ValueError('conflicting underlying')
                by[r[0]]=r
        save(file,{'key':key,'bars':sorted(by.values()),'start':start,'end':end});return symbol,'DOWNLOADED'
    results=[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        fs={pool.submit(pull,item):item[0] for item in jobs.items()}
        for i,f in enumerate(as_completed(fs),1):
            try:s,status=f.result();results.append({'symbol':s,'status':status})
            except Exception as e:results.append({'key':fs[f],'status':'UNKNOWN','error':str(e)})
            if i%10==0:print('stocks',i,'/',len(jobs),flush=True)
    save(STORE/'underlying_collection.json',results);print('stocks done',dict(Counter(r['status'] for r in results)),flush=True)

def signals():
    ranks=json.loads((STORE/'ranks.json').read_text());days=calendar();out={}
    spot={b.available:b for b in map(Bar.parse,json.loads((CACHE/'expiry_research/spot.json').read_text()))}
    final={}
    for at,b in sorted(spot.items()):final[at.date().isoformat()]=b
    stocks={}
    for f in (STORE/'underlying').glob('*.json'):
        raw=json.loads(f.read_text());stocks[f.stem]=(raw['key'],{b.available:b for b in map(Bar.parse,raw['bars'])})
    for d,x in ranks.items():
        i=days.index(d);p=x['partition'];last='2026-06-20' if p=='earlier' else '2026-09-18';ss={};errors={};unavailable={}
        for name,rs in x['ranks'].items():
            for mode,h in [('CASH1',1),('CASH5',5),('CALL5',5)]:
                n=name+'_'+mode
                if not rs or i+h>=len(days) or days[i+h]>last:continue
                r=rs[0];raw=stocks.get(r['symbol'])
                if known_late_open(r['symbol'],d,stamp(d,'09:30')):
                    unavailable[n]='KNOWN_SPECIAL_PREOPEN_NSE_CMTR_73856';continue
                if not raw:errors[n]='MISSING_STOCK_HISTORY';continue
                key,bars=raw
                if key!=r['key'] or any(stamp(d,'09:16')+timedelta(minutes=j) not in bars for j in range(15)):
                    errors[n]='MISSING_IDENTITY_OR_OPEN_MINUTES';continue
                at=stamp(d,'09:30');ss[n]={'name':n,'at':at.isoformat(),'day':d,'side':'CE','symbol':r['symbol'],'key':r['key'],
                    'spot':str(bars[at].close),'exit_day':days[i+h],'exit_at':stamp(days[i+h],'15:10').isoformat(),'mode':mode,'rank':r}
        if i+1<len(days) and days[i+1]<=last:
            at=stamp(d,'15:10');op=spot.get(stamp(d,'09:16'));cur=spot.get(at)
            prior=final.get(days[i-1]);old=final.get(days[i-21]) if i>=21 else None
            for n in NIFTY:
                for hhmm in ('09:30','15:10'):
                    name='NIFTY_'+n+'_'+hhmm.replace(':','')
                    if any(b is None for b in (op,cur,prior,old)):errors[name]='MISSING_NIFTY_SIGNAL_BAR';continue
                    ret=cur.close/op.open-1;trend=prior.close/old.close-1;side=None
                    if n=='UNCONDITIONAL':side='CE'
                    elif n=='SELLOFF_REBOUND' and ret<=D('-.0075'):side='CE'
                    elif n=='DAY_CONTINUATION' and abs(ret)>=D('.005'):side='CE' if ret>0 else 'PE'
                    elif n=='TREND_ALIGNMENT' and abs(ret)>=D('.002') and ret*trend>0:side='CE' if ret>0 else 'PE'
                    if side:ss[name]={'name':name,'at':at.isoformat(),'day':d,'side':side,'symbol':'NIFTY','key':'NSE_INDEX|Nifty 50',
                        'spot':str(cur.close),'exit_day':days[i+1],'exit_at':stamp(days[i+1],hhmm).isoformat(),'mode':'INDEX','detail':{'session_return':str(ret),'trend20':str(trend)}}
        out[d]={'partition':p,'signals':ss,'errors':errors,'unavailable':unavailable}
    save(STORE/'signals.json',out);print('signals',dict(Counter(n for x in out.values() for n in x['signals'])),'errors',dict(Counter(n for x in out.values() for n in x['errors'])),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['archives','rank','stock_history','signals']);a=p.parse_args();globals()[a.stage]()
