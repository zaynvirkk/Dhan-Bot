"""Exact contracts from prior NSE files. Historical data, never live orders."""
import argparse,json,hashlib
from collections import Counter
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import date,timedelta
from functools import lru_cache
from urllib.parse import quote
from research.gauntlet.data import CACHE,save,contracts,upstox,candles
from research.gauntlet.core import Contract,D,Bar
from research.expiry.signals import stamp
from research.gauntlet.contracts import metadata
from research.gauntlet.option_history import day_path,fetch_range,split_rows
from research.gauntlet.tape import normalize
from .prepare import STORE,OUT,calendar,raw_rows

@lru_cache(maxsize=8)
def exchange(day):
    name=f'BhavCopy_NSE_FO_0_0_0_{day.replace("-", "")}_F_0000.csv.zip'
    p=CACHE/'public'/name
    if not p.exists():p=CACHE/'event90/public'/name
    return raw_rows(p)

@lru_cache(maxsize=256)
def exact(key,expiry):
    return contracts(key,expiry) if expiry<'2026-09-19' else upstox('/v2/option/contract?instrument_key='+quote(key,safe='')+'&expiry_date='+expiry)

def candidates(signal,side):
    days=calendar();day=signal['day'];prior=days[days.index(day)-1];stock=signal['mode']=='CALL5'
    rows=[r for r in exchange(prior) if r['TckrSymb']==signal['symbol'] and r['FinInstrmTp']==('STO' if stock else 'IDO') and r['OptnTp']==side]
    eligible=[]
    for row in rows:
        c=metadata(row);buffer=(date.fromisoformat(c.expiry)-date.fromisoformat(signal['exit_day'])).days
        if buffer>(7 if stock else 0):eligible.append(c)
    if not eligible:return []
    expiry=min(c.expiry for c in eligible);chain=[c for c in eligible if c.expiry==expiry];spot=D(signal['spot'])
    atm=min(chain,key=lambda c:(abs(c.strike-spot),c.strike)).strike
    chain=sorted([c for c in chain if c.strike>=atm] if side=='CE' else [c for c in chain if c.strike<=atm],key=lambda c:abs(c.strike-atm))[:11 if stock else 4]
    if stock:chain=[c for c in chain if abs(c.strike/spot-1)<=D('.10')]
    metas={r['instrument_key']:r for r in exact(signal['key'],expiry)};out=[]
    for c in chain:
        m=metas.get(c.key)
        if m is None:
            # Resolve only if selection actually reaches this strike. A missing
            # farther strike cannot erase an earlier known affordable contract.
            out.append({'unresolved_key':c.key});continue
        parsed=Contract.parse(m)
        if parsed.lot!=c.lot or parsed.strike!=c.strike or parsed.side!=c.side:raise ValueError('CONTRACT_DISAGREEMENT')
        out.append(m)
    return out

def prepare():
    plan=json.loads((STORE/'signals.json').read_text());jobs={}
    for day,x in plan.items():
        for s in x['signals'].values():
            if s['mode'].startswith('CASH'):continue
            for side in ('CE','PE') if s['mode']=='INDEX' else ('CE',):
                key=(day,s['symbol'],s['exit_day'],side);jobs.setdefault(key,s)
    out={};count=Counter()
    def build(item):
        key,s=item
        try:return key,{'contracts':candidates(s,key[-1])}
        except Exception as e:return key,{'error':str(e)}
    with ThreadPoolExecutor(max_workers=3) as pool:
        for i,(key,result) in enumerate(pool.map(build,jobs.items()),1):
            out['|'.join(key)]=result;count.update(['ERROR' if 'error' in result else 'READY'])
            if i%30==0:print('contract selections',i,'/',len(jobs),dict(count),flush=True)
    save(STORE/'contracts.json',out);print('contracts done',len(out),dict(count),flush=True)

def pull_contract(c,start,end):
    """One exact contract per requested interval, cached in existing licensed store."""
    days=[d for d in calendar() if start<=d<=end]
    missing=[d for d in days if not day_path(c.key,d).exists()]
    if missing:
        requested=history_key(c,date.today().isoformat())
        if requested==c.key:fetch_range({'key':c.key,'days':missing})
        else:
            rows=candles(requested,missing[0],missing[-1],True)
            for day,values in split_rows(rows,missing).items():
                save(day_path(c.key,day),{'key':c.key,'request_key':requested,'day':day,
                    'requested_start':missing[0],'requested_end':missing[-1],'bars':values,
                    'status':'DOWNLOADED' if values else 'EMPTY_RESPONSE'})

def history_key(c,collected_on):
    # Cached metadata can predate expiry; the historical route must follow the
    # exact same exchange token/expiry when that active contract has expired.
    if len(c.key.split('|'))==2 and c.expiry<collected_on:
        return c.key+'|'+date.fromisoformat(c.expiry).strftime('%d-%m-%Y')
    return c.key

@lru_cache(maxsize=4096)
def option_day(key,day,tick):
    file=day_path(key,day)
    if not file.exists():raise ValueError('MISSING_OPTION_DAY')
    raw=json.loads(file.read_text());assert raw['key']==key and raw['day']==day
    rows=raw['bars'];actual=sum(int(r[5]) for r in rows)
    row=next((r for r in exchange(day) if r['FinInstrmId']==key.split('|')[1]),None)
    if row is None:raise ValueError('MISSING_OFFICIAL_CONTRACT')
    expected=int(row['TtlTradgVol'])*int(row['NewBrdLotQty']);issues=[]
    if actual!=expected:issues.append('VOLUME_MISMATCH')
    bars=[Bar.parse(r) for r in rows]
    if any(getattr(b,p)%tick for b in bars for p in ('open','high','low','close')):issues.append('OFF_TICK')
    # Fill only verified no-trade minutes, carrying past quotes with zero volume.
    if actual==expected:
        by={b.start:b for b in bars};out=[];last=None;at=stamp(day,'09:15')
        days=calendar();prior=days[days.index(day)-1]
        previous=next((r for r in exchange(prior) if r['FinInstrmId']==key.split('|')[1]),None)
        if previous and D(previous['ClsPric'])>0:
            p=D(previous['ClsPric']);last=Bar(at-timedelta(minutes=1),p,p,p,p,0,int(previous['OpnIntrst']))
        while at.strftime('%H:%M')<'15:16':
            b=by.get(at)
            if b is not None:last=b
            elif last is not None:b=Bar(at,last.close,last.close,last.close,last.close,0,last.oi)
            if b:out.append(b)
            at+=timedelta(minutes=1)
        bars=out
    return bars,issues

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['prepare']);p.parse_args();prepare()
