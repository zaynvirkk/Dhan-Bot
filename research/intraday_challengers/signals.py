"""Signals have no access to option outcome bars or final session statistics."""
from datetime import timedelta
from statistics import median
from research.gauntlet.core import D
from research.expiry.signals import stamp

NEW = ('OPEN_DRIVE', 'GAP_FADE', 'FIRST_LAST', 'TREND_PULLBACK',
       'VOLUME_REVERSAL', 'SECTOR_CATCHUP', 'RANGE_FAILURE', 'AFTERNOON_COMPRESSION')
BENCH = ('CHAIN_UNWIND', 'SKEW_UNWIND')
NAMES = NEW + BENCH

class Missing(Exception): pass

def get(series, at):
    if at not in series: raise Missing('MISSING_COMPLETED_BAR:' + at.isoformat())
    return series[at]

def change(series, at, n):
    old = get(series, at - timedelta(minutes=n)).close
    if old <= 0: raise Missing('NONPOSITIVE_REFERENCE')
    return get(series, at).close / old - 1

def direction(x): return 1 if x > 0 else -1 if x < 0 else 0

def persistent(series, at, d):
    closes = [get(series, at - timedelta(minutes=i)).close for i in (2, 1, 0)]
    return all(d * (b-a) > 0 for a,b in zip(closes, closes[1:]))

def scan(day, spot, future, bank, it, prior_day):
    out = {}; gaps = {}
    previous_rows = [b for t,b in spot.items() if t.date().isoformat()==prior_day]
    previous_close = max(previous_rows,key=lambda b:b.available).close if previous_rows else None
    for minute in range(585, 886, 5):
        at = stamp(day, f'{minute//60:02}:{minute%60:02}')
        for name in NEW:
            if name in out or name in gaps: continue
            if name == 'OPEN_DRIVE' and minute > 630: continue
            if name == 'GAP_FADE' and minute > 690: continue
            if name == 'FIRST_LAST' and minute != 885: continue
            if name not in ('OPEN_DRIVE','GAP_FADE','FIRST_LAST') and minute < 600: continue
            if name == 'AFTERNOON_COMPRESSION' and minute < 810: continue
            try:
                now = get(spot, at).close; op = get(spot, stamp(day,'09:16')).open
                f5 = change(future, at, 5); d = 0; detail = {}
                if name == 'OPEN_DRIVE':
                    r = now/op-1; v = direction(r)
                    rows = [get(future, stamp(day,'09:16')+timedelta(minutes=i)) for i in range(minute-555)]
                    vol = sum(b.volume for b in rows)
                    if not vol: raise Missing('ZERO_FUTURE_VOLUME')
                    vwap = sum(((b.high+b.low+b.close)/3*b.volume for b in rows), D(0))/vol
                    if abs(r)>=D('.0035') and v*f5>0 and v*(get(future,at).close-vwap)>0 and persistent(spot,at,v): d=v
                    detail = {'open_return':str(r), 'future_vwap':str(vwap)}
                elif name == 'GAP_FADE':
                    if previous_close is None: raise Missing('MISSING_PRIOR_SESSION')
                    previous = previous_close
                    gap=op/previous-1; v=-direction(gap)
                    fraction=(op-now)/(op-previous) if op!=previous else D(0)
                    if abs(gap)>=D('.005') and D('.25')<=fraction<=1 and v*f5>0 and persistent(spot,at,v): d=v
                    detail={'gap':str(gap),'gap_fraction_filled':str(fraction)}
                elif name == 'FIRST_LAST':
                    r=get(spot,stamp(day,'09:45')).close/op-1;v=direction(r)
                    if abs(r)>=D('.002') and v*(now-op)>0 and v*f5>0 and persistent(spot,at,v): d=v
                    detail={'first_half_hour_return':str(r)}
                elif name == 'TREND_PULLBACK':
                    r=change(spot,at,30);pull=change(spot,at,10);v=direction(r)
                    if abs(r)>=D('.0025') and v*pull<0 and v*f5>0 and persistent(spot,at,v):d=v
                    detail={'trend_30m':str(r),'pullback_10m':str(pull)}
                elif name == 'VOLUME_REVERSAL':
                    r=change(spot,at,15);v=-direction(r)
                    rows=[get(future,at-timedelta(minutes=i)) for i in range(33)]
                    base=median(sum(b.volume for b in rows[i:i+3]) for i in range(3,33,3))
                    ratio=D(sum(b.volume for b in rows[:3]))/D(str(base)) if base else D(0)
                    if abs(r)>=D('.002') and ratio>=3 and v*change(future,at,1)>0 and persistent(spot,at,v):d=v
                    detail={'move_15m':str(r),'volume_ratio':str(ratio)}
                elif name == 'SECTOR_CATCHUP':
                    b=change(bank,at,15);i=change(it,at,15);s=change(spot,at,15);v=direction(b)
                    if abs(b)>=D('.002') and v*i>=D('.002') and v*s<min(abs(b),abs(i))/2 and v*f5>0 and persistent(spot,at,v):d=v
                    detail={'bank_15m':str(b),'it_15m':str(i),'spot_15m':str(s)}
                elif name == 'RANGE_FAILURE':
                    first=[get(spot,stamp(day,'09:16')+timedelta(minutes=i)) for i in range(30)]
                    high=max(b.high for b in first);low=min(b.low for b in first)
                    past=[get(spot,at-timedelta(minutes=i)).close for i in range(1,16)]
                    if low<=now<=high:
                        for v,failed in [(1,min(past)<low-now*D('.0005')),(-1,max(past)>high+now*D('.0005'))]:
                            if failed and v*f5>0 and persistent(spot,at,v):d=v;break
                    detail={'opening_high':str(high),'opening_low':str(low)}
                elif name == 'AFTERNOON_COMPRESSION':
                    past=[get(spot,at-timedelta(minutes=i)) for i in range(3,33)]
                    high=max(b.high for b in past);low=min(b.low for b in past)
                    latest=[get(spot,at-timedelta(minutes=i)).close for i in (2,1,0)]
                    if (high-low)/now<=D('.0015'):
                        if min(latest)>high and f5>0:d=1
                        elif max(latest)<low and f5<0:d=-1
                    detail={'compressed_high':str(high),'compressed_low':str(low)}
                if d: out[name]={'name':name,'at':at.isoformat(),'side':'CE' if d>0 else 'PE','spot':str(now),'detail':detail}
            except Missing as exc:gaps[name]=str(exc)
    return out,gaps
