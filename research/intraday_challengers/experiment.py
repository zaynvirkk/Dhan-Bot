"""Independent bankroll paths. Uses authenticated historical reads only."""
import argparse
import hashlib
import json
import random
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
from datetime import datetime,timedelta
from math import ceil
from pathlib import Path

from dhan_cas_bot.risk import FeeSchedule
from research.gauntlet.core import Bar,Contract,D,entry,cash_after,tick_down
from research.gauntlet.data import ROOT,CACHE,save
from research.expiry.collect import option_file,fetch,selected_chain
from research.expiry.replay import choose
from research.expiry.signals import stamp
from research.finalsearch.experiment import data
from research.multifeature.providers import STORE as OLD
from research.multifeature.quality import tape_issues
from .signals import NAMES,BENCH,scan

STORE=CACHE/'intraday_challengers'
OUT=ROOT/'research/results/intraday_challengers'
START=D('9411.18')
EXITS={'FAST':(D('1.25'),D('.85'),30),'SWING':(D('1.50'),D('.75'),60),'DOUBLE':(D(2),D('.5'),1000)}

def source_hash():
    paths=list(Path(__file__).parent.glob('*.py'))+[Path(__file__).with_name('PROTOCOL.md')]
    paths += [ROOT/p for p in ('research/gauntlet/core.py','research/expiry/replay.py','research/expiry/fast_order.py',
                               'research/expiry/collect.py','research/finalsearch/experiment.py','research/multifeature/quality.py','dhan_cas_bot/risk.py')]
    return hashlib.sha256(b''.join(str(p.relative_to(ROOT)).encode()+p.read_bytes() for p in sorted(paths))).hexdigest()

def prepare():
    inst,spot=data(); old=json.loads((OLD/'signals.json').read_text());futures={};idx={}
    for p in (OLD/'futures').glob('*.json'):
        raw=json.loads(p.read_text());futures[raw['key']]={b.available:b for b in map(Bar.parse,raw['bars'])}
    for symbol in ('BANK','IT'):
        raw=json.loads((OLD/'indexes'/f'{symbol}.json').read_text());idx[symbol]={b.available:b for b in map(Bar.parse,raw['bars'])}
    plan={};jobs={}
    for day,x in sorted(inst.items()):
        if x.get('expiry_day'):continue
        if 'error' in x:plan[day]=x;continue
        signals,gaps=scan(day,spot,futures.get(x['future_key'],{}),idx['BANK'],idx['IT'],x['prior_day'])
        for n in BENCH:
            if n in old[day]['signals']:signals[n]=old[day]['signals'][n]
            else:
                gap=next((g for g in old[day]['gaps'] if g.startswith(n+':')),None)
                if gap:gaps[n]=gap
        chain=[Contract.parse(v) for v in x['chain'].values()]
        for s in signals.values():
            for side in ('CE','PE'):
                for c in selected_chain(chain,D(s['spot']),side):jobs[day,c.key]={'day':day,'key':c.key}
        plan[day]={'partition':x['partition'],'signals':signals,'gaps':gaps}
    save(STORE/'plan.json',plan);save(STORE/'jobs.json',list(jobs.values()))
    print('sessions',len(plan),'contract-days',len(jobs),'signals',dict(Counter(n for x in plan.values() for n in x.get('signals',{}))),flush=True)

def collect():
    from research.gauntlet.option_history import plan_ranges,day_path,fetch_range
    inst,_=data();jobs=json.loads((STORE/'jobs.json').read_text())
    pending=[{'contract_key':j['key'],'day':j['day']} for j in jobs if not option_file(j['day'],j['key']).exists() and not day_path(j['key'],j['day']).exists()]
    ranges=plan_ranges(pending);print('new requests',len(ranges),flush=True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        for i,f in enumerate(as_completed([pool.submit(fetch_range,r) for r in ranges]),1):
            f.result()
            if i%20==0:print('collected',i,'/',len(ranges),flush=True)
    audit={}
    for j in jobs:
        d,k=j['day'],j['key'];x=inst[d];r=x['official'].get(k.split('|')[1])
        audit[d+' '+k]=fetch(d,k,x['chain'][k],r) if r else {'status':'UNKNOWN_OFFICIAL_RECORD'}
    save(STORE/'collection.json',audit);print('audit',dict(Counter(r['status'] for r in audit.values())),flush=True)

def load():
    inst,_=data();plan=json.loads((STORE/'plan.json').read_text());days={};audit=Counter();paths=[STORE/'plan.json',STORE/'jobs.json',OLD/'instruments.json',OLD/'signals.json',CACHE/'expiry_research/spot.json']
    paths+=list((OLD/'indexes').glob('*.json'))+list((OLD/'futures').glob('*.json'))+list((OLD/'api').glob('*.json'))
    for day,p in plan.items():
        if 'error' in p:days[day]=p;continue
        days[day]={**p,'chain':[Contract.parse(v) for v in inst[day]['chain'].values()],'bars':{},'audit_errors':{},'errors':{}}
    for j in json.loads((STORE/'jobs.json').read_text()):
        d,k=j['day'],j['key'];p=option_file(d,k);x=days[d]
        if not p.exists():x['errors'][k]='UNKNOWN_REQUEST';continue
        paths.append(p);raw=json.loads(p.read_text());assert raw['day']==d and raw['key']==k
        rows=list(map(Bar.parse,raw['bars']));x['bars'][k]=rows
        errors=tape_issues(raw,rows);audit.update(errors or ['RECONCILED'])
        if errors:x['audit_errors'][k]=errors
    digest=hashlib.sha256('\n'.join(str(p.relative_to(ROOT))+hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(set(paths))).encode()).hexdigest()
    return days,digest,dict(audit)

def reserve(order,cash):
    fees=FeeSchedule();qty=order.quantity
    while qty:
        n=ceil(qty/order.contract.freeze);turn=qty*order.limit
        if turn+fees.buy(turn,n)+3*fees.sell(D(0),n)<=cash:return replace(order,quantity=qty)
        qty-=order.contract.lot
    return None

def liquidate(order,fill,bars,style,day,delay=1):
    """A completed close submits a future exit; highs never award profit."""
    mult,loss,minutes=EXITS[style];price=fill['price'];target=price*mult;stop=price*loss
    by={b.start:b for b in bars};at=fill['bar'].start
    scheduled=min(at+timedelta(minutes=minutes),stamp(day,'15:34' if day>='2026-08-03' else '15:24'))
    exit_at=scheduled;reason='TIMED_CLOSE';remaining=order.quantity;parts=[];worst=price
    while at<=exit_at+timedelta(minutes=2):
        b=by.get(at)
        if b is None:return {'status':'UNKNOWN_HOLDING_BAR','at':at.isoformat(),'parts':parts}
        # Entry-bar high/low ordering is unknown; mark diagnostics start later.
        if at>fill['bar'].start:worst=min(worst,b.low)
        if at>=exit_at:
            qty=min(remaining,int(D(b.volume)*D('.05'))//order.contract.lot*order.contract.lot)
            if qty:
                px=tick_down(b.low*D('.99'),order.contract.tick)
                parts.append({'quantity':qty,'price':str(px),'at':at.isoformat()});remaining-=qty
            if not remaining:
                return {'status':'MODELED_EXIT','at':b.available.isoformat(),'price':sum(D(p['price'])*p['quantity'] for p in parts)/order.quantity,
                        'parts':parts,'reason':reason,'worst':worst}
        elif reason=='TIMED_CLOSE' and (b.close<=stop or b.close>=target):
            proposed=b.available+timedelta(minutes=delay)
            if proposed<exit_at:exit_at=proposed;reason='STOP_CLOSE' if b.close<=stop else 'TARGET_CLOSE'
        at+=timedelta(minutes=1)
    return {'status':'UNKNOWN_EXIT_CAPACITY','at':at.isoformat(),'parts':parts,'remaining':remaining}

def run(days,name,style,period,quality='reported',delay=1,adverse=True,skip=None,seed=None):
    cash=START;peak=cash;dd=D(0);counts=Counter();ledger=[];unknown=None;best=None;bestp=D(0);rng=random.Random(seed)
    for day,x in sorted(days.items()):
        if x.get('partition')!=period:continue
        counts['sessions']+=1
        if 'error' in x:unknown=[day,x['error']];break
        sig=x['signals'].get(name)
        if not sig:
            if name in x['gaps']:unknown=[day,x['gaps'][name]];break
            counts['no_signal']+=1;continue
        counts['signals']+=1
        side=sig['side'] if seed is None else rng.choice(['CE','PE'])
        if day==skip:counts['deleted_best']+=1;continue
        # Retrospective quality audit never changes an actual strategy choice.
        view={**x,'errors':x['errors']| (x['audit_errors'] if quality=='strict' else {})}
        view['_snapshots']=x.setdefault('_snapshots',{})
        order,status,trace=choose(view,sig,cash,side)
        row={'day':day,'signal_at':sig['at'],'side':side,'cash_before':str(cash),'status':status,'selection':trace}
        if status.startswith('UNKNOWN'):unknown=[day,status];ledger.append(row);break
        if order:order=reserve(order,cash)
        if not order:counts['no_order']+=1;ledger.append(row);continue
        row.update(contract=order.contract.key,lot=order.contract.lot,quantity=order.quantity,limit=str(order.limit))
        f=entry(order,x['bars'][order.contract.key],delay_bars=delay,adverse=adverse);row['status']=f['status']
        if f['status'].startswith('UNKNOWN'):unknown=[day,f['status']];ledger.append(row);break
        if f['status']!='MODELED_FILL':counts['misses']+=1;ledger.append(row);continue
        cache=x.setdefault('_exits_new',{});key=(order.contract.key,order.quantity,f['time'],f['price'],style,delay)
        if key not in cache:cache[key]=liquidate(order,f,x['bars'][order.contract.key],style,day,delay)
        out=cache[key];row.update(status=out['status'],entry=str(f['price']),entry_at=f['time'])
        if out['status']!='MODELED_EXIT':unknown=[day,out['status']];ledger.append(row);break
        after,fees=cash_after(cash,order,f['price'],out['price'],out['parts']);pnl=after-cash
        if after<0:raise AssertionError('cash reserve failed')
        counts['trades']+=1;counts['wins' if pnl>0 else 'losses']+=1
        if pnl>bestp:bestp=pnl;best=day
        low=cash-order.quantity*f['price']+order.quantity*out['worst']-fees
        dd=max(dd,1-low/peak,1-after/peak);cash=after;peak=max(peak,cash)
        row.update(cash_after=str(cash),pnl=str(pnl),fees=str(fees),exit=str(out['price']),exit_at=out['at'],exit_parts=out['parts'],reason=out['reason'])
        ledger.append(row)
    return {'strategy':name+'_'+style,'period':period,'quality':quality,'delay':delay,'adverse':adverse,
            'final_bankroll':None if unknown else str(cash.quantize(D('.01'))),'resolved_cash':str(cash.quantize(D('.01'))),
            'unknown':unknown,'counts':dict(counts),'model_drawdown':str(dd),'best_trade_day':best,'ledger':ledger}

def evaluate():
    days,datahash,audit=load();runs=[]
    for name in NAMES:
        for style in EXITS:
            for period in ('earlier','recent'):
                base=run(days,name,style,period);base['scenario']='primary';runs.append(base)
                for scenario,kw in [('delay2',{'delay':2}),('delay3',{'delay':3}),('open_plus_1pct',{'adverse':False}),
                                    ('delete_best',{'skip':base['best_trade_day']}),('strict',{'quality':'strict'})]:
                    r=run(days,name,style,period,**kw);r['scenario']=scenario;runs.append(r)
                print(base['strategy'],period,base['final_bankroll'],base['counts'].get('trades',0),base['unknown'],flush=True)
    save(OUT/'results.json',{'source_sha256':source_hash(),'input_sha256':datahash,'audit':audit,'runs':runs})

def controls():
    days,datahash,_=load();raw=json.loads((OUT/'results.json').read_text());answer=[]
    assert raw['source_sha256']==source_hash() and raw['input_sha256']==datahash
    for base in raw['runs']:
        if base['period']!='recent' or base['scenario']!='primary' or base['final_bankroll'] is None or D(base['final_bankroll'])<=D('11908.11'):continue
        name,style=base['strategy'].rsplit('_',1);observed=D(base['final_bankroll']);values=[];unknown=0;records=[]
        for seed in range(999):
            r=run(days,name,style,'recent',seed=seed)
            records.append({'seed':seed,'final_bankroll':r['final_bankroll'],'unknown':r['unknown']})
            if r['unknown']:unknown+=1
            else:values.append(D(r['final_bankroll']))
        exceed=sum(v>=observed for v in values)
        lower=(1+exceed)/1000;upper=(1+exceed+unknown)/1000
        answer.append({'strategy':base['strategy'],'observed':str(observed),'controls':999,'resolved':len(values),'unknown':unknown,'at_least_observed':exceed,
                       'p_lower':lower,'p_upper':upper,'bonferroni_118_upper':min(1,118*upper),'seeds':'0..998','paths':records})
        print('random-side',{k:v for k,v in answer[-1].items() if k!='paths'},flush=True)
    save(OUT/'controls.json',{'source_sha256':source_hash(),'input_sha256':datahash,'results':answer})

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['prepare','collect','evaluate','controls']);a=p.parse_args();globals()[a.stage]()
