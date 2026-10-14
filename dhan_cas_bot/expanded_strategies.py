"""Production ports of recorded NIFTY research rules, never outcome selectors.

Every indicator reads completed bars or explicitly available source features.
TARGET/TRAIL execution is a named live policy: completed closes, then delayed
orders; no historical high-touch is treated as a live fill. Unknown fields
block only the rules that require them. Controls and cash/stock/multi-leg
experiments are not single-leg NIFTY engines.
"""
from datetime import datetime, time, timedelta
from decimal import Decimal as D
from statistics import median, pstdev
import math

INTRADAY=('OPEN_DRIVE','GAP_FADE','FIRST_LAST','TREND_PULLBACK','VOLUME_REVERSAL',
          'SECTOR_CATCHUP','RANGE_FAILURE','AFTERNOON_COMPRESSION','CHAIN_UNWIND','SKEW_UNWIND')
MULTI=('FUTURE_TREND','FUTURE_OI','BASIS_LEAD','IV_CHEAP_TREND','SKEW_UNWIND',
       'SECTOR_CONFIRM','GIFT_CATCHUP','CHAIN_UNWIND','PCR_CONFIRM','PAIN_ESCAPE',
       'INSTITUTIONAL_ALIGN','PUBLISHED_PCR','PUBLISHED_PAIN')
READINESS=('FAILED_ORB','VWAP_RECLAIM','COMPRESSION_BREAK','PRIOR_OI_WALL')
SPOT=('ORB30','LATE_BREAK','LATE_FADE','TREND1445','OPTION_ACCEL','OPTION_ACCEL_OI')
OVERNIGHT=('NIFTY_SELLOFF_REBOUND','NIFTY_DAY_CONTINUATION','NIFTY_TREND_ALIGNMENT')
FRONTIER=('SELLOFF_CALL','SELLOFF_PUT','RALLY_CALL','RALLY_PUT','TWO_SIDED_REVERSAL',
          'TWO_SIDED_CONTINUATION','TREND_PULLBACK','TREND_CONTINUATION')
SPECS={}
for family in INTRADAY:
    for style in ('FAST','SWING','DOUBLE'):
        SPECS[family+'_'+style]=(family,style,'ORDINARY','INTRADAY')
for family in (*MULTI,*READINESS,*SPOT):
    for scope in ('EXPIRY','ORDINARY'):
        # Historical old spot baselines were expiry-only.
        if family in SPOT and scope=='ORDINARY':continue
        for style in ('TARGET','TRAIL'):
            SPECS[scope+'_'+family+'_'+style]=(family,style,scope,'MARKET')
for family in SPOT:
    for style in ('TARGET','TRAIL'):
        SPECS[family+'_'+style]=(family,style,'EXPIRY','MARKET')
for family in OVERNIGHT:
    for clock in ('0930','1510'):
        SPECS[family+'_'+clock]=(family,'DOUBLE','ANY',clock)
for family in FRONTIER:
    SPECS[family]=(family,'DOUBLE','ANY','FRONTIER')
NAMES=tuple(SPECS)

RULES={
'OPEN_DRIVE':'From open >= 0.35%; three rising/falling closes, futures five-minute direction and session VWAP agree.',
'GAP_FADE':'Opening gap >= 0.5%; 25–100% retraced, three closes and futures confirm the reversal.',
'FIRST_LAST':'First half-hour move >= 0.2%; at 14:45 price remains on that side with futures and three-close confirmation.',
'TREND_PULLBACK':'Intraday: 30-minute move >= 0.25%, opposite ten-minute pullback and three-close/futures resumption. Overnight: 0.75% move opposing prior 20-day trend.',
'VOLUME_REVERSAL':'15-minute move >= 0.2%; three-minute futures volume >= 3x prior baseline and three closes reverse.',
'SECTOR_CATCHUP':'Bank and IT move >= 0.2% together; NIFTY moves less than half as much and then confirms.',
'RANGE_FAILURE':'Prior 15 minutes exceed opening range by 0.05%; price returns inside with three-close/futures reversal.',
'AFTERNOON_COMPRESSION':'Prior 30-minute range <= 0.15%; three closes break out with futures confirmation.',
'FUTURE_TREND':'15-minute NIFTY move >= 0.1%; futures direction and session VWAP agree.',
'FUTURE_OI':'Future-trend rule plus at least 1% futures OI increase in five minutes.',
'BASIS_LEAD':'Five-minute futures move >= 0.1%; basis changes >= 0.05% in that direction and three spot closes confirm.',
'IV_CHEAP_TREND':'Future-trend rule; current ATM IV <= prior 30-minute realized volatility and VIX is not falling.',
'SECTOR_CONFIRM':'NIFTY 15-minute move >= 0.1%; Bank and IT each confirm by >= 0.05%.',
'GIFT_CATCHUP':'GIFT 15-minute move >= 0.15%, with two-minute additional delay; NIFTY underreacts and three closes confirm.',
'SKEW_UNWIND':'Same-strike premium rises >= 25% in three minutes, OI falls >= 8%, opposite premium falls >= 10%; futures agree.',
'CHAIN_UNWIND':'ATM premium rises >= 15% in five minutes; own three-strike OI falls >= 5%, opposite OI rises >= 5%.',
'PCR_CONFIRM':'Future-trend rule plus >= 10% directional change in two completed, delayed five-minute PCR buckets.',
'PAIN_ESCAPE':'Future-trend rule; price crosses published max-pain level and stays beyond it for two closes.',
'INSTITUTIONAL_ALIGN':'Future-trend rule plus aligned FII futures change and DII net cash, lagged two verified sessions.',
'PUBLISHED_PCR':'Future-trend rule plus >= 10% directional PCR change in the complete prior-session chain.',
'PUBLISHED_PAIN':'Future-trend rule; two-close crossing of max-pain from the complete prior-session chain.',
'FAILED_ORB':'Three closes break opening range by 0.05%; two return inside with futures reversal and >= 2x volume.',
'VWAP_RECLAIM':'15 completed futures closes stay on one side of VWAP, then two cross; spot persists and volume >= 2x.',
'COMPRESSION_BREAK':'Prior 30-minute range <= 0.1%; three closes break by 0.02%, with futures and >= 2x volume.',
'PRIOR_OI_WALL':'Cross highest nearby prior-session OI wall; two closes persist, premium rises >= 25%, OI falls >= 8%.',
'ORB30':'Two closes break the complete first 30-minute range by at least five NIFTY points.',
'LATE_BREAK':'Two closes break the 14:15–14:30 range by at least five points.',
'LATE_FADE':'After the first five-point late-range break, two closes return inside; trade the reversal.',
'TREND1445':'At 14:45 the 15-minute move is >= 0.1%, aligns with the 61-minute move and efficiency >= 60%.',
'OPTION_ACCEL':'Frozen 14:45 ATM contract: premium rises >= 25% over three minutes and volume >= 2x baseline.',
'OPTION_ACCEL_OI':'Option-acceleration rule plus >= 8% OI decline in the same absolute contract.',
'NIFTY_SELLOFF_REBOUND':'At 15:10 NIFTY is down >= 0.75% from open; buy a call with next-session exit.',
'NIFTY_DAY_CONTINUATION':'At 15:10 the move from open is >= 0.5%; buy in the same direction.',
'NIFTY_TREND_ALIGNMENT':'At 15:10 move >= 0.2% from open, aligned with the published prior 20-day trend.',
'SELLOFF_CALL':'At 15:10 decline >= 0.75% from open; overnight call.',
'SELLOFF_PUT':'At 15:10 decline >= 0.75% from open; overnight put.',
'RALLY_CALL':'At 15:10 rise >= 0.75% from open; overnight call.',
'RALLY_PUT':'At 15:10 rise >= 0.75% from open; overnight put.',
'TWO_SIDED_REVERSAL':'At 15:10 absolute move >= 0.75%; buy the opposite side overnight.',
'TWO_SIDED_CONTINUATION':'At 15:10 absolute move >= 0.75%; buy the same side overnight.',
'TREND_CONTINUATION':'At 15:10 absolute move >= 0.75%, aligned with prior 20-day trend; continuation overnight.'}


class Missing(ValueError):pass


def bar(series,at):
    row=series.get(at)
    if row is None or row.available!=at or row.close<=0:raise Missing('MISSING_COMPLETED_BAR')
    return row


def ret(series,at,n):return bar(series,at).close/bar(series,at-timedelta(minutes=n)).close-1
def sign(value):return 1 if value>0 else -1 if value<0 else 0


def persistent(series,at,direction):
    rows=[bar(series,at-timedelta(minutes=i)).close for i in (2,1,0)]
    return direction!=0 and all(direction*(b-a)>0 for a,b in zip(rows,rows[1:]))


def range_values(rows):
    if not rows or any(b.high is None or b.low is None for b in rows):raise Missing('MISSING_OHLC_RANGE')
    return max(b.high for b in rows),min(b.low for b in rows)


def session_rows(series,opening,end):
    rows=[]; t=opening+timedelta(minutes=1)
    while t<=end:
        rows.append(bar(series,t));t+=timedelta(minutes=1)
    return rows


def vwap(series,opening,end):
    rows=session_rows(series,opening,end)
    if not rows or any(b.high is None or b.low is None for b in rows):raise Missing('MISSING_VWAP_INPUTS')
    volume=sum(b.volume for b in rows)
    if volume<=0:raise Missing('ZERO_FUTURE_VOLUME')
    return sum(((b.high+b.low+b.close)/3*b.volume for b in rows),D(0))/volume


def exit_policy(strategy):
    style=SPECS.get(strategy,('','DOUBLE','',''))[1]
    target,stop,minutes={'FAST':('1.25','.85',30),'SWING':('1.50','.75',60),
                         'DOUBLE':('2','.5',None),'TARGET':('2','.5',None),
                         'TRAIL':(None,'.5',None)}[style]
    return {'exit_target':target,'exit_stop':stop,'exit_trail':style=='TRAIL','hold_minutes':minutes}


def option(series,at,side,strike):
    row=series.get((side,strike),{}).get(at)
    if row is None or row.available!=at or row.close<=0:raise Missing('MISSING_SAME_STRIKE_OPTION')
    return row


def evaluate(strategy,now,calendar,spot,future,expiries,*,features=None,bar_at=None):
    from .session_strategies import Evaluation, IST
    from .domain import ContractError
    if strategy not in SPECS:raise ContractError('unknown directional strategy')
    family,style,scope,schedule=SPECS[strategy];now=now.astimezone(IST)
    at=(bar_at or now).astimezone(IST).replace(second=0,microsecond=0);features=features or {}
    policy=exit_policy(strategy)
    def result(state,reason,side=None,detail=None,exit_at=None):
        return Evaluation(strategy,state,reason,at,side,D(detail['anchor_spot']) if detail and detail.get('anchor_spot') else spot.get(at).close if at in spot else None,
            (exit_at.date()+timedelta(days=1) if schedule in ('0930','1510','FRONTIER') and exit_at else now.date()),
            exit_at,{**(detail or {}),**policy},
            [{'key':'rule','state':'PASS' if state=='SIGNAL' else 'FAIL' if state=='NO_SIGNAL' else 'UNKNOWN',
              'family':family,'value':reason}])
    if not 0 <= (now-at).total_seconds() <= 90:return result('UNKNOWN','STRATEGY_INPUTS_STALE')
    if not calendar or not calendar.fresh(now):return result('UNKNOWN','CALENDAR_UNAVAILABLE')
    if not calendar.is_open(now):return result('WAITING','EXCHANGE_CLOSED')
    if not expiries:return result('UNKNOWN','CONTRACT_CALENDAR_UNAVAILABLE')
    expiry=now.date() in expiries
    if (scope=='EXPIRY' and not expiry) or (scope=='ORDINARY' and expiry):
        return result('NOT_APPLICABLE','EXPIRY_SESSION_OUTSIDE_RESEARCH_SCOPE' if expiry else 'REQUIRES_EXPIRY_SESSION')
    if calendar.opens.time()!=time(9,15):return result('NOT_APPLICABLE','SPECIAL_SESSION_OUTSIDE_RESEARCH_SCOPE')
    minutes=at.hour*60+at.minute
    bounds=(585,630) if family=='OPEN_DRIVE' else (585,690) if family=='GAP_FADE' else (885,885) if family=='FIRST_LAST' else (810,885) if family=='AFTERNOON_COMPRESSION' else (600,885) if schedule=='INTRADAY' else (600,910)
    if family=='ORB30':bounds=(586,720)
    if family in ('LATE_BREAK','LATE_FADE'):bounds=(871,914)
    if family=='TREND1445':bounds=(885,885)
    if family in ('OPTION_ACCEL','OPTION_ACCEL_OI'):bounds=(885,930)
    # These suffixes describe NEXT-SESSION EXIT clocks in the recorded replay;
    # both source experiments entered at 15:10. Do not invent a 09:30 entry.
    if schedule in ('0930','1510'):bounds=(910,910)
    if schedule=='FRONTIER':bounds=(910,910)
    step=5 if family in MULTI or schedule=='INTRADAY' else 1
    if not bounds[0]<=minutes<=bounds[1] or minutes%step:
        return result('WAITING','OUTSIDE_STRATEGY_WINDOW')
    try:
        current=bar(spot,at).close;op=bar(spot,calendar.opens+timedelta(minutes=1)).open
        if op<=0:raise Missing('INVALID_OPEN_REFERENCE')
        d=0;detail={};exit_at=calendar.closes-timedelta(minutes=6)
        def future_core():
            s=ret(spot,at,15);f=ret(future,at,15);v=sign(s)
            level=vwap(future,calendar.opens,at)
            yes=abs(s)>=D('.001') and v*f>0 and v*(bar(future,at).close-level)>0
            return v if yes else 0,{'spot_15m':str(s),'future_15m':str(f),'future_vwap':str(level)}
        def volume_multiple():
            recent=sum(bar(future,at-timedelta(minutes=i)).volume for i in range(3))
            base=D(str(median(bar(future,at-timedelta(minutes=i)).volume for i in range(3,23))))
            if base<=0:raise Missing('ZERO_VOLUME_BASE')
            return D(recent)/(base*3)
        def published(key):
            row=features.get(key)
            if not isinstance(row,dict):raise Missing('MISSING_'+key.upper())
            available=row.get('received_at')
            if not isinstance(available,datetime) or available.tzinfo is None or available>now:
                raise Missing('SOURCE_NOT_YET_AVAILABLE')
            return row
        if schedule in ('0930','1510','FRONTIER'):
            from_open=current/op-1;v=sign(from_open)
            if family in ('NIFTY_SELLOFF_REBOUND','SELLOFF_CALL'):d=1 if from_open<=D('-.0075') else 0
            elif family=='SELLOFF_PUT':d=-1 if from_open<=D('-.0075') else 0
            elif family=='RALLY_CALL':d=1 if from_open>=D('.0075') else 0
            elif family=='RALLY_PUT':d=-1 if from_open>=D('.0075') else 0
            elif family=='TWO_SIDED_REVERSAL':d=-v if abs(from_open)>=D('.0075') else 0
            elif family=='TWO_SIDED_CONTINUATION':d=v if abs(from_open)>=D('.0075') else 0
            elif family in ('NIFTY_DAY_CONTINUATION','NIFTY_TREND_ALIGNMENT','TREND_CONTINUATION','TREND_PULLBACK'):
                trend=D(str(published('prior_trend')['value']))
                if family=='NIFTY_DAY_CONTINUATION':d=v if abs(from_open)>=D('.005') else 0
                elif family=='NIFTY_TREND_ALIGNMENT':d=v if abs(from_open)>=D('.002') and from_open*trend>0 else 0
                elif family=='TREND_CONTINUATION':d=v if abs(from_open)>=D('.0075') and from_open*trend>0 else 0
                else:d=-v if abs(from_open)>=D('.0075') and from_open*trend<0 else 0
                detail['prior_trend_20d']=str(trend)
            clock=time(9,30) if schedule=='0930' else time(15,10)
            exit_at=datetime.combine(calendar.next_opens.date(),clock,IST)
            if not calendar.next_opens<exit_at<calendar.next_closes:raise Missing('NEXT_SESSION_EXIT_UNAVAILABLE')
            detail.update(open_return=str(from_open))
        elif family in ('OPEN_DRIVE','GAP_FADE','FIRST_LAST','TREND_PULLBACK','VOLUME_REVERSAL','SECTOR_CATCHUP','RANGE_FAILURE','AFTERNOON_COMPRESSION'):
            f5=ret(future,at,5)
            if family=='OPEN_DRIVE':
                r=current/op-1;v=sign(r);level=vwap(future,calendar.opens,at)
                d=v if abs(r)>=D('.0035') and v*f5>0 and v*(bar(future,at).close-level)>0 and persistent(spot,at,v) else 0
                detail={'open_return':str(r),'future_vwap':str(level)}
            elif family=='GAP_FADE':
                previous=bar(spot,calendar.previous_spot_closes or calendar.previous_closes).close
                gap=op/previous-1;v=-sign(gap);fraction=(op-current)/(op-previous) if op!=previous else D(0)
                d=v if abs(gap)>=D('.005') and D('.25')<=fraction<=1 and v*f5>0 and persistent(spot,at,v) else 0
                detail={'gap':str(gap),'fraction_filled':str(fraction)}
            elif family=='FIRST_LAST':
                r=bar(spot,calendar.opens+timedelta(minutes=30)).close/op-1;v=sign(r)
                d=v if abs(r)>=D('.002') and v*(current-op)>0 and v*f5>0 and persistent(spot,at,v) else 0
                detail={'first_half_hour_return':str(r)}
            elif family=='TREND_PULLBACK':
                r=ret(spot,at,30);pull=ret(spot,at,10);v=sign(r)
                d=v if abs(r)>=D('.0025') and v*pull<0 and v*f5>0 and persistent(spot,at,v) else 0
                detail={'trend_30m':str(r),'pullback_10m':str(pull)}
            elif family=='VOLUME_REVERSAL':
                r=ret(spot,at,15);v=-sign(r)
                rows=[bar(future,at-timedelta(minutes=i)) for i in range(33)]
                base=D(str(median(sum(b.volume for b in rows[i:i+3]) for i in range(3,33,3))))
                if base<=0:raise Missing('ZERO_VOLUME_BASE')
                ratio=D(sum(b.volume for b in rows[:3]))/base
                d=v if abs(r)>=D('.002') and ratio>=3 and v*ret(future,at,1)>0 and persistent(spot,at,v) else 0
                detail={'move_15m':str(r),'volume_ratio':str(ratio)}
            elif family=='SECTOR_CATCHUP':
                b=ret(features.get('BANK',{}),at,15);i=ret(features.get('IT',{}),at,15);s=ret(spot,at,15);v=sign(b)
                d=v if abs(b)>=D('.002') and v*i>=D('.002') and v*s<min(abs(b),abs(i))/2 and v*f5>0 and persistent(spot,at,v) else 0
                detail={'bank_15m':str(b),'it_15m':str(i),'spot_15m':str(s)}
            elif family=='RANGE_FAILURE':
                hi,lo=range_values(session_rows(spot,calendar.opens,calendar.opens+timedelta(minutes=30)))
                past=[bar(spot,at-timedelta(minutes=i)).close for i in range(1,16)]
                if lo<=current<=hi:
                    for v,failed in ((1,min(past)<lo-current*D('.0005')),(-1,max(past)>hi+current*D('.0005'))):
                        if failed and v*f5>0 and persistent(spot,at,v):d=v;break
                detail={'opening_high':str(hi),'opening_low':str(lo)}
            else:
                hi,lo=range_values([bar(spot,at-timedelta(minutes=i)) for i in range(3,33)])
                latest=[bar(spot,at-timedelta(minutes=i)).close for i in (2,1,0)]
                if (hi-lo)/current<=D('.0015'):
                    if min(latest)>hi and f5>0:d=1
                    elif max(latest)<lo and f5<0:d=-1
                detail={'compressed_high':str(hi),'compressed_low':str(lo)}
        elif family in ('FUTURE_TREND','FUTURE_OI','IV_CHEAP_TREND','PCR_CONFIRM','PAIN_ESCAPE','INSTITUTIONAL_ALIGN','PUBLISHED_PCR','PUBLISHED_PAIN'):
            d,detail=future_core()
            if d and family=='FUTURE_OI':
                old=bar(future,at-timedelta(minutes=5)).oi;new=bar(future,at).oi
                if old<=0:raise Missing('MISSING_FUTURE_OI')
                detail['future_oi_5m']=str(D(new)/old-1)
                if D(new)/old<D('1.01'):d=0
            elif d and family=='IV_CHEAP_TREND':
                row=published('iv');k=min(row['values'],key=lambda k:(abs(k-current),k))
                iv=D(str(row['values'][k].get('CE' if d>0 else 'PE',0)))
                if iv<=0 or (now-row['received_at']).total_seconds()>90:raise Missing('MISSING_CURRENT_IV')
                prices=[float(bar(spot,at-timedelta(minutes=i)).close) for i in range(30,-1,-1)]
                rv=D(str(pstdev([math.log(b/a) for a,b in zip(prices,prices[1:])])*math.sqrt(252*375)*100))
                v=ret(features.get('VIX',{}),at,15);detail.update(iv=str(iv),realized_vol_30m=str(rv),vix_15m=str(v))
                if iv>rv or v<0:d=0
            elif d and family=='PCR_CONFIRM':
                rows=published('insights')['pcr'];new=rows.get(at);old=rows.get(at-timedelta(minutes=5))
                if not new or not old:raise Missing('MISSING_PCR_INSIGHT')
                change=new/old-1;detail['pcr_change_5m']=str(change)
                if d*change<D('.10'):d=0
            elif d and family in ('PAIN_ESCAPE','PUBLISHED_PCR','PUBLISHED_PAIN'):
                row=published('prior_chain') if family.startswith('PUBLISHED') else published('insights')
                if family=='PUBLISHED_PCR':
                    change=D(str(row['pcr_change']));detail['pcr_change']=str(change)
                    if d*change<D('.10'):d=0
                else:
                    level=D(str(row['max_pain'])) if family=='PUBLISHED_PAIN' else row['max-pain'].get(at)
                    if not level:raise Missing('MISSING_MAX_PAIN_INSIGHT')
                    closes=[bar(spot,at-timedelta(minutes=i)).close for i in (2,1,0)]
                    detail['known_max_pain']=str(level)
                    if not (d*(closes[0]-level)<=0 and all(d*(p-level)>0 for p in closes[1:])):d=0
            elif d and family=='INSTITUTIONAL_ALIGN':
                row=published('institutions');f=D(str(row['fii_net_change']));di=D(str(row['dii_net']))
                detail.update(fii_net_change=str(f),dii_net=str(di),source_date=str(row['source_date']))
                if d*f<=0 or d*di<=0:d=0
        elif family=='BASIS_LEAD':
            f=ret(future,at,5);s=ret(spot,at,5);v=sign(f)
            basis=bar(future,at).close/current-bar(future,at-timedelta(minutes=5)).close/bar(spot,at-timedelta(minutes=5)).close
            d=v if abs(f)>=D('.001') and v*basis>=D('.0005') and persistent(spot,at,v) else 0
            detail={'future_5m':str(f),'spot_5m':str(s),'basis_change':str(basis)}
        elif family=='SECTOR_CONFIRM':
            s=ret(spot,at,15);v=sign(s)
            b=ret(features.get('BANK',{}),at,15);i=ret(features.get('IT',{}),at,15)
            d=v if abs(s)>=D('.001') and v*b>=D('.0005') and v*i>=D('.0005') else 0
            detail={'spot_15m':str(s),'bank_15m':str(b),'it_15m':str(i)}
        elif family=='GIFT_CATCHUP':
            lead_at=at-timedelta(minutes=2);lead=ret(features.get('GIFT',{}),lead_at,15);s=ret(spot,at,15);v=sign(lead)
            d=v if abs(lead)>=D('.0015') and v*s<abs(lead)/2 and persistent(spot,at,v) else 0
            detail={'gift_15m':str(lead),'spot_15m':str(s),'lead_available':lead_at.isoformat()}
        elif family in ('CHAIN_UNWIND','SKEW_UNWIND'):
            options=features.get('options',{});strikes=sorted({k for side,k in options})
            if not strikes:raise Missing('MISSING_SAME_STRIKE_OPTION')
            k=min(strikes,key=lambda k:(abs(k-current),k));f=ret(future,at,5);v=sign(f)
            side='CE' if v>0 else 'PE';other='PE' if side=='CE' else 'CE';look=5 if family=='CHAIN_UNWIND' else 3
            cur=option(options,at,side,k);old=option(options,at-timedelta(minutes=look),side,k)
            r=cur.close/old.close-1;detail={'premium_return':str(r),'strike':str(k),'future_5m':str(f)}
            if v and r>=(D('.15') if look==5 else D('.25')):
                if look==5:
                    j=strikes.index(k);ks=strikes[max(0,j-1):j+2]
                    if len(ks)!=3:raise Missing('MISSING_CHAIN_NEIGHBOURS')
                    total=lambda s,t:sum(option(options,t,s,k).oi for k in ks)
                    own,opp=total(side,at-timedelta(minutes=5)),total(other,at-timedelta(minutes=5))
                    if min(own,opp)<=0:raise Missing('MISSING_CHAIN_OI')
                    ownratio=D(total(side,at))/own;oppratio=D(total(other,at))/opp
                    detail.update(own_oi=str(ownratio-1),opposite_oi=str(oppratio-1))
                    if ownratio<=D('.95') and oppratio>=D('1.05'):d=v
                else:
                    if old.oi<=0:raise Missing('MISSING_OPTION_OI')
                    opp=option(options,at,other,k).close/option(options,at-timedelta(minutes=3),other,k).close
                    detail.update(oi_change=str(D(cur.oi)/old.oi-1),opposite_return=str(opp-1))
                    if D(cur.oi)/old.oi<=D('.92') and opp<=D('.90'):d=v
        elif family in ('OPTION_ACCEL','OPTION_ACCEL_OI'):
            anchor=bar(spot,datetime.combine(now.date(),time(14,45),IST)).close
            options=features.get('options',{});strikes=sorted({k for side,k in options})
            if not strikes:raise Missing('MISSING_SAME_STRIKE_OPTION')
            k=min(strikes,key=lambda k:(abs(k-anchor),k));qualifying=[]
            for side in ('CE','PE'):
                rows=[option(options,at-timedelta(minutes=j),side,k) for j in range(32,-1,-1)]
                r=rows[-1].close/rows[-4].close-1
                base=D(str(median(sum(b.volume for b in rows[j:j+3]) for j in range(0,30,3))))
                unwind=rows[-4].oi>0 and D(rows[-1].oi)/rows[-4].oi<=D('.92')
                if r>=D('.25') and base>0 and sum(b.volume for b in rows[-3:])>=base*2 and (family=='OPTION_ACCEL' or unwind):
                    qualifying.append((r,side,unwind))
            if qualifying:
                r,side,unwind=sorted(qualifying,key=lambda x:(-x[0],x[1]))[0];d=1 if side=='CE' else -1
                # Signal strike selection uses the frozen 14:45 spot anchor.
                current=anchor
                detail={'premium_return_3m':str(r),'anchor_spot':str(anchor),'oi_unwind':unwind}
        elif family=='PRIOR_OI_WALL':
            row=published('prior_chain');anchor=bar(spot,datetime.combine(now.date(),time(9,30),IST)).close
            closes=[bar(spot,at-timedelta(minutes=i)).close for i in (2,1,0)]
            for side,v in (('CE',1),('PE',-1)):
                ks=[(k,oi) for (s,k),oi in row['oi'].items() if s==side and abs(k-anchor)<=200]
                if not ks:raise Missing('MISSING_PRIOR_WALL')
                k,oi=min(ks,key=lambda x:(-x[1],x[0]))
                if oi<=0:raise Missing('ZERO_PRIOR_WALL_OI')
                if not (v*(closes[0]-k)<=0 and all(v*(c-k)>0 for c in closes[1:])) or v*ret(future,at,3)<=0:continue
                cur=option(features.get('options',{}),at,side,k);old=option(features.get('options',{}),at-timedelta(minutes=3),side,k)
                if old.oi<=0:raise Missing('MISSING_PRIOR_OPTION_OI')
                if D(cur.oi)/old.oi<=D('.92') and cur.close/old.close>=D('1.25'):
                    d=v;detail={'prior_oi_wall':str(k),'oi_change':str(D(cur.oi)/old.oi-1),'premium_return':str(cur.close/old.close-1)};break
        elif family in READINESS:
            if family=='COMPRESSION_BREAK':
                hi,lo=range_values([bar(spot,at-timedelta(minutes=i)) for i in range(3,33)])
                closes=[bar(spot,at-timedelta(minutes=i)).close for i in range(3)]
                v=1 if min(closes)>=hi*D('1.0002') else -1 if max(closes)<=lo*D('.9998') else 0
                ratio=volume_multiple()
                d=v if (hi-lo)/((hi+lo)/2)<=D('.001') and v*ret(future,at,3)>0 and ratio>=2 else 0
                detail={'compression_high':str(hi),'compression_low':str(lo),'volume_ratio':str(ratio)}
            elif family=='VWAP_RECLAIM':
                times=[at-timedelta(minutes=i) for i in range(16,1,-1)]
                differences=[bar(future,t).close-vwap(future,calendar.opens,t) for t in times]
                v=1 if all(p<0 for p in differences) else -1 if all(p>0 for p in differences) else 0
                if v and all(v*(bar(future,t).close-vwap(future,calendar.opens,t))>0 for t in (at-timedelta(minutes=1),at)) and persistent(spot,at,v):
                    ratio=volume_multiple();d=v if ratio>=2 else 0;detail={'volume_ratio':str(ratio),'future_vwap':str(vwap(future,calendar.opens,at))}
            elif family=='FAILED_ORB':
                hi,lo=range_values(session_rows(spot,calendar.opens,calendar.opens+timedelta(minutes=30)))
                t=calendar.opens+timedelta(minutes=32);broken=None
                while t<at:
                    closes=[bar(spot,t-timedelta(minutes=i)).close for i in range(3)]
                    v=1 if min(closes)>=hi*D('1.0005') else -1 if max(closes)<=lo*D('.9995') else 0
                    if v:broken=(v,t);break
                    t+=timedelta(minutes=1)
                if broken and all(lo<=bar(spot,at-timedelta(minutes=i)).close<=hi for i in (1,0)) and persistent(future,at,-broken[0]):
                    ratio=volume_multiple();d=-broken[0] if ratio>=2 else 0
                    detail={'first_break_at':broken[1].isoformat(),'opening_high':str(hi),'opening_low':str(lo),'volume_ratio':str(ratio)}
        elif family in SPOT:
            if family=='ORB30' or family in ('LATE_BREAK','LATE_FADE'):
                begin=calendar.opens if family=='ORB30' else datetime.combine(now.date(),time(14,15),IST)
                end=begin+timedelta(minutes=30 if family=='ORB30' else 15)
                hi,lo=range_values(session_rows(spot,begin,end))
                closes=[bar(spot,at-timedelta(minutes=i)).close for i in (1,0)]
                if family=='LATE_FADE':
                    t=end+timedelta(minutes=1);broken=0
                    while t<at:
                        p=bar(spot,t).close
                        if p>=hi+5:broken=1;break
                        if p<=lo-5:broken=-1;break
                        t+=timedelta(minutes=1)
                    d=-broken if broken and all(lo<=p<=hi for p in closes) else 0
                else:d=1 if min(closes)>=hi+5 else -1 if max(closes)<=lo-5 else 0
                detail={'box_high':str(hi),'box_low':str(lo)}
            elif family=='TREND1445':
                rows=session_rows(spot,datetime.combine(now.date(),time(13,44),IST),at)
                prices=[b.close for b in rows];change=prices[-1]-prices[-16]
                path=sum(abs(b-a) for a,b in zip(prices[-16:],prices[-15:]))
                d=sign(change) if abs(change/prices[-16])>=D('.001') and change*(prices[-1]-prices[0])>0 and path>0 and abs(change)/path>=D('.60') else 0
                detail={'efficiency':str(abs(change)/path) if path else None}
        if policy['hold_minutes'] is not None:exit_at=min(exit_at,at+timedelta(minutes=1+policy['hold_minutes']))
        return result('SIGNAL' if d else 'NO_SIGNAL','EXPANDED_RULE_CONFIRMED' if d else 'EXPANDED_RULE_NOT_MET','CE' if d>0 else 'PE' if d<0 else None,detail,exit_at)
    except (Missing,KeyError,ArithmeticError,ValueError) as exc:
        return result('UNKNOWN',str(exc) if isinstance(exc,Missing) else 'COMPLETED_INPUT_MISSING_OR_INVALID')
