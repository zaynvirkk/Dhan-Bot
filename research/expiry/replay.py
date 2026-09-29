"""Whole-lot chronological research replay; model fills are not executions."""
from __future__ import annotations
import argparse,csv,hashlib,json,random
from collections import Counter
from datetime import datetime,timedelta
from decimal import Decimal as D
from math import ceil
from pathlib import Path
from research.gauntlet.core import Bar,Contract,entry,tick_down,tick_up,cash_after
from research.gauntlet.data import save
from .collect import STORE,option_file,selected_chain
from .signals import NAMES,option_signals,stamp
from .fast_order import make_order

START=D('9411.18')
RESULTS=Path(__file__).resolve().parents[1]/'results/expiry'

def digest():
    paths=list(Path(__file__).parent.glob('*.py'))+[Path(__file__).parent/'PROTOCOL.md',
        Path(__file__).resolve().parents[1]/'gauntlet/core.py',Path(__file__).resolve().parents[2]/'dhan_cas_bot/risk.py']
    return hashlib.sha256(b''.join(p.name.encode()+p.read_bytes() for p in sorted(paths))).hexdigest()

def dataset(quality='strict'):
    if quality not in ('strict','reported'):raise ValueError('unknown data-quality policy')
    plan=json.loads((STORE/'plan.json').read_text());days={}
    hashes=[]
    for day,x in sorted(plan.items()):
        if 'error' in x:days[day]=x;continue
        chain=[Contract.parse(m) for m in x['contracts'].values()];bars={};errors={}
        for c in chain:
            file=option_file(day,c.key)
            if not file.exists():errors[c.key]='UNKNOWN_REQUEST';continue
            raw=json.loads(file.read_text());hashes.append(hashlib.sha256(file.read_bytes()).hexdigest())
            if raw['key']!=c.key or raw['day']!=day:raise ValueError('cache identity mismatch')
            if raw['audit']['status']!='RECONCILED' and quality=='strict':errors[c.key]=raw['audit']['status']
            bars[c.key]=[Bar.parse(r) for r in raw['bars']]
        anchors={side:selected_chain(chain,D(x['anchor']),side)[0] for side in ('CE','PE')}
        eligible={s:bars[c.key] for s,c in anchors.items() if c.key in bars and c.key not in errors}
        os,og=option_signals(eligible,day,D(x['anchor']))
        signals=x['signals']|os
        for side in ('CE','PE'):
            signals['BLIND_'+side]={'name':'BLIND_'+side,'at':stamp(day,'14:45').isoformat(),'side':side,'spot':x['anchor'],'detail':{}}
        days[day]={'partition':x['partition'],'signals':signals,'gaps':x['gaps']+og,
                   'chain':chain,'bars':bars,'errors':errors}
    raw_hashes=[hashlib.sha256((STORE/n).read_bytes()).hexdigest() for n in ('spot.json','official.json','calendar.json','plan.json')]
    datahash=hashlib.sha256((''.join(raw_hashes)+''.join(hashes)).encode()).hexdigest()
    return days,datahash

def choose(day,signal,cash,side=None):
    at=datetime.fromisoformat(signal['at']);side=side or signal['side']
    trace=[]
    for c in selected_chain(day['chain'],D(signal['spot']),side):
        if c.key in day['errors']:return None,'UNKNOWN_SELECTION_DATA',trace+[day['errors'][c.key]]
        cache=day.setdefault('_snapshots',{})
        if (c.key,at) not in cache:
            # The order rule uses exactly these last three completed minutes.
            # Filter the full tape by availability once, then retain that bounded
            # view. Contiguity is checked below before order construction.
            cache[c.key,at]=[b for b in day['bars'].get(c.key,[]) if b.available<=at][-3:]
        known=cache[c.key,at]
        required=[at-timedelta(minutes=j) for j in range(0,3)]
        if any(t not in {b.available for b in known[-3:]} for t in required):
            return None,'UNKNOWN_SELECTION_BARS',trace
        order,status=make_order(c,known,at,cash,signal['name']+':'+at.isoformat())
        trace.append({'contract':c.key,'status':status})
        if order:return order,status,trace
    return None,'NO_AFFORDABLE_LIQUID_CONTRACT',trace

def liquidate(order,fill,bars,style,close_at):
    """Adverse stop precedence and pending partial exits; no future stop ratchet."""
    by={b.start:b for b in bars};at=fill['bar'].start
    stop=tick_down(fill['price']*D('.5'),order.contract.tick)
    peak=fill['price'];target=tick_up(fill['price']*2,order.contract.tick)
    remaining=order.quantity;parts=[];pending=None;worst=fill['price']
    while at<close_at:
        b=by.get(at)
        if b is None:return {'status':'UNKNOWN_HOLDING_BAR','at':at.isoformat(),'parts':parts}
        worst=min(worst,b.low)
        if pending is None:
            if b.low<=stop:pending='STOP'
            elif at>=close_at-timedelta(minutes=6):pending='TIMED_CLOSE'
        capacity=int(D(b.volume)*D('.05'))//order.contract.lot*order.contract.lot
        if at==fill['bar'].start:capacity=max(0,capacity-order.quantity)
        if pending:
            qty=min(remaining,capacity)
            if qty:
                px=tick_down(b.low*D('.99'),order.contract.tick)
                parts.append({'quantity':qty,'price':str(px),'at':at.isoformat()});remaining-=qty
            if not remaining:
                return {'status':'MODELED_EXIT','at':b.available.isoformat(),'price':sum(D(p['price'])*p['quantity'] for p in parts)/order.quantity,
                        'parts':parts,'reason':pending,'worst':worst}
        elif at>fill['bar'].start and style=='TARGET' and b.high>=target*D('1.02') and capacity>=remaining:
            return {'status':'MODELED_EXIT','at':b.available.isoformat(),'price':target,'reason':'TARGET_2X','worst':worst}
        # A close is usable only for subsequent bars, never this bar's low.
        if style=='TRAIL' and not pending:
            peak=max(peak,b.close);stop=max(stop,tick_down(peak*D('.5'),order.contract.tick))
        at+=timedelta(minutes=1)
    return {'status':'UNKNOWN_EXIT_CAPACITY','at':at.isoformat(),'remaining':remaining,'parts':parts}

def run(days,name,style,period,delay=1,adverse=True,seed=None,skip=None):
    cash=START;peak=START;mdd=D(0);ledger=[];counts=Counter();rng=random.Random(seed)
    unknown=None;best=None;bestpnl=D('-Infinity');marked_dd=D(0)
    for day,x in sorted(days.items()):
        if period!='all' and x['partition']!=period:continue
        counts['sessions']+=1
        if 'error' in x:
            unknown=day+':'+x['error'];break
        sig=x['signals'].get(name)
        if not sig:
            if any(g.startswith(name+':') for g in x['gaps']):unknown=day+':UNKNOWN_SIGNAL';break
            counts['no_signal']+=1;continue
        side=sig['side'] if seed is None else rng.choice(['CE','PE'])
        counts['signals']+=1
        row={'day':day,'at':sig['at'],'side':side,'cash_before':str(cash),'signal':name}
        if day==skip:counts['deleted']+=1;continue
        order,status,trace=choose(x,sig,cash,side)
        row.update(status=status,selection=trace)
        if status.startswith('UNKNOWN'):
            ledger.append(row);unknown=day+':'+status;break
        if not order:
            counts['unaffordable_or_liquidity']+=1;ledger.append(row);continue
        row.update(contract=order.contract.key,strike=str(order.contract.strike),lot=order.contract.lot,quantity=order.quantity,limit=str(order.limit))
        f=entry(order,x['bars'][order.contract.key],delay_bars=delay,adverse=adverse)
        row['status']=f['status']
        if f['status'].startswith('UNKNOWN'):
            ledger.append(row);unknown=day+':'+f['status'];break
        if f['status']!='MODELED_FILL':counts['misses']+=1;ledger.append(row);continue
        close=stamp(day,'15:40' if day>='2026-08-03' else '15:30')
        cache=x.setdefault('_exits',{})
        k=(order.contract.key,order.quantity,f['time'],f['price'],style)
        if k not in cache:cache[k]=liquidate(order,f,x['bars'][order.contract.key],style,close)
        out=cache[k]
        row.update(status=out['status'],entry=str(f['price']),entry_at=f['time'])
        if out['status']!='MODELED_EXIT':
            ledger.append(row);unknown=day+':'+out['status'];break
        new,fees=cash_after(cash,order,f['price'],out['price'],out.get('parts'))
        pnl=new-cash;counts['trades']+=1;counts['wins' if pnl>0 else 'losses']+=1
        counts[out['reason']]+=1
        row.update(exit=str(out['price']),exit_at=out['at'],reason=out['reason'],pnl=str(pnl),fees=str(fees),cash_after=str(new),premium_multiple=str(out['price']/f['price']))
        # Conservative low mark is a diagnostic, not an executable liquidation.
        low_equity=cash-order.quantity*f['price']+order.quantity*out['worst']-fees
        marked_dd=max(marked_dd,1-low_equity/peak)
        cash=new;peak=max(peak,cash);mdd=max(mdd,1-cash/peak)
        if pnl>bestpnl:bestpnl=pnl;best=day
        ledger.append(row)
    return {'strategy':name+'_'+style,'period':period,'delay':delay,'adverse':adverse,'seed':seed,
        'final_bankroll':None if unknown else str(cash.quantize(D('.01'))),'resolved_cash':str(cash.quantize(D('.01'))),
        'unknown':unknown,'counts':dict(counts),'closed_drawdown':str(mdd),'intrabar_mark_drawdown':str(marked_dd),
        'best_trade_day':best,'ledger':ledger}

def main():
    p=argparse.ArgumentParser();p.add_argument('--period',choices=['development','recent_validation','older_validation','all'],required=True)
    p.add_argument('--quality',choices=['strict','reported'],default='strict');a=p.parse_args()
    days,datahash=dataset(a.quality);out=[]
    for name in NAMES+('BLIND_CE','BLIND_PE'):
        for style in ('TARGET','TRAIL'):
            for delay,adverse,label in [(1,True,'primary'),(2,True,'delay2'),(3,True,'delay3'),(1,False,'open_plus_1pct')]:
                r=run(days,name,style,a.period,delay,adverse);r['scenario']=label;out.append(r)
            base=out[-4]
            r=run(days,name,style,a.period,skip=base['best_trade_day']);r['scenario']='delete_best';out.append(r)
            print(a.period,name,style,'cash',base['final_bankroll'],'trades',base['counts'].get('trades',0),'unknown',base['unknown'],flush=True)
    save(RESULTS/(a.period+'_'+a.quality+'.json'),{'source_hash':digest(),'data_hash':datahash,'quality':a.quality,'runs':out})

if __name__=='__main__':main()
