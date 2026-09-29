"""Pre-period fitted lead/lag probes. No test-period coefficient fitting.

These explicit sub-universes operationalize two broad, previously unspecified
hypotheses: GIFT -> NIFTY and bank/IT index -> disclosed bank/IT constituents.
They are discovery variants, not a claim to have covered every possible link.
"""
from collections import defaultdict
from datetime import datetime,timedelta
from decimal import Decimal as D
from statistics import mean,pstdev
import json
from .core import Bar
from .data import CACHE,save
from .collect import START,END

def load(symbol):
    return sorted([Bar.parse(r) for r in json.loads((CACHE/'underlying'/f'{symbol}.json').read_text())],key=lambda b:b.start)

def pair_rows(lead,target,lag_minutes):
    l={b.start:b for b in lead};t={b.start:b for b in target};out=[]
    for b in target:
        minute=b.available.hour*60+b.available.minute
        if not 565<=minute<=910:continue
        k=b.start-timedelta(minutes=lag_minutes)
        a=l.get(k);old_l=l.get(k-timedelta(minutes=5));old_t=t.get(b.start-timedelta(minutes=5))
        prev=[t.get(b.start-timedelta(minutes=i)) for i in (2,1,0)]
        if a is None or old_l is None or old_t is None or any(x is None for x in prev):continue
        if old_l.close<=0 or old_t.close<=0:continue
        x=float(a.close/old_l.close-1);y=float(b.close/old_t.close-1)
        out.append((b,x,y,prev,old_t.close,a.available+timedelta(minutes=lag_minutes)))
    return out

def fit(training):
    if len(training)<2000:return None
    xs=[r[1] for r in training];ys=[r[2] for r in training]
    mx=mean(xs);my=mean(ys);var=sum((x-mx)**2 for x in xs)
    if var<=0:return None
    beta=sum((x-mx)*(y-my) for x,y in zip(xs,ys))/var
    intercept=my-beta*mx
    residual=pstdev([y-intercept-beta*x for x,y in zip(xs,ys)])
    if residual<=0 or beta<=0:return None
    return {'beta':beta,'intercept':intercept,'lead_std':pstdev(xs),'residual_std':residual,'training_rows':len(training)}

def scan_pair(engine,symbol,lead,lag):
    rows=pair_rows(load(lead),load(symbol),lag)
    train=[r for r in rows if r[0].start.date()<START]
    model=fit(train)
    if model is None:return [],{'symbol':symbol,'reason':'INSUFFICIENT_PREPERIOD_MODEL'}
    seen=set();signals=[]
    for b,x,y,prev,reference,available in rows:
        day=b.start.date()
        if day<START or day>END or day in seen:continue
        predicted=model['intercept']+model['beta']*x
        direction=1 if predicted>0 else -1
        if abs(x)<3*model['lead_std'] or direction*(predicted-y)<model['residual_std']:continue
        if not all(direction*(q.close-p.close)>0 for p,q in zip(prev,prev[1:])):continue
        if direction*(b.close-reference)<=0:continue
        seen.add(day)
        signals.append({'id':f'{engine}:{symbol}:{b.available.isoformat()}','engine':engine,'symbol':symbol,
            'at':b.available.isoformat(),'side':'CE' if direction>0 else 'PE','spot':str(b.close),
            'reference':str(reference),'extreme':str(b.close),'materiality':'NOT_REQUIRED','futures_confirmation':'NOT_REQUIRED',
            'lead':lead,'lead_available_at':available.isoformat(),'assumed_feed_age_minutes':lag,
            'variant':'GIFT_NIFTY_120S_REFRESH_BOUND' if engine=='CROSS_MARKET_LEAD_LAG' else 'BANK_IT_PREPERIOD_GRAPH'})
    return signals,{'symbol':symbol,'lead':lead,**model,'signals':len(signals)}

def scan():
    # Classification carried in exchange records published BEFORE the test.
    industries={}
    for f in sorted((CACHE/'public').glob('announcements_*.json')):
        if 'receipt' in f.name:continue
        for r in json.loads(f.read_text()):
            if r.get('sort_date','')[:10]>=str(START):continue
            industry=(r.get('smIndustry') or '').lower()
            if r['symbol'] not in industries and ('bank' in industry or industry in ('it - software','computers - software')):
                industries[r['symbol']]='BANKNIFTY' if 'bank' in industry else 'NIFTYIT'
    keys=json.loads((CACHE/'keys.json').read_text())
    pairs=[('CROSS_MARKET_LEAD_LAG','NIFTY','GIFT',2)]+[
        ('SECTOR_SHOCK_LAG',s,lead,0) for s,lead in sorted(industries.items()) if s in keys]
    signals=[];models=[]
    for engine,symbol,lead,lag in pairs:
        s,m=scan_pair(engine,symbol,lead,lag);signals+=s;models.append(m)
        print('leadlag',engine,symbol,'signals',len(s),flush=True)
    save(CACHE/'leadlag_candidates.json',sorted(signals,key=lambda s:(s['at'],s['symbol'])))
    save(CACHE/'leadlag_models.json',{'models':models,'graph':industries,'fit_end':'2026-07-17','all_test_data_held_out_from_fit':True})

if __name__=='__main__':scan()
