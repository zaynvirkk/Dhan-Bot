"""Bounded Dhan checks of selected NIFTY decision/entry/exit minutes."""
import asyncio,json,hashlib,time
from datetime import date,datetime,timedelta,timezone
from decimal import ROUND_HALF_UP
import httpx
from dhan_cas_bot.auth import resolve_dhan_access_token
from research.multifeature.providers import environment
from research.gauntlet.data import CACHE,save
from research.gauntlet.core import Contract,Bar,D
from research.gauntlet.option_history import day_path
from .prepare import OUT,STORE,calendar
from .options import exchange

def main():
    results=json.loads((OUT/'options.json').read_text());plan=json.loads((STORE/'signals.json').read_text());meta=json.loads((STORE/'contracts.json').read_text())
    spot={r[0]:r for r in json.loads((CACHE/'expiry_research/spot.json').read_text())};days=calendar();jobs=[]
    for r in results['runs']:
        if r['strategy']!='NIFTY_SELLOFF_REBOUND_1510' or r['scenario']!='primary':continue
        for row in r['ledger']:
            if row['status']!='RESOLVED':continue
            s=plan[row['day']]['signals'][r['strategy']]
            c=Contract.parse(next(m for m in meta['|'.join((row['day'],'NIFTY',s['exit_day'],'CE'))]['contracts'] if m.get('instrument_key')==row['contract']))
            for label,at in [('decision',datetime.fromisoformat(row['signal_at'])-timedelta(minutes=1)),('entry',datetime.fromisoformat(row['entry_at'])),('exit',datetime.fromisoformat(row['exit_parts'][-1]['at']))]:
                d=at.date().isoformat();prior=days[days.index(d)-1]
                expiries=sorted({x.get('FininstrmActlXpryDt') or x['XpryDt'] for x in exchange(prior) if x['TckrSymb']=='NIFTY' and x['FinInstrmTp']=='IDO' and (x.get('FininstrmActlXpryDt') or x['XpryDt'])>=d})
                code=expiries.index(c.expiry)+1;price=D(str(spot[at.isoformat()][4]));atm=(price/50).quantize(D(1),rounding=ROUND_HALF_UP)*50;offset=int((c.strike-atm)/50)
                jobs.append((r['period'],row['day'],label,c,at,code,offset))
    env=environment();access=asyncio.run(resolve_dhan_access_token(env['DHAN_CLIENT_ID'],pin=env['DHAN_PIN'],totp_secret=env['DHAN_TOTP_SECRET']))
    out=[];count=0
    for period,signal_day,label,c,at,code,offset in jobs:
        found=None;paths=[]
        for k in (offset,offset-1,offset+1):
            if abs(k)>10:continue
            d=at.date().isoformat();body={'exchangeSegment':'NSE_FNO','interval':'1','securityId':'13','instrument':'OPTIDX','expiryFlag':'WEEK','expiryCode':code,
                'strike':'ATM' if k==0 else f'ATM{k:+d}','drvOptionType':'CALL','requiredData':['open','high','low','close','volume','oi','strike','spot'],
                'fromDate':d,'toDate':(date.fromisoformat(d)+timedelta(days=1)).isoformat()}
            f=STORE/'dhan_selected'/(hashlib.sha256(json.dumps(body,sort_keys=True).encode()).hexdigest()+'.json');paths.append(str(f.relative_to(CACHE)))
            if f.exists():receipt=json.loads(f.read_text())
            else:
                response=httpx.post('https://api.dhan.co/v2/charts/rollingoption',headers={'access-token':access,'client-id':env['DHAN_CLIENT_ID']},json=body,timeout=30)
                receipt={'request':body,'status':response.status_code,'body':response.json(),'at':datetime.now(timezone.utc).isoformat(),'sha256':hashlib.sha256(response.content).hexdigest()};save(f,receipt);count+=1;time.sleep(.3)
            x=receipt.get('body',{}).get('data',{}).get('ce') or {}
            for i,t in enumerate(x.get('timestamp',[])):
                if t==int(at.timestamp()) and D(str(x['strike'][i]))==c.strike:
                    found={field:x[field][i] for field in ('open','high','low','close','volume','oi','strike')};break
            if found:break
        up=next(x for x in json.loads(day_path(c.key,at.date().isoformat()).read_text())['bars'] if x[0]==at.isoformat())
        differences=None if found is None else {field:str(D(str(found[field]))-D(str(up[i]))) for field,i in [('open',1),('high',2),('low',3),('close',4),('volume',5),('oi',6)]}
        out.append({'period':period,'signal_day':signal_day,'label':label,'at':at.isoformat(),'key':c.key,'expiry':c.expiry,'expiry_code':code,'strike':str(c.strike),'dhan':found,'upstox':up,'differences':differences,'receipts':paths})
        print(period,signal_day,label,'matched',found is not None,flush=True)
    save(OUT/'crosscheck.json',{'scope':'Selected decision, entry and final exit minutes only; not full tape or order-book validation. Expiry mapped to prior published index contract calendar and Dhan weekly expiryCode; strike and timestamp explicitly matched.','new_requests':count,'rows':out})
    summarize()

def summarize():
    p=OUT/'crosscheck.json';x=json.loads(p.read_text());results=json.loads((OUT/'options.json').read_text())
    trades={(r['period'],v['day']):v for r in results['runs'] if r['scenario']=='primary' and r['strategy']=='NIFTY_SELLOFF_REBOUND_1510' for v in r['ledger'] if v['status']=='RESOLVED'}
    for r in x['rows']:
        v=trades[r['period'],r['signal_day']];d=r['dhan']
        if d is None or r['label']=='decision':continue
        q=v['quantity'] if r['label']=='entry' else v['exit_parts'][-1]['quantity']
        r['dhan_snapshot_capacity_pass']=D(q)<=D(str(d['volume']))*D('.05')
        if r['label']=='entry':r['dhan_high_below_submitted_limit']=D(str(d['high']))<=D(v['limit'])
    x['ohlc_exact']=sum(r['differences'] is not None and all(D(r['differences'][f])==0 for f in ('open','high','low','close')) for r in x['rows'])
    x['max_absolute_differences']={f:str(max(abs(D(r['differences'][f])) for r in x['rows'] if r['differences'])) for f in ('open','high','low','close','volume','oi')}
    files={CACHE/f for r in x['rows'] for f in r['receipts']}
    x['receipt_hashes']={str(f.relative_to(CACHE)):hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(files)}
    save(p,x)

if __name__=='__main__':
    try:main()
    except Exception as e:print('CROSSCHECK_STOPPED',type(e).__name__,flush=True);raise SystemExit(1)
