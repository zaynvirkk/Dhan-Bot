"""Frozen next hypotheses; all signal construction precedes option outcomes."""
import argparse,hashlib,json
from collections import Counter
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timedelta,timezone
from pathlib import Path
from statistics import median

from research.gauntlet.core import Bar,Contract,D
from research.gauntlet.data import CACHE,save
from research.expiry.collect import selected_chain,option_file,fetch
from research.expiry.signals import stamp,signal
from research.expiry.replay import run
from research.multifeature.providers import STORE as PREVIOUS
from research.multifeature.signals import rolling_map,mapped,Missing,at_bar,ret,confirms,option_value
from research.multifeature.quality import tape_issues

STORE=CACHE/'readiness';OUT=Path(__file__).resolve().parents[1]/'results/readiness'
NAMES=('FAILED_ORB','VWAP_RECLAIM','COMPRESSION_BREAK','PRIOR_OI_WALL')
STRATEGIES=tuple(scope+'_'+name for scope in ('EXPIRY','ORDINARY') for name in NAMES)

def digest():
    root=Path(__file__).resolve().parents[2]
    paths=list(Path(__file__).parent.glob('*.py'))+[Path(__file__).with_name('PROTOCOL.md')]
    paths+=list((root/'research/expiry').glob('*.py'))+list((root/'research/multifeature').glob('*.py'))
    paths+=[root/'research/gauntlet/core.py',root/'dhan_cas_bot/risk.py']
    return hashlib.sha256(b''.join(str(p.relative_to(root)).encode()+p.read_bytes() for p in sorted(paths))).hexdigest()

def vwap_series(future,day):
    at=stamp(day,'09:16');end=stamp(day,'15:10');total=D(0);volume=0;out={}
    while at<=end:
        b=future.get(at)
        if b is None:break
        total+=(b.high+b.low+b.close)/3*b.volume;volume+=b.volume
        if volume:out[at]=total/volume
        at+=timedelta(minutes=1)
    return out

def scan(day,spot,future,options,prior,expiry):
    sigs={};gaps={};walls={};broken=None;vw=vwap_series(future,day)
    try:
        opening=[at_bar(spot,stamp(day,'09:16')+timedelta(minutes=i)) for i in range(30)]
        hi=max(b.high for b in opening);lo=min(b.low for b in opening)
    except Missing:gaps['FAILED_ORB']='MISSING_OPENING_RANGE';hi=lo=D(0)
    try:
        anchor=at_bar(spot,stamp(day,'09:30')).close
        for side in ('CE','PE'):
            rows=[r for r in prior if r['FinInstrmTp']=='IDO' and r['OptnTp']==side and (r.get('FininstrmActlXpryDt') or r['XpryDt'])==expiry and abs(D(r['StrkPric'])-anchor)<=200]
            if not rows:raise Missing('MISSING_PRIOR_WALL')
            chosen=min(rows,key=lambda r:(-int(r['OpnIntrst']),D(r['StrkPric'])))
            if int(chosen['OpnIntrst'])<=0:raise Missing('ZERO_PRIOR_WALL_OI')
            walls[side]=D(chosen['StrkPric'])
    except Missing as e:gaps['PRIOR_OI_WALL']=str(e)
    def volume(at):
        recent=sum(at_bar(future,at-timedelta(minutes=i)).volume for i in range(3))
        base=median(at_bar(future,at-timedelta(minutes=i)).volume for i in range(3,23))
        if base<=0:raise Missing('ZERO_FUTURE_VOLUME_BASE')
        return recent>=base*6,{'volume_ratio':recent/(base*3)}
    # Opening-range state may be formed before the allowed entry time.
    for minutes in range(587,911):
        at=stamp(day,f'{minutes//60:02d}:{minutes%60:02d}')
        if broken is None and 'FAILED_ORB' not in gaps:
            try:
                closes=[at_bar(spot,at-timedelta(minutes=i)).close for i in range(3)]
                if all(c>=hi*D('1.0005') for c in closes):broken=(1,at)
                elif all(c<=lo*D('.9995') for c in closes):broken=(-1,at)
            except Missing:gaps['FAILED_ORB']='MISSING_BREAK_SEQUENCE'
        if minutes<600:continue
        def failed():
            if not broken or at<=broken[1]:return None,{}
            closes=[at_bar(spot,at-timedelta(minutes=i)).close for i in (1,0)]
            if not all(lo<=c<=hi for c in closes):return None,{}
            direction=-broken[0]
            if not confirms(future,at,direction):return None,{}
            ok,detail=volume(at);detail.update(first_break_at=broken[1].isoformat(),range_high=str(hi),range_low=str(lo))
            return ('CE' if direction>0 else 'PE') if ok else None,detail
        def reclaim():
            times=[at-timedelta(minutes=i) for i in range(16,1,-1)]
            if any(t not in vw for t in times+[at-timedelta(minutes=1),at]):raise Missing('MISSING_SESSION_VWAP')
            differences=[at_bar(future,t).close-vw[t] for t in times]
            direction=1 if all(d<0 for d in differences) else -1 if all(d>0 for d in differences) else 0
            if not direction:return None,{}
            if not all(direction*(at_bar(future,t).close-vw[t])>0 for t in (at-timedelta(minutes=1),at)):return None,{}
            if not confirms(spot,at,direction):return None,{}
            ok,detail=volume(at);detail['vwap']=str(vw[at])
            return ('CE' if direction>0 else 'PE') if ok else None,detail
        def compression():
            base=[at_bar(spot,at-timedelta(minutes=i)) for i in range(3,33)]
            high=max(b.high for b in base);low=min(b.low for b in base);middle=(high+low)/2
            if (high-low)/middle>D('.001'):return None,{}
            last=[at_bar(spot,at-timedelta(minutes=i)).close for i in range(3)]
            direction=1 if all(c>=high*D('1.0002') for c in last) else -1 if all(c<=low*D('.9998') for c in last) else 0
            if not direction or direction*ret(future,at,3)<=0:return None,{}
            ok,detail=volume(at);detail.update(compression_high=str(high),compression_low=str(low))
            return ('CE' if direction>0 else 'PE') if ok else None,detail
        def wall():
            closes=[at_bar(spot,at-timedelta(minutes=i)).close for i in (2,1,0)]
            for side,direction in (('CE',1),('PE',-1)):
                k=walls[side]
                if not (direction*(closes[0]-k)<=0 and all(direction*(c-k)>0 for c in closes[1:])):continue
                if direction*ret(future,at,3)<=0:continue
                current=option_value(options,at,side,k);old=option_value(options,at-timedelta(minutes=3),side,k)
                if old[1]<=0:raise Missing('MISSING_PRIOR_OPTION_OI')
                if current[1]/old[1]<=.92 and current[0]/old[0]>=1.25:
                    return side,{'prior_oi_wall':str(k),'oi_change':current[1]/old[1]-1,'premium_change':current[0]/old[0]-1}
            return None,{}
        for name,fn in [('FAILED_ORB',failed),('VWAP_RECLAIM',reclaim),('COMPRESSION_BREAK',compression),('PRIOR_OI_WALL',wall)]:
            if name in sigs or name in gaps:continue
            try:
                side,detail=fn()
                if side:sigs[name]=signal(name,at,side,at_bar(spot,at).close,detail)
            except Missing as e:gaps[name]=str(e)+':'+at.isoformat()
    return sigs,[k+':'+v for k,v in gaps.items()]

def prepare():
    registration=OUT/'registration.json'
    if not registration.exists():save(registration,{'at':datetime.now(timezone.utc).isoformat(),'protocol_hash':hashlib.sha256(Path(__file__).with_name('PROTOCOL.md').read_bytes()).hexdigest(),'variants':16,'minimum_trials_corrected':80,'retrospective':True})
    inst=json.loads((PREVIOUS/'instruments.json').read_text());official=json.loads((PREVIOUS/'official.json').read_text())
    spot=mapped(json.loads((PREVIOUS/'indexes/NIFTY.json').read_text())['bars']);future={}
    for f in (PREVIOUS/'futures').glob('*.json'):
        raw=json.loads(f.read_text());future[raw['key']]=mapped(raw['bars'])
    options=rolling_map();plan={};jobs={};counts=Counter()
    for day,x in sorted(inst.items()):
        if 'error' in x:plan[day]=x;continue
        sig,gaps=scan(day,spot,future[x['future_key']],options,official[x['prior_day']],x['expiry'])
        scope='EXPIRY' if x['expiry_day'] else 'ORDINARY'
        sig={scope+'_'+n:dict(s,name=scope+'_'+n) for n,s in sig.items()};gaps=[scope+'_'+g for g in gaps]
        plan[day]={'partition':x['partition'],'expiry_day':x['expiry_day'],'signals':sig,'gaps':gaps}
        chain=[Contract.parse(m) for m in x['chain'].values()]
        for n,s in sig.items():
            counts[n]+=1
            for side in ('CE','PE'):
                for c in selected_chain(chain,D(s['spot']),side):jobs[day,c.key]={'day':day,'key':c.key}
    save(STORE/'signals.json',plan);save(STORE/'option_jobs.json',list(jobs.values()))
    print('first signals',dict(counts),'exact contract-days',len(jobs),'gaps',sum(len(x.get('gaps',[])) for x in plan.values()),flush=True)

def collect():
    inst=json.loads((PREVIOUS/'instruments.json').read_text());jobs=json.loads((STORE/'option_jobs.json').read_text())
    from research.gauntlet.option_history import plan_ranges,day_path,fetch_range
    pending=[{'contract_key':j['key'],'day':j['day']} for j in jobs if not option_file(j['day'],j['key']).exists() and not day_path(j['key'],j['day']).exists()]
    ranges=plan_ranges(pending);print('missing batched option requests',len(ranges),flush=True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        for i,f in enumerate(as_completed([pool.submit(fetch_range,r) for r in ranges]),1):
            f.result()
            if i%25==0:print('requests',i,'/',len(ranges),flush=True)
    receipts={}
    for j in jobs:
        d=j['day'];k=j['key'];x=inst[d];record=x['official'].get(k.split('|')[1])
        receipts[d+' '+k]=fetch(d,k,x['chain'][k],record) if record else {'status':'UNKNOWN_OFFICIAL_RECORD'}
    save(STORE/'collection.json',receipts);print('audits',dict(Counter(r['status'] for r in receipts.values())),flush=True)

def inputs(quality='reported'):
    inst=json.loads((PREVIOUS/'instruments.json').read_text());plan=json.loads((STORE/'signals.json').read_text())
    jobs=json.loads((STORE/'option_jobs.json').read_text());by={};hashes=[];audits=Counter()
    paths=[STORE/'signals.json',STORE/'option_jobs.json',PREVIOUS/'instruments.json',PREVIOUS/'official.json',PREVIOUS/'indexes/NIFTY.json']
    paths+=sorted((PREVIOUS/'futures').glob('*.json'))+sorted((PREVIOUS/'api').glob('*.json'))
    for j in jobs:by.setdefault(j['day'],[]).append(j['key'])
    days={}
    for day,row in plan.items():
        if 'error' in row:days[day]=row;continue
        x=inst[day];bars={};errors={}
        for k in by.get(day,[]):
            f=option_file(day,k)
            if not f.exists():errors[k]='UNKNOWN_REQUEST';continue
            paths.append(f);raw=json.loads(f.read_text());assert raw['key']==k and raw['day']==day
            bars[k]=[Bar.parse(r) for r in raw['bars']];issues=tape_issues(raw,bars[k]);audits[raw['audit']['status']]+=1
            audits.update(i for i in issues if i!=raw['audit']['status'])
            if quality=='strict' and issues:errors[k]=';'.join(issues)
        days[day]={**row,'chain':[Contract.parse(m) for m in x['chain'].values()],'bars':bars,'errors':errors}
    for f in paths:hashes.append(hashlib.sha256(f.read_bytes()).hexdigest())
    return days,hashlib.sha256(''.join(hashes).encode()).hexdigest(),dict(audits)

def replay():
    sh=digest()
    for quality in ('reported','strict'):
        days,dh,audits=inputs(quality);runs=[]
        for period in ('earlier','recent'):
            for name in STRATEGIES:
                for style in ('TARGET','TRAIL'):
                    base=run(days,name,style,period);base.update(scenario='primary',quality=quality);runs.append(base)
                    for delay,adverse,label in [(2,True,'delay2'),(3,True,'delay3'),(1,False,'open_plus_1pct')]:
                        r=run(days,name,style,period,delay,adverse);r.update(scenario=label,quality=quality);runs.append(r)
                    r=run(days,name,style,period,skip=base['best_trade_day']);r.update(scenario='delete_best',quality=quality);runs.append(r)
                    print(quality,period,name,style,base['final_bankroll'],base['counts'].get('trades',0),base['unknown'],flush=True)
        assert sh==digest(),'source drift'
        save(OUT/(quality+'.json'),{'source_hash':sh,'data_hash':dh,'runs':runs,'audits':audits,'calendar_days_per_window':90})

def noise():
    sh=digest();days,dh,_=inputs();doc=json.loads((OUT/'reported.json').read_text())
    assert doc['source_hash']==sh and doc['data_hash']==dh
    baseline={(r['period'],r['strategy'],r['scenario']):r for r in doc['runs']};rows=[]
    for period in ('earlier','recent'):
        for name in STRATEGIES:
            for style in ('TARGET','TRAIL'):
                key=name+'_'+style;base=baseline[period,key,'primary'];controls=[]
                if base['final_bankroll'] is not None and base['counts'].get('signals',0):
                    robust=all(baseline[p,key,s]['final_bankroll'] is not None and D(baseline[p,key,s]['final_bankroll'])>D('9411.18') for p in ('earlier','recent') for s in ('primary','delete_best'))
                    for seed in range(3999 if robust else 499):controls.append(run(days,name,style,period,seed=2026092100+seed)['final_bankroll'])
                p=None if not controls or None in controls else (1+sum(D(c)>=D(base['final_bankroll']) for c in controls))/(len(controls)+1)
                rows.append({'period':period,'strategy':key,'controls':controls,'p':p,'adjusted_p':None})
                print('random directions',period,key,len(controls),p,flush=True)
    for period in ('earlier','recent'):
        rank=sorted([r for r in rows if r['period']==period and r['p'] is not None],key=lambda r:r['p']);previous=0.
        for i,r in enumerate(rank):previous=max(previous,min(1.,(80-i)*r['p']));r['adjusted_p']=previous
    assert sh==digest(),'source drift'
    save(OUT/'noise.json',{'source_hash':sh,'data_hash':dh,'rows':rows,'minimum_trial_count':80})

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['prepare','collect','replay','noise']);a=p.parse_args();globals()[a.stage]()
