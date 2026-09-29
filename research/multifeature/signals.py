"""First-signal decisions use only completed, timestamp-aligned input records."""
import hashlib,json,math
from collections import defaultdict
from datetime import datetime,timedelta,timezone
from statistics import pstdev
from research.gauntlet.core import Bar,Contract,D
from research.gauntlet.data import save
from research.expiry.signals import stamp,spot_signals,signal
from .providers import STORE,OUT

NAMES=('FUTURE_TREND','FUTURE_OI','BASIS_LEAD','IV_CHEAP_TREND','SKEW_UNWIND','SECTOR_CONFIRM','GIFT_CATCHUP','CHAIN_UNWIND','PCR_CONFIRM','PAIN_ESCAPE','INSTITUTIONAL_ALIGN','PUBLISHED_PCR','PUBLISHED_PAIN')
IST=timezone(timedelta(hours=5,minutes=30))

def mapped(rows):return {b.available:b for b in map(Bar.parse,rows)}

def rolling_map():
    """No ATM-relative returns: key every row by absolute strike and timestamp."""
    out={};conflicts=set();summary=defaultdict(int)
    for f in sorted((STORE/'api').glob('*.json')):
        r=json.loads(f.read_text())
        if r.get('path')!='/v2/charts/rollingoption' or r.get('status')!=200:continue
        req=r['request'];side='CE' if req['drvOptionType']=='CALL' else 'PE'
        x=r['body'].get('data',{}).get('ce' if side=='CE' else 'pe') or {}
        fields=('close','oi','iv','spot','volume','open','high','low')
        times=x.get('timestamp',[])
        if any(len(x.get(k,[]))!=len(times) for k in fields+('strike',)):
            summary['unequal_arrays']+=1;continue
        for i,t in enumerate(times):
            at=datetime.fromtimestamp(t,IST)+timedelta(minutes=1);day=at.date().isoformat()
            if not req['fromDate']<=day<req['toDate']:summary['out_of_requested_range']+=1;continue
            vals=tuple(float(x[k][i]) if x[k][i] is not None else float('nan') for k in fields)
            if not all(math.isfinite(v) for v in vals) or min(vals)<0 or vals[0]<=0:
                summary['invalid_rows']+=1;continue
            strike=float(x['strike'][i]);key=(at,side,strike)
            if key in out and out[key]!=vals:conflicts.add(key);summary['conflicting_rows']+=1
            else:out[key]=vals
            summary['rows']+=1
    for k in conflicts:out.pop(k,None)
    summary['unique_usable']=len(out)
    save(OUT/'rolling_identity_audit.json',dict(summary))
    return out

class Missing(Exception):pass

def at_bar(series,at):
    b=series.get(at)
    if b is None:raise Missing('MISSING_COMPLETED_BAR')
    return b

def ret(series,at,minutes):
    now=at_bar(series,at);old=at_bar(series,at-timedelta(minutes=minutes))
    if old.close<=0:raise Missing('ZERO_REFERENCE')
    return float(now.close/old.close-1)

def confirms(spot,at,direction):
    rows=[at_bar(spot,at-timedelta(minutes=i)).close for i in (2,1,0)]
    return all(direction*(b-a)>0 for a,b in zip(rows,rows[1:]))

def option_value(options,at,side,strike):
    r=options.get((at,side,float(strike)))
    if r is None:raise Missing('MISSING_SAME_STRIKE_OPTION')
    return r

def market_maps(days):
    insights={'pcr':{},'max-pain':{}};institutions={'fii':{},'dii':{}}
    for f in sorted((STORE/'api').glob('*.json')):
        raw=json.loads(f.read_text());path=raw.get('path','')
        if raw.get('status')!=200:continue
        from urllib.parse import urlparse,parse_qs
        args=parse_qs(urlparse(path).query);data=raw.get('body',{}).get('data') or {}
        for kind in insights:
            if path.startswith('/v2/market/'+kind+'?'):
                day=args['date'][0];field='max_pain' if kind=='max-pain' else 'pcr'
                for row in data.get('insights',[]):
                    # Delay the whole bucket; top-level EOD summaries ignored.
                    at=stamp(day,row['time'])+timedelta(minutes=5)
                    value=float(row[field]);key=(day,at)
                    if value<=0:continue
                    if key in insights[kind] and insights[kind][key]!=value:raise ValueError('conflicting intraday insight')
                    insights[kind][key]=value
        for kind in institutions:
            if path.startswith('/v2/market/'+kind+'?'):
                for rows in data.values():
                    for row in rows:
                        day=datetime.fromtimestamp(row['time_stamp']/1000,IST).date().isoformat()
                        if day in institutions[kind] and institutions[kind][day]!=row:raise ValueError('conflicting institutional row')
                        institutions[kind][day]=row
    resolved={}
    for day in days:
        previous=sorted(d for d in days if d<day)
        if len(previous)<3:continue
        d=previous[-2];p=previous[-3]
        if d not in institutions['fii'] or p not in institutions['fii'] or d not in institutions['dii']:continue
        f=institutions['fii'][d];old=institutions['fii'][p];di=institutions['dii'][d]
        resolved[day]={'source_date':d,'fii_net_change':f['total_long_contracts']-f['total_short_contracts']-old['total_long_contracts']+old['total_short_contracts'],
                       'dii_net':di['buy_amount']-di['sell_amount']}
    return insights,resolved

def prior_chain_features(rows,expiry):
    rows=[r for r in rows if r['FinInstrmTp']=='IDO' and (r.get('FininstrmActlXpryDt') or r['XpryDt'])==expiry]
    total={side:sum(int(r['OpnIntrst']) for r in rows if r['OptnTp']==side) for side in ('CE','PE')}
    old={side:sum(int(r['OpnIntrst'])-int(r['ChngInOpnIntrst']) for r in rows if r['OptnTp']==side) for side in ('CE','PE')}
    if not rows or min(total.values())<=0 or min(old.values())<=0:return {}
    strikes=sorted({float(r['StrkPric']) for r in rows})
    def liability(k):return sum(int(r['OpnIntrst'])*max(0,k-float(r['StrkPric']) if r['OptnTp']=='CE' else float(r['StrkPric'])-k) for r in rows)
    pain=min(strikes,key=lambda k:(liability(k),k))
    return {'pcr_change':(total['PE']/total['CE'])/(old['PE']/old['CE'])-1,'max_pain':pain}

def scan_day(day,idx,future,options,chain,lag=0,market=None,institutional=None,prior_chain=None):
    market=market or {};institutional=institutional or {}
    prior_chain=prior_chain or {}
    signals={};gaps={};history=[];spot=idx['NIFTY']
    strikes=sorted({float(c.strike) for c in chain})
    for minutes in range(600,911,5):
        at=stamp(day,f'{minutes//60:02d}:{minutes%60:02d}');oldat=at-timedelta(minutes=lag)
        feature={'at':at.isoformat(),'lag_minutes':lag}
        def evaluate(name,fn):
            if name in signals or name in gaps:return
            try:
                side,detail=fn()
                if side:signals[name]=signal(name,at,side,at_bar(spot,at).close,detail)
            except Missing as e:gaps[name]=str(e)+':'+at.isoformat()
        def core():
            s=ret(spot,at,15);f=ret(future,at,15);direction=1 if s>0 else -1
            if abs(s)<.001 or direction*f<=0:return None,{'spot_15m':s,'future_15m':f}
            rows=[at_bar(future,stamp(day,'09:16')+timedelta(minutes=i)) for i in range(minutes-555)]
            volume=sum(b.volume for b in rows)
            if not volume:raise Missing('ZERO_FUTURE_VOLUME')
            vwap=sum(float((b.high+b.low+b.close)/3)*b.volume for b in rows)/volume
            last=float(at_bar(future,at).close)
            if direction*(last-vwap)<=0:return None,{'vwap':vwap}
            return 'CE' if direction>0 else 'PE',{'spot_15m':s,'future_15m':f,'future_vwap':vwap}
        def oi():
            side,d=core()
            if not side:return side,d
            old=at_bar(future,oldat-timedelta(minutes=5)).oi;now=at_bar(future,oldat).oi
            if old<=0:raise Missing('MISSING_FUTURE_OI')
            d['future_oi_5m']=now/old-1
            return (side if now/old>=1.01 else None),d
        def basis():
            f=ret(future,at,5);s=ret(spot,at,5);direction=1 if f>0 else -1
            current=float(at_bar(future,at).close/at_bar(spot,at).close)
            old=float(at_bar(future,at-timedelta(minutes=5)).close/at_bar(spot,at-timedelta(minutes=5)).close)
            d={'future_5m':f,'spot_5m':s,'basis_change':current-old}
            return ('CE' if direction>0 else 'PE') if abs(f)>=.001 and direction*(current-old)>=.0005 and confirms(spot,at,direction) else None,d
        def cheap():
            side,d=core()
            if not side:return side,d
            k=min(strikes,key=lambda k:(abs(k-float(at_bar(spot,oldat).close)),k))
            iv=option_value(options,oldat,side,k)[2]
            if iv<=0:raise Missing('MISSING_IV')
            prices=[float(at_bar(spot,at-timedelta(minutes=i)).close) for i in range(30,-1,-1)]
            rv=pstdev([math.log(b/a) for a,b in zip(prices,prices[1:])])*math.sqrt(252*375)*100
            v=ret(idx['VIX'],at,15);d.update(iv=iv,realized_vol_30m=rv,vix_15m=v)
            return side if iv<=rv and v>=0 else None,d
        def sectors():
            s=ret(spot,at,15);direction=1 if s>0 else -1
            if abs(s)<.001:return None,{'spot_15m':s}
            bank=ret(idx['BANK'],at,15);it=ret(idx['IT'],at,15)
            return ('CE' if direction>0 else 'PE') if direction*bank>=.0005 and direction*it>=.0005 else None,{'spot_15m':s,'bank_15m':bank,'it_15m':it}
        def gift():
            if day<'2026-05-11':raise Missing('UPSTOX_GLOBAL_NOT_LAUNCHED')
            leadat=at-timedelta(minutes=2);lead=ret(idx['GIFT'],leadat,15);direction=1 if lead>0 else -1
            s=ret(spot,at,15)
            return ('CE' if direction>0 else 'PE') if abs(lead)>=.0015 and direction*s<abs(lead)*.5 and confirms(spot,at,direction) else None,{'gift_15m':lead,'spot_15m':s,'lead_available':leadat.isoformat()}
        def pcr():
            side,d=core()
            if not side:return side,d
            now=market.get('pcr',{}).get((day,oldat));old=market.get('pcr',{}).get((day,oldat-timedelta(minutes=5)))
            if now is None or old is None:raise Missing('MISSING_PCR_INSIGHT')
            direction=1 if side=='CE' else -1;change=now/old-1;d['pcr_change_5m']=change
            return side if direction*change>=.10 else None,d
        def pain():
            side,d=core()
            if not side:return side,d
            level=market.get('max-pain',{}).get((day,oldat))
            if level is None:raise Missing('MISSING_MAX_PAIN_INSIGHT')
            direction=1 if side=='CE' else -1
            closes=[float(at_bar(spot,at-timedelta(minutes=i)).close) for i in (2,1,0)]
            ok=direction*(closes[0]-level)<=0 and all(direction*(v-level)>0 for v in closes[1:])
            d['known_max_pain']=level
            return side if ok else None,d
        def institutional_rule():
            side,d=core()
            if not side:return side,d
            row=institutional.get(day)
            if row is None:raise Missing('MISSING_PREVIOUS_PUBLISHED_INSTITUTIONAL')
            direction=1 if side=='CE' else -1;d.update(row)
            return side if direction*row['fii_net_change']>0 and direction*row['dii_net']>0 else None,d
        def published(pain_mode=False):
            side,d=core()
            if not side:return side,d
            if not prior_chain:raise Missing('MISSING_PUBLISHED_CHAIN')
            direction=1 if side=='CE' else -1;d.update(prior_chain)
            if not pain_mode:return side if direction*prior_chain['pcr_change']>=.10 else None,d
            level=prior_chain['max_pain'];closes=[float(at_bar(spot,at-timedelta(minutes=i)).close) for i in (2,1,0)]
            return side if direction*(closes[0]-level)<=0 and all(direction*(v-level)>0 for v in closes[1:]) else None,d
        def option_flow(chainflow=False):
            k=min(strikes,key=lambda k:(abs(k-float(at_bar(spot,oldat).close)),k))
            f=ret(future,at,5);side='CE' if f>0 else 'PE';opposite='PE' if side=='CE' else 'CE'
            if f==0:return None,{'future_5m':0}
            look=5 if chainflow else 3
            current=option_value(options,oldat,side,k);prior=option_value(options,oldat-timedelta(minutes=look),side,k)
            r=current[0]/prior[0]-1
            if r<(.15 if chainflow else .25):return None,{'premium_return':r}
            if chainflow:
                i=strikes.index(k);ks=strikes[max(0,i-1):i+2]
                if len(ks)!=3:raise Missing('MISSING_CHAIN_NEIGHBOURS')
                now=sum(option_value(options,oldat,side,j)[1] for j in ks)
                old=sum(option_value(options,oldat-timedelta(minutes=look),side,j)[1] for j in ks)
                oppnow=sum(option_value(options,oldat,opposite,j)[1] for j in ks)
                oppold=sum(option_value(options,oldat-timedelta(minutes=look),opposite,j)[1] for j in ks)
                if old<=0 or oppold<=0:raise Missing('MISSING_CHAIN_OI')
                return side if now/old<=.95 and oppnow/oppold>=1.05 else None,{'premium_return':r,'own_oi':now/old-1,'opposite_oi':oppnow/oppold-1,'strikes':ks}
            oppnow=option_value(options,oldat,opposite,k);oppold=option_value(options,oldat-timedelta(minutes=look),opposite,k)
            if prior[1]<=0:raise Missing('MISSING_OPTION_OI')
            return side if current[1]/prior[1]<=.92 and oppnow[0]/oppold[0]<=.90 and f!=0 else None,{'premium_return':r,'oi_change':current[1]/prior[1]-1,'opposite_return':oppnow[0]/oppold[0]-1,'strike':k}
        for name,fn in [('FUTURE_TREND',core),('FUTURE_OI',oi),('BASIS_LEAD',basis),('IV_CHEAP_TREND',cheap),
                        ('SECTOR_CONFIRM',sectors),('GIFT_CATCHUP',gift),('SKEW_UNWIND',option_flow),('CHAIN_UNWIND',lambda:option_flow(True)),
                        ('PCR_CONFIRM',pcr),('PAIN_ESCAPE',pain),('INSTITUTIONAL_ALIGN',institutional_rule),
                        ('PUBLISHED_PCR',published),('PUBLISHED_PAIN',lambda:published(True))]:
            evaluate(name,fn)
        history.append(feature)
    return signals,[k+':'+v for k,v in gaps.items()]

def main():
    inst=json.loads((STORE/'instruments.json').read_text());idx={}
    for symbol in ('NIFTY','BANK','IT','VIX','GIFT'):
        raw=json.loads((STORE/'indexes'/(symbol+'.json')).read_text());idx[symbol]=mapped(raw['bars'])
    futures={}
    for f in (STORE/'futures').glob('*.json'):
        raw=json.loads(f.read_text());futures[raw['key']]=mapped(raw['bars'])
    options=rolling_map();out={};market,institutional=market_maps(sorted(inst));official=json.loads((STORE/'official.json').read_text())
    for day,x in inst.items():
        if 'error' in x:out[day]={'signals':{},'lag5_signals':{},'gaps':[n+':INSTRUMENT_ERROR' for n in NAMES],'anchor':None};continue
        chain=[Contract.parse(m) for m in x['chain'].values()]
        prior=prior_chain_features(official[x['prior_day']],x['expiry'])
        if prior:prior['source_date']=x['prior_day']
        sig,gap=scan_day(day,idx,futures.get(x['future_key'],{}),options,chain,market=market,institutional=institutional,prior_chain=prior)
        lag,lg=scan_day(day,idx,futures.get(x['future_key'],{}),options,chain,5,market,institutional,prior)
        bars=[b for b in idx['NIFTY'].values() if b.start.date().isoformat()==day]
        old,og,anchor=spot_signals(bars,day)
        out[day]={'signals':sig,'gaps':gap,'lag5_signals':lag,'lag5_gaps':lg,'old_signals':old,'old_gaps':og,'anchor':str(anchor) if anchor else None}
        print('signals',day,'new',len(sig),'unknown',len(gap),'lag5',len(lag),flush=True)
    save(STORE/'signals.json',out)

if __name__=='__main__':main()
