"""MSCI Standard August review: evaluate necessary price/volume conditions.

No fabricated fund-flow estimates. A failed necessary condition is a known
rejection; a passed condition with missing flow magnitude remains unknown.
"""
import json
from collections import defaultdict
from datetime import datetime
from decimal import Decimal as D
from statistics import median
from .data import CACHE,save,public
from .core import Bar

CHANGES={'ADANIENSOL':1,'GROWW':1,'LAURUSLABS':1,'LENSKART':1,'ASTRAL':-1,'BALKRISIND':-1,'SBICARD':-1}
SOURCE='https://www.msci.com/eqb/gimi/stdindex/MSCI_Aug26_STPublicList.pdf'

def scan():
    public(SOURCE,'MSCI_Aug26_STPublicList.pdf')
    universe=json.loads((CACHE/'universe.json').read_text());previous='2026-08-28';day='2026-08-31'
    results=[];unknown=[]
    for symbol,direction in CHANGES.items():
        if symbol not in universe[previous]:
            results.append({'symbol':symbol,'status':'NOT_IN_PRIOR_NSE_FO_UNIVERSE'});continue
        rows=[Bar.parse(r) for r in json.loads((CACHE/'underlying'/f'{symbol}.json').read_text())]
        byday=defaultdict(list)
        for b in rows:byday[b.start.date().isoformat()].append(b)
        past=sorted(d for d in byday if d<day)[-20:];cumulative={}
        if len(past)!=20:raise ValueError('missing pre-rebalance volume history')
        for d in past:
            total=0;cumulative[d]={}
            for b in byday[d]:total+=b.volume;cumulative[d][b.start.strftime('%H:%M')]=total
        bars=byday[day];opening=[b for b in bars if b.start.hour==9 and b.start.minute<30]
        boundary=max(b.high for b in opening) if direction>0 else min(b.low for b in opening)
        total=0;prospects=[]
        for i,b in enumerate(bars):
            total+=b.volume
            if not '14:30'<=b.available.strftime('%H:%M')<='15:10' or i<2:continue
            baseline=median(cumulative[d][b.start.strftime('%H:%M')] for d in past)
            if baseline<=0:continue
            rvol=D(total)/D(baseline)
            if rvol>=3 and all(direction*(x.close-boundary)>0 for x in bars[i-2:i+1]):
                prospects.append({'at':b.available.isoformat(),'rvol':str(rvol)})
        status='UNKNOWN_FLOW_MAGNITUDE' if prospects else 'REJECTED_PRICE_VOLUME_NECESSARY_CONDITION'
        results.append({'symbol':symbol,'direction':direction,'status':status,'possible_minutes':prospects})
        if prospects:unknown.append(symbol)
        print('passive',symbol,status,flush=True)
    save(CACHE/'passive_scan.json',{'engine':'PASSIVE_FLOW','variant':'MSCI_STANDARD_AUGUST_ONLY',
        'source':SOURCE,'announcement_date':'2026-08-12','effective_close':day,'results':results,
        'unknown_flow_symbols':unknown,'fully_rejected_subvariant':not unknown,
        'scope':'Constituent additions/deletions only; intra-index weight changes and other index families incomplete.'})
    save(CACHE/'passive_candidates.json',[])

if __name__=='__main__':scan()
