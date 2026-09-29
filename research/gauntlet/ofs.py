"""OFS-only subvariant using an exchange filing visually read before replay."""
from collections import defaultdict
from datetime import datetime,date
from decimal import Decimal as D
from statistics import median
import json
from .core import Bar
from .data import CACHE,save
from .signals import ofs_rule

def scan():
    # Original NSE notice, received publicly 2026-08-03 21:04:40 IST.
    # Pages 1-2: date and base size; page 6 item 11: INR 382 floor.
    # Optional oversubscription is deliberately excluded from base-day sizing.
    term={'symbol':'LICI','published':'2026-08-03T21:04:40+05:30','floor':'382',
          'base_shares':316249885,'sessions':['2026-08-04','2026-08-05'],
          'source':'https://nsearchives.nseindia.com/corporate/tchari_03082026210047_LICI_OFSNOTICE.pdf',
          'pages':[1,2,6],'extraction':'visually read original scan, no price-outcome labels'}
    rows=[Bar.parse(r) for r in json.loads((CACHE/'underlying/LICI.json').read_text())]
    byday=defaultdict(list)
    for b in rows:byday[b.start.date().isoformat()].append(b)
    days=sorted(byday);close=json.loads((CACHE/'cash_closes.json').read_text())
    reference=D(close['2026-08-03']['LICI']['close'])
    signals=[];sessions=[]
    for day in term['sessions']:
        idx=days.index(day);past=days[idx-20:idx]
        cum={}
        adv=[]
        for d in past:
            total=0;c={};value=D(0)
            for b in byday[d]:
                total+=b.volume;c[b.start.strftime('%H:%M')]=total;value+=b.close*b.volume
            cum[d]=c;adv.append(value)
        mean_adv=sum(adv)/20
        event={'available_at':datetime.fromisoformat(term['published']), 'effective_date':date.fromisoformat(day),
               'floor':D(term['floor']),'reference':reference,'offer_value':D(term['base_shares'])*D(term['floor'])}
        bars=byday[day];total=0;fired=False
        for i,b in enumerate(bars):
            total+=b.volume
            if i<2 or b.available.hour*60+b.available.minute>910:continue
            denominator=median(cum[d][b.start.strftime('%H:%M')] for d in past)
            if denominator<=0:continue
            rvol=D(total)/D(denominator)
            side=ofs_rule(event,bars[i-2:i+1],rvol,mean_adv)
            if side:
                signals.append({'id':f'BLOCK_OFS_DISLOCATION:LICI:{b.available.isoformat()}','engine':'BLOCK_OFS_DISLOCATION',
                   'symbol':'LICI','at':b.available.isoformat(),'side':side,'spot':str(b.close),'reference':str(reference),
                   'extreme':str(b.close),'materiality':'NOT_REQUIRED','futures_confirmation':'NOT_REQUIRED',
                   'variant':'NSE_ANNOUNCED_OFS_ONLY','event_url':term['source'],'event_at':term['published'],'rvol':str(rvol)})
                fired=True;break
        sessions.append({'date':day,'triggered':fired,'base_offer_over_adv':str(event['offer_value']/mean_adv)})
    save(CACHE/'ofs_candidates.json',signals)
    save(CACHE/'ofs_scan.json',{'terms':term,'sessions':sessions,'signals':len(signals),
        'scope':'NSE metadata announcements with explicit OFS terms; preannounced block deals not comprehensively classified'})
    print('OFS',sessions,'signals',len(signals))

if __name__=='__main__':scan()
