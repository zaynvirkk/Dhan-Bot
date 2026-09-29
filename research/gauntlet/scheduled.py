"""RBI-only scheduled-volatility subvariant; fixed prior-event comparison."""
import json
from datetime import datetime,timedelta
from decimal import Decimal as D
from statistics import median
from .data import CACHE,save,candles
from .core import Bar,snapshot
from .contracts import option_candidates,execution_contract,instrument_bars
from .signals import scheduled_vol_rule

PRIOR=('2025-04-09','2025-06-06','2025-08-06','2025-10-01','2025-12-05','2026-02-06','2026-04-08','2026-06-05')
DAY='2026-08-05'
SOURCES={
 'schedule':'https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=62422',
 'time':'https://www.linkedin.com/posts/reservebankofindia_rbi-rbimonetarypolicy-rbipressconference-activity-7490272970263707648-AXQM',
 'prior_dates':['https://rbidocs.rbi.org.in/rdocs/PressRelease/PDFs/PR61C1724B25DB7646DFB49022F184DF3766.PDF',
 'https://rbidocs.rbi.org.in/rdocs/PressRelease/PDFs/PR4894AE68CD2090049E59CE684ED07792E4E.PDF']+
 ['https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid='+str(x) for x in (60957,61332,61749,62169,62515,62863)]}

def scan():
    keys=json.loads((CACHE/'keys.json').read_text());results=[]
    at=datetime.fromisoformat(DAY+'T09:30:00+05:30');event=at+timedelta(minutes=30)
    for symbol in ('NIFTY','BANKNIFTY'):
        prior=[]
        for day in PRIOR:
            rows=candles(keys[symbol],day,day)
            prices={r[0][11:16]:D(str(r[4])) for r in rows if r[0][:10]==day}
            if '09:29' not in prices or '10:29' not in prices:raise ValueError('missing RBI comparison bar '+symbol+' '+day)
            prior.append({'date':day,'absolute_move':str(abs(prices['10:29']/prices['09:29']-1))})
        under=[Bar.parse(r) for r in json.loads((CACHE/'underlying'/f'{symbol}.json').read_text()) if r[0][:10]==DAY]
        spot=snapshot(under,at)[-1].close;legs=[]
        for side in ('CE','PE'):
            c=execution_contract(option_candidates(symbol,DAY,spot,side)[0])
            bars=sorted([Bar.parse(r) for r in instrument_bars(c.key,DAY)],key=lambda b:b.start)
            known=snapshot(bars,at)
            if not known or known[-1].available!=at:raise ValueError('missing RBI option decision bar')
            legs.append({'key':c.key,'strike':str(c.strike),'premium':str(known[-1].close),'lot':c.lot})
        if legs[0]['strike']!=legs[1]['strike']:raise ValueError('straddle strikes disagree')
        cost=sum(D(l['premium']) for l in legs)
        move=median(D(p['absolute_move']) for p in prior)
        qualifies=scheduled_vol_rule(datetime.fromisoformat('2026-08-04T23:59:59+05:30'),at,event,cost,spot,[D(p['absolute_move']) for p in prior])
        results.append({'symbol':symbol,'decision_at':at.isoformat(),'event_at':event.isoformat(),'prior_events':prior,
            'spot':str(spot),'straddle_premium':str(cost),'straddle_over_spot':str(cost/spot),
            'max_qualifying_premium':str(spot*D('.75')*move),'signal':qualifies,'legs':legs,
            'one_lot_premium':str(cost*legs[0]['lot'])})
        print('scheduled',symbol,'signal',qualifies,'premium',cost,'threshold',spot*D('.75')*move,flush=True)
    save(CACHE/'scheduled_scan.json',{'engine':'SCHEDULED_EVENT_VOL','variant':'RBI_NIFTY_BANKNIFTY_ONLY',
        'sources':SOURCES,'results':results,'signals':sum(r['signal'] for r in results),
        'scope':'Scheduled RBI decision only; other earnings/macro calendars not silently imputed.'})
    if any(r['signal'] for r in results):raise RuntimeError('qualifying straddle requires full two-leg execution replay')
    save(CACHE/'scheduled_candidates.json',[])

if __name__=='__main__':scan()
