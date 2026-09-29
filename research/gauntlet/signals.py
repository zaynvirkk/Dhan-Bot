"""Frozen, causal signal rules. Inputs are completed bars and public records."""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime,timedelta
from decimal import Decimal as D
from statistics import median, mean
from zoneinfo import ZoneInfo
import json
import re
from .core import Bar
from .data import CACHE, save
from .collect import START, END

IST=ZoneInfo('Asia/Kolkata')
MATERIAL=re.compile(r'financial results|unaudited.*results|audited.*results|acquisition|bagging/receiving|guidance|change in management|resignation of director/kmp/smp|action\(s\) taken|regulatory.*order',re.I)
AMBIGUOUS={'General Updates','Updates','Press Release','Outcome of Board Meeting','Resignation','Appointment'}
REPOST={'Copy of Newspaper Publication','Analysts/Institutional Investor Meet/Con. Call Updates','Investor Presentation','Trading Window'}

def announcement_records():
    out=defaultdict(list);seen=set()
    for file in sorted((CACHE/'public').glob('announcements_*.json')):
        if 'receipt' in file.name:
            continue
        for r in json.loads(file.read_text()):
            key=r.get('seq_id')
            if key in seen:continue
            seen.add(key)
            text=r.get('desc','')+' '+r.get('attchmntText','')
            ts=r.get('exchdisstime')
            if not ts:continue  # Retained separately as a data gap by audit.
            try:at=datetime.strptime(ts,'%d-%b-%Y %H:%M:%S').replace(tzinfo=IST)
            except ValueError:continue
            quality='OTHER' if r.get('desc') in REPOST else ('QUALIFYING_TEXT' if MATERIAL.search(text) else ('UNKNOWN_MATERIALITY' if r.get('desc') in AMBIGUOUS else 'OTHER'))
            out[r['symbol']].append({'id':key,'at':at,'quality':quality,'category':r.get('desc'),
                'text':text,'url':r.get('attchmntFile')})
    return {s:sorted(rows,key=lambda e:e['at']) for s,rows in out.items()}

def event_rule(last3,ref,opening,rvol,extreme,direction,intraday=False):
    if len(last3)!=3 or any(b.available!=c.start for b,c in zip(last3,last3[1:])):
        return False
    if ref<=0 or opening<=0 or rvol<D(3):return False
    if any(D(direction)*(b.close/ref-1)<D('.025') for b in last3):return False
    if intraday:
        if D(direction)*(last3[-1].close-last3[0].close)<=0:return False
    elif any(D(direction)*(b.close/opening-1)<D('.015') for b in last3):return False
    impulse=D(direction)*(extreme-ref)
    return impulse>0 and D(direction)*(last3[-1].close-ref)>=impulse*D('.5')

def forced_rule(underlying,options,strike,side):
    """33 bars required; exact contract and exact contiguous minute alignment."""
    if len(options)<33 or len(underlying)<4:return False
    x=options[-33:];u=underlying[-4:]
    if any(a.available!=b.start for a,b in zip(x,x[1:])):return False
    if any(a.available!=b.start for a,b in zip(u,u[1:])):return False
    if x[-1].start!=u[-1].start:return False
    sign=1 if side=='CE' else -1
    if not (sign*(u[-3].close-strike)<=0 and all(sign*(b.close-strike)>0 for b in u[-2:])):return False
    old=x[-4];new=x[-1]
    if old.close<=0 or old.oi<=0:return False
    baseline=D(sum(b.volume for b in x[:-3]))/10
    return (new.close>=old.close*D('1.25') and D(new.oi)<=D(old.oi)*D('.92') and
            baseline>0 and sum(b.volume for b in x[-3:])>=baseline*4)

def passive_rule(known_event,last3,opening_range,rvol,adv):
    """Caller must supply original announced terms, not realized close flows."""
    if known_event['available_at']>last3[-1].available:return False
    if known_event['effective_date']!=last3[-1].start.date():return False
    if last3[-1].available.hour*60+last3[-1].available.minute<870:return False
    flow=known_event['signed_flow']
    if adv<=0 or abs(flow)<adv*D('.2') or rvol<3:return False
    boundary=opening_range[1] if flow>0 else opening_range[0]
    return all((1 if flow>0 else -1)*(b.close-boundary)>0 for b in last3)

def lag_rule(lead_move,lead_std,beta,target_move,residual_std,last3):
    """beta/std must come from a frozen pre-test estimation sample."""
    if lead_std<=0 or residual_std<=0 or abs(lead_move)<3*lead_std:return False
    predicted=beta*lead_move
    direction=1 if predicted>0 else -1
    return (direction*(predicted-target_move)>=residual_std and
            all(direction*(b.close-a.close)>0 for a,b in zip(last3,last3[1:])))

def scheduled_vol_rule(schedule_known_at,now,event_at,straddle,spot,prior_moves):
    if schedule_known_at>now or event_at-now!=timedelta(minutes=30) or len(prior_moves)<8 or spot<=0:return False
    return straddle/spot<D('.75')*D(str(median(prior_moves)))

def ofs_rule(event,last3,rvol,adv):
    if event['available_at']>last3[-1].available or event['effective_date']!=last3[-1].start.date():return None
    if last3[-1].available.hour*60+last3[-1].available.minute<570:return None
    if adv<=0 or event['offer_value']<adv*D('.2') or rvol<3:return None
    if all(b.close<event['floor'] for b in last3):return 'PE'
    if all(b.close>event['reference'] for b in last3):return 'CE'
    return None

def scan_events():
    records=announcement_records()
    universe=json.loads((CACHE/'universe.json').read_text())
    calendar=sorted(d for d,v in universe.items() if '_error' not in v)
    closes=json.loads((CACHE/'cash_closes.json').read_text())
    signals=[];gaps=[];counts=defaultdict(int)
    for file in sorted((CACHE/'underlying').glob('*.json')):
        symbol=file.stem
        if symbol not in records:continue
        rows=[Bar.parse(r) for r in json.loads(file.read_text())]
        byday=defaultdict(list)
        for bar in rows:byday[bar.start.date().isoformat()].append(bar)
        cumulative={}
        for day,bars in byday.items():
            total=0;out={}
            for b in bars:
                total+=b.volume;out[b.start.strftime('%H:%M')]=total
            cumulative[day]=out
        for day,bars in sorted(byday.items()):
            if not str(START)<=day<=str(END):continue
            idx=calendar.index(day) if day in calendar else 0
            prior=calendar[idx-1] if idx else None
            if prior is None or symbol not in universe.get(prior,{}):continue
            previous=closes.get(prior,{}).get(symbol,{}).get('close')
            if not previous:
                gaps.append({'symbol':symbol,'day':day,'reason':'MISSING_OFFICIAL_PREVIOUS_CLOSE'});continue
            reference=D(previous)
            # Corporate-action/reference discontinuity must be resolved, not treated as momentum.
            official_prev=closes.get(day,{}).get(symbol,{}).get('previous')
            if official_prev and abs(D(official_prev)/reference-1)>D('.01'):
                gaps.append({'symbol':symbol,'day':day,'reason':'CORPORATE_ACTION_REFERENCE_REQUIRES_AUDIT'});continue
            opening=bars[0].open;opened=bars[0].start
            prev_close_time=datetime.fromisoformat(prior+'T15:15:00+05:30' if prior>='2026-08-03' else prior+'T15:30:00+05:30')
            overnight=[e for e in records[symbol] if prev_close_time<=e['at']<opened and e['quality']!='OTHER']
            intraday=[e for e in records[symbol] if opened<=e['at']<opened.replace(hour=15,minute=10) and e['quality']!='OTHER']
            cohorts=[]
            if overnight:cohorts.append(('EVENT_CONTINUATION',overnight,reference,opened))
            for e in intraday:
                before=[b.close for b in bars if b.available<=e['at']][-5:]
                if len(before)==5:cohorts.append(('INTRADAY_EVENT',[e],median(before),e['at']))
            for engine,events,ref,start in cohorts:
                extreme_high=ref;extreme_low=ref
                for i,b in enumerate(bars):
                    if b.start<start:continue
                    if b.available.hour*60+b.available.minute>910:break
                    extreme_high=max(extreme_high,b.high);extreme_low=min(extreme_low,b.low)
                    # Three-minute futures return needs four completed bars.
                    # Before 09:19 it is not ready, rather than a missing record.
                    if i<3 or bars[i-2].start<start:continue
                    for direction in (1,-1):
                        if direction*(b.close/ref-1)<D('.025'):continue
                        histories=[cumulative.get(d,{}).get(b.start.strftime('%H:%M')) for d in calendar[max(0,idx-20):idx]]
                        if len(histories)!=20 or any(x is None for x in histories) or median(histories)<=0:
                            gaps.append({'symbol':symbol,'day':day,'reason':'MISSING_20_SESSION_RVOL','at':b.available.isoformat()});break
                        rvol=D(cumulative[day][b.start.strftime('%H:%M')])/D(median(histories))
                        extreme=extreme_high if direction>0 else extreme_low
                        if not event_rule(bars[i-2:i+1],ref,opening,rvol,extreme,direction,engine=='INTRADAY_EVENT'):continue
                        future_path=CACHE/'futures'/f'{symbol}_{day}.json'
                        future_status='PENDING'
                        if future_path.exists():
                            future=json.loads(future_path.read_text())
                            f={r[0]:r for r in future.get('bars',[])}
                            latest=f.get(b.start.isoformat()); earlier=f.get((b.start-timedelta(minutes=3)).isoformat())
                            if latest is None or earlier is None:
                                gaps.append({'symbol':symbol,'day':day,'reason':'MISSING_FUTURE_CONFIRMATION','at':b.available.isoformat()});continue
                            if direction*(D(str(latest[4]))-D(str(earlier[4])))<=0:continue
                            future_status='CONFIRMED'
                        good=[e for e in events if e['quality']=='QUALIFYING_TEXT']
                        chosen=good[0] if good else events[0]
                        signal={'id':f'{engine}:{symbol}:{b.available.isoformat()}', 'engine':engine,'symbol':symbol,
                            'at':b.available.isoformat(),'side':'CE' if direction>0 else 'PE','spot':str(b.close),
                            'reference':str(ref),'extreme':str(extreme),'rvol':str(rvol),
                            'event_id':chosen['id'],'event_at':chosen['at'].isoformat(),'event_category':chosen['category'],
                            'event_url':chosen['url'],'materiality':chosen['quality'],'futures_confirmation':future_status}
                        signals.append(signal);counts[engine]+=1
                        break
                    else:continue
                    if signals and signals[-1].get('id')==f'{engine}:{symbol}:{b.available.isoformat()}':break
    # Keep the first qualifying event signal per engine/symbol/session.
    unique={}
    for s in sorted(signals,key=lambda s:(s['at'],s['symbol'],s['event_id'])):
        unique.setdefault((s['engine'],s['symbol'],s['at'][:10]),s)
    save(CACHE/'event_candidates.json',list(unique.values()))
    save(CACHE/'event_gaps.json',gaps)
    print('event_price_candidates',len(unique),'gaps',len(gaps),'engines',dict(counts),flush=True)

if __name__=='__main__':scan_events()
