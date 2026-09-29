"""Causal signal definitions. No access to forward option returns."""
from datetime import datetime, timedelta
from decimal import Decimal as D
from statistics import median

NAMES = ('ORB30','LATE_BREAK','LATE_FADE','TREND1445','OPTION_ACCEL','OPTION_ACCEL_OI')

def stamp(day, hm):
    return datetime.fromisoformat(day+'T'+hm+':00+05:30')

def contiguous(bars):
    return bool(bars) and all(a.available==b.start for a,b in zip(bars,bars[1:]))

def signal(name, at, side, spot, detail):
    return {'name':name,'at':at.isoformat(),'side':side,'spot':str(spot),'detail':detail}

def spot_signals(bars, day):
    """A missing window fails closed even if a later favorable signal exists."""
    bars=sorted(bars,key=lambda b:b.start)
    out={}; gaps=[]
    for name,begin,end,finish in [('ORB30','09:15','09:45','12:00'),
                                ('LATE_BREAK','14:15','14:30','15:14' if day>='2026-08-03' else '15:24')]:
        box=[b for b in bars if stamp(day,begin)<=b.start<stamp(day,end)]
        expected=int((stamp(day,end)-stamp(day,begin)).total_seconds()/60)
        scan=[b for b in bars if stamp(day,end)<=b.start and b.available<=stamp(day,finish)]
        if len(box)!=expected or not contiguous(box) or not scan or scan[0].start!=stamp(day,end) or not contiguous(scan) or scan[-1].available!=stamp(day,finish):
            gaps.append(name+':MISSING_SPOT_WINDOW');continue
        hi=max(b.high for b in box);lo=min(b.low for b in box)
        breached=None
        for i,b in enumerate(scan):
            if i:
                prev=scan[i-1]
                side='CE' if min(prev.close,b.close)>=hi+5 else 'PE' if max(prev.close,b.close)<=lo-5 else None
                if side and name not in out:out[name]=signal(name,b.available,side,b.close,{'box_high':str(hi),'box_low':str(lo)})
                if name=='LATE_BREAK' and breached and 'LATE_FADE' not in out and lo<=prev.close<=hi and lo<=b.close<=hi:
                    out['LATE_FADE']=signal('LATE_FADE',b.available,'PE' if breached=='CE' else 'CE',b.close,{'first_break':breached})
            if name=='LATE_BREAK' and breached is None:
                if b.close>=hi+5:breached='CE'
                elif b.close<=lo-5:breached='PE'
    if any(g.startswith('LATE_BREAK:') for g in gaps):gaps.append('LATE_FADE:MISSING_SPOT_WINDOW')
    look=[b for b in bars if stamp(day,'13:44')<=b.start<stamp(day,'14:45')]
    if len(look)!=61 or not contiguous(look):gaps.append('TREND1445:MISSING_SPOT_WINDOW')
    else:
        prices=[b.close for b in look]; change=prices[-1]-prices[-16]
        path=sum(abs(y-x) for x,y in zip(prices[-16:],prices[-15:]))
        if abs(change/prices[-16])>=D('.001') and change*(prices[-1]-prices[0])>0 and path and abs(change)/path>=D('.60'):
            out['TREND1445']=signal('TREND1445',stamp(day,'14:45'),'CE' if change>0 else 'PE',prices[-1],{'efficiency':str(abs(change)/path)})
    anchor=next((b.close for b in bars if b.available==stamp(day,'14:45')),None)
    return out,gaps,anchor

def option_signals(by_side, day, anchor):
    out={}; gaps=[]
    maps={s:{b.available:b for b in rows} for s,rows in by_side.items()}
    at=stamp(day,'14:45'); end=stamp(day,'15:30' if day>='2026-08-03' else '15:20')
    blocked=set()
    while at<=end:
        qualifying=[]
        for side in ('CE','PE'):
            seq=[maps.get(side,{}).get(at-timedelta(minutes=j)) for j in range(32,-1,-1)]
            if any(b is None for b in seq):
                # If either leg is missing, we cannot know which fired first.
                for name in ('OPTION_ACCEL','OPTION_ACCEL_OI'):
                    if name not in out and name not in blocked:
                        gaps.append(name+':MISSING_OPTION_LOOKBACK');blocked.add(name)
                continue
            if seq[-4].close<=0:continue
            ret=seq[-1].close/seq[-4].close-1
            past=[sum(b.volume for b in seq[i:i+3]) for i in range(0,30,3)]
            base=D(str(median(past))); vol=sum(b.volume for b in seq[-3:])
            if ret>=D('.25') and base>0 and vol>=2*base:
                oi=seq[-4].oi>0 and D(seq[-1].oi)/seq[-4].oi<=D('.92')
                qualifying.append((ret,side,oi))
        for name in ('OPTION_ACCEL','OPTION_ACCEL_OI'):
            rows=[r for r in qualifying if name=='OPTION_ACCEL' or r[2]]
            if rows and name not in out and name not in blocked:
                ret,side,oi=sorted(rows,key=lambda x:(-x[0],x[1]))[0]
                out[name]=signal(name,at,side,anchor,{'anchor_time':'14:45','premium_return_3m':str(ret),'oi_unwind':oi})
        at+=timedelta(minutes=1)
    return out,gaps
