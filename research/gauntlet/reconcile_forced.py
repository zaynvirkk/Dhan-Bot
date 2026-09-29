"""Audit every scanned option day and repair only verified no-trade gaps."""
import json
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta
from decimal import Decimal as D
from .data import CACHE,save
from .core import Bar
from .signals import forced_rule
from .contracts import audited_option_bars
from .nonexpiry import underlying_days

def check(path):
    x=json.loads(path.read_text());j=x['job']
    destination=CACHE/'nonexpiry_reconciled'/path.name
    if destination.exists():return json.loads(destination.read_text())
    raw,audit=audited_option_bars(j['contract_key'],j['day'])
    x['audit']=audit
    if audit['status']!='EXACT_DAILY_VOLUME_RECONCILED':
        x['status']='UNKNOWN_VOLUME_RECONCILIATION'
    else:
        options=sorted([Bar.parse(r) for r in raw],key=lambda b:b.start)
        underlying=underlying_days(j['symbol']).get(j['day'],[])
        x['signals']=[];x['status']='CHECKED_RECONCILED'
        for stamp in j['cross_bar_starts']:
            at=datetime.fromisoformat(stamp)+timedelta(minutes=1)
            o=[b for b in options if b.available<=at];u=[b for b in underlying if b.available<=at]
            if len(o)<33 or any(a.available!=b.start for a,b in zip(o[-33:],o[-32:])):
                x['status']='UNKNOWN_OPTION_LOOKBACK';continue
            if forced_rule(u,o,D(j['strike']),j['side']):x['signals'].append(at.isoformat())
    save(destination,x)
    return x

def run():
    paths=sorted((CACHE/'nonexpiry_completed_v2').glob('*.json'))
    counts=Counter();signals=0
    with ThreadPoolExecutor(max_workers=4) as pool:
        for i,x in enumerate(pool.map(check,paths),1):
            counts[x['status']]+=1;signals+=len(x['signals'])
            if i%500==0:print('reconciled',i,'of',len(paths),'signals',signals,dict(counts),flush=True)
    save(CACHE/'nonexpiry_reconciliation.json',{'contract_days':len(paths),'counts':dict(counts),'signals':signals})
    print('reconciliation_complete',dict(counts),'signals',signals,flush=True)

if __name__=='__main__':run()
