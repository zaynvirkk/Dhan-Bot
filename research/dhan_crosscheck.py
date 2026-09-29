"""Read-only independent spot/option cross-check; no broker-order methods."""
import asyncio,json,os,shlex,hashlib
from datetime import datetime,timedelta,timezone
from pathlib import Path
import httpx
from dhan_cas_bot.auth import session_token
from research.gauntlet.data import CACHE,save
from research.gauntlet.contracts import instrument_bars

async def main():
    for line in Path('.env').read_text().splitlines():
        parts=shlex.split(line,comments=True)
        if parts and '=' in parts[0]:
            k,v=parts[0].split('=',1);os.environ[k]=v
    token=await session_token({'account_id':os.environ['DHAN_CLIENT_ID']},CACHE/'auth')
    signals=[s for s in json.loads((CACHE/'nonexpiry_candidates.json').read_text()) if s['symbol']=='NIFTY']
    results=[]
    async with httpx.AsyncClient(timeout=45) as client:
        for s in signals:
            day=s['at'][:10];end=(datetime.fromisoformat(day)+timedelta(days=1)).date().isoformat()
            rows=instrument_bars(s['contract_key'],day)
            stamp=(datetime.fromisoformat(s['at'])-timedelta(minutes=1)).isoformat()
            up=next(r for r in rows if r[0]==stamp)
            found=None
            for offset in ('ATM','ATM+1','ATM-1','ATM+2','ATM-2','ATM+3','ATM-3'):
                request={'exchangeSegment':'NSE_FNO','interval':'1','securityId':'13','instrument':'OPTIDX',
                    'expiryFlag':'WEEK','expiryCode':1,'strike':offset,'drvOptionType':'CALL' if s['side']=='CE' else 'PUT',
                    'requiredData':['open','high','low','close','volume','strike','oi','spot','iv'],'fromDate':day,'toDate':end}
                file=CACHE/'dhan_history'/(hashlib.sha256(json.dumps(request,sort_keys=True).encode()).hexdigest()+'.json')
                if file.exists():body=json.loads(file.read_text())['body']
                else:
                    r=await client.post('https://api.dhan.co/v2/charts/rollingoption',headers={'access-token':token},json=request)
                    body=r.json();save(file,{'request':request,'status':r.status_code,'body':body,'retrieved_at':datetime.now(timezone.utc).isoformat()})
                    if r.status_code!=200:raise RuntimeError('Dhan historical request failed: '+str(r.status_code))
                    await asyncio.sleep(1)
                x=body['data']['ce' if s['side']=='CE' else 'pe']
                epoch=int(datetime.fromisoformat(stamp).timestamp())
                for i,t in enumerate(x['timestamp']):
                    if t==epoch and float(x['strike'][i])==float(s['strike']):
                        found={k:x[k][i] for k in ('open','high','low','close','volume','oi','strike')};break
                if found:break
            results.append({'contract_key':s['contract_key'],'at':stamp,'upstox':up,'dhan':found,
                'close_difference':None if found is None else round(float(found['close'])-float(up[4]),6),
                'expiry_identity_note':'Dhan nearest weekly rolling route; strike and timestamp matched explicitly.'})
            print(day,'matched',found is not None,'close_difference',results[-1]['close_difference'],flush=True)
    save(CACHE/'cross_broker_audit.json',{'results':results,'scope':'Four NIFTY signal minutes; not full-market certification.'})

if __name__=='__main__':asyncio.run(main())
