"""Replay the stated expiry rule on regular-spot data (CAS remains separate)."""
import json
from collections import defaultdict
from datetime import datetime,timedelta
from decimal import Decimal as D
from .core import Bar
from .data import CACHE,save
from .contracts import exchange_contracts,metadata,audited_option_bars,previous_session
from .signals import forced_rule
from .collect import START,END

def scan_expiry():
    universe=json.loads((CACHE/'universe.json').read_text())
    calendar=sorted(d for d,v in universe.items() if '_error' not in v and str(START)<=d<=str(END))
    prospects=[];gaps=[]
    for day in calendar:
        chain=[r for r in exchange_contracts(previous_session(day)) if r['FinInstrmTp']=='IDO' and (r.get('FininstrmActlXpryDt') or r['XpryDt'])==day]
        symbols=sorted(set(r['TckrSymb'] for r in chain))
        for symbol in symbols:
            file=CACHE/'underlying'/f'{symbol}.json'
            if not file.exists():gaps.append({'symbol':symbol,'day':day,'reason':'MISSING_UNDERLYING'});continue
            bars=[Bar.parse(r) for r in json.loads(file.read_text()) if r[0][:10]==day]
            if not bars:gaps.append({'symbol':symbol,'day':day,'reason':'MISSING_UNDERLYING_DAY'});continue
            for row in [r for r in chain if r['TckrSymb']==symbol]:
                c=metadata(row);sign=1 if c.side=='CE' else -1
                for i in range(3,len(bars)):
                    b=bars[i];minute=b.available.hour*60+b.available.minute
                    begin=880 if day>='2026-08-03' else 870
                    # Archived regular-spot candles are not auction IEP observations.
                    end=915 if day>='2026-08-03' else 925
                    if not begin<=minute<=end:continue
                    if sign*(bars[i-2].close-c.strike)<=0 and all(sign*(x.close-c.strike)>0 for x in bars[i-1:i+1]):
                        prospects.append((day,symbol,c,i,bars))
    print('expiry_crossings',len(prospects),'unique_contract_days',len(set((d,c.key) for d,s,c,i,b in prospects)),flush=True)
    signals=[];loaded={}
    for n,(day,symbol,c,i,underlying) in enumerate(prospects):
        try:
            key=(day,c.key)
            if key not in loaded:
                raw,audit=audited_option_bars(c.key,day)
                loaded[key]=sorted([Bar.parse(r) for r in raw],key=lambda b:b.start)
                if audit['status']!='EXACT_DAILY_VOLUME_RECONCILED':
                    gaps.append({'symbol':symbol,'day':day,'key':c.key,'reason':audit})
            at=underlying[i].available
            options=[b for b in loaded[key] if b.available<=at]
            if len(options)<33 or any(a.available!=b.start for a,b in zip(options[-33:],options[-32:])):
                gaps.append({'symbol':symbol,'day':day,'key':c.key,'at':at.isoformat(),'reason':'UNKNOWN_OPTION_LOOKBACK'})
                continue
            if forced_rule(underlying[:i+1],options,c.strike,c.side):
                signals.append({'id':f'EXPIRY_FORCED_FLOW:{symbol}:{c.key}:{at.isoformat()}',
                    'engine':'EXPIRY_FORCED_FLOW','symbol':symbol,'at':at.isoformat(),'side':c.side,
                    'spot':str(underlying[i].close),'reference':str(c.strike),'extreme':str(underlying[i].close),
                    'contract_key':c.key,'materiality':'NOT_REQUIRED','futures_confirmation':'NOT_REQUIRED',
                    'variant':'REGULAR_SPOT_ONLY','exit_rule':'STRIKE_CROSS_BACK','lot':c.lot,'strike':str(c.strike),'expiry':c.expiry})
        except Exception as e:gaps.append({'symbol':symbol,'day':day,'key':c.key,'reason':str(e)})
        if (n+1)%20==0:print('expiry_checked',n+1,'signals',len(signals),flush=True)
    save(CACHE/'expiry_candidates.json',signals)
    save(CACHE/'expiry_scan.json',{'crossings':len(prospects),'signals':len(signals),'gaps':gaps,
        'scope':'NSE indices present in historical files, regular-spot only; CAS indicative path unavailable'})
    print('expiry_complete','signals',len(signals),'gaps',len(gaps),flush=True)

if __name__=='__main__':scan_expiry()
