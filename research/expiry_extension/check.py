import argparse,hashlib,json
from concurrent.futures import ThreadPoolExecutor
from datetime import date,datetime,timedelta,timezone
from pathlib import Path
from research.gauntlet.data import CACHE,save,candles,contracts
from research.gauntlet.core import Bar,Contract,D
from research.expiry.collect import official,selected_chain,partition,STORE,fetch,option_file
from research.expiry.signals import spot_signals
from research.expiry.replay import run,dataset,digest,RESULTS

EXT=STORE/'extension'
OUT=RESULTS/'extension'

def registration():
    save(OUT/'registration.json',{'created_at':datetime.now(timezone.utc).isoformat(),'base_source_hash':digest(),
        'extension_source_hash':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'protocol_hash':hashlib.sha256(Path(__file__).with_name('PROTOCOL.md').read_bytes()).hexdigest(),
        'period':'2024-10-01/2025-09-30','selected_after_original_results':True,'changed_strategy_parameters':False})

def collect():
    registration()
    available=json.loads((STORE/'available_expiries.json').read_text());days=[d for d in available if '2024-10-01'<=d<='2025-09-30']
    f=EXT/'spot.json'
    if not f.exists():
        rows=[];at=date(2024,9,27)
        while at<=date(2025,9,30):
            end=min(at+timedelta(days=27),date(2025,9,30))
            rows+=candles('NSE_INDEX|Nifty 50',str(at),str(end));at=end+timedelta(days=1)
        by={}
        for r in rows:
            if r[0] in by and by[r[0]]!=r:raise ValueError('conflicting spot')
            by[r[0]]=r
        save(f,sorted(by.values()))
    spot=json.loads(f.read_text());trading=sorted(set(r[0][:10] for r in spot));plan={}
    for day in days:
        bars=[Bar.parse(r) for r in spot if r[0][:10]==day]
        sig,gap,anchor=spot_signals(bars,day)
        plan[day]={'partition':'extension','signal':sig.get('TREND1445'),'gaps':[g for g in gap if g.startswith('TREND1445:')]}
    # Complete denominator first; no option returns inspected to choose dates.
    save(EXT/'plan.json',plan)
    jobs=[]
    for day,x in plan.items():
        if not x['signal']:continue
        try:
            prev=max(d for d in trading if d<day)
            prior={r['FinInstrmId']:r for r in official(prev) if (r.get('FininstrmActlXpryDt') or r['XpryDt'])==day}
            end={r['FinInstrmId']:r for r in official(day)};raw={};chain=[]
            for m in contracts('NSE_INDEX|Nifty 50',day):
                c=Contract.parse(m);r=prior.get(c.key.split('|')[1])
                if r is None:continue
                if c.lot!=int(r['NewBrdLotQty']) or c.strike!=D(r['StrkPric']) or c.side!=r['OptnTp'] or c.expiry!=day:raise ValueError('metadata mismatch')
                raw[c.key]=m;chain.append(c)
            needed={}
            for side in ('CE','PE'):
                for c in selected_chain(chain,D(x['signal']['spot']),side):needed[c.key]=raw[c.key]
            if len(needed)<8:raise ValueError('missing ATM/outward contracts')
            x['contracts']=needed;x['prior_day']=prev
            for k,m in needed.items():jobs.append((day,k,m,end[k.split('|')[1]]))
        except Exception as e:x['error']=str(e)
    save(EXT/'plan.json',plan)
    print('extension denominator',len(days),'expiries','signals',sum(bool(x['signal']) for x in plan.values()),'contract days',len(jobs),flush=True)
    receipts={}
    with ThreadPoolExecutor(max_workers=4) as pool:
        for j,r in zip(jobs,pool.map(lambda j:fetch(*j),jobs)):
            receipts[j[0]+' '+j[1]]=r;print('extension collected',len(receipts),'/',len(jobs),r['status'],flush=True)
    save(EXT/'download.json',receipts)

def inputs(quality):
    p=json.loads((EXT/'plan.json').read_text());days={};hashes=[]
    for day,x in p.items():
        if 'error' in x:days[day]=x;continue
        d={'partition':'extension','signals':{'TREND1445':x['signal']} if x['signal'] else {},'gaps':x['gaps'],'chain':[],'bars':{},'errors':{}}
        for k,m in x.get('contracts',{}).items():
            d['chain'].append(Contract.parse(m));f=option_file(day,k)
            if not f.exists():d['errors'][k]='UNKNOWN_REQUEST';continue
            raw=json.loads(f.read_text());hashes.append(hashlib.sha256(f.read_bytes()).hexdigest())
            if raw['key']!=k or raw['day']!=day:raise ValueError('identity mismatch')
            if quality=='strict' and raw['audit']['status']!='RECONCILED':d['errors'][k]=raw['audit']['status']
            d['bars'][k]=[Bar.parse(r) for r in raw['bars']]
        days[day]=d
    dh=hashlib.sha256(((EXT/'plan.json').read_text()+hashlib.sha256((EXT/'spot.json').read_bytes()).hexdigest()+''.join(hashes)).encode()).hexdigest()
    return days,dh

def replay():
    records=[];controls=[]
    for quality in ('strict','reported'):
        days,dh=inputs(quality);original,original_hash=dataset(quality)
        for period,all_days in [('extension',days),('all',days|original)]:
            for style in ('TARGET','TRAIL'):
                base=run(all_days,'TREND1445',style,period)
                for delay,adv,label in [(1,True,'primary'),(2,True,'delay2'),(3,True,'delay3'),(1,False,'open_plus_1pct')]:
                    r=run(all_days,'TREND1445',style,period,delay,adv);r.update(quality=quality,scenario=label);records.append(r)
                r=run(all_days,'TREND1445',style,period,skip=base['best_trade_day']);r.update(quality=quality,scenario='delete_best');records.append(r)
                print('extension result',period,quality,style,base['final_bankroll'],base['counts'],flush=True)
                if quality=='reported':
                    vals=[]
                    for seed in range(999):
                        r=run(all_days,'TREND1445',style,period,seed=130260920+seed)
                        vals.append(r['final_bankroll'])
                    pv=None if base['final_bankroll'] is None or None in vals else (1+sum(D(v)>=D(base['final_bankroll']) for v in vals))/1000
                    controls.append({'period':period,'strategy':base['strategy'],'p_conditional':pv,'twelve_trial_bound':None if pv is None else min(1,12*pv),'controls':vals})
    save(OUT/'results.json',{'source_hash':digest(),'extension_source_hash':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'data_hash':dh,'original_data_hash':original_hash,'runs':records,'noise':controls})

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['collect','replay']);a=p.parse_args();globals()[a.stage]()
