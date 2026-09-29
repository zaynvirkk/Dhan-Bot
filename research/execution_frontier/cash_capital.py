"""Complete only the missing cash-margin probes; no order routes."""
import asyncio
import csv
import hashlib
import json
import time
from datetime import datetime, timezone

import httpx

from dhan_cas_bot.auth import resolve_dhan_access_token
from research.gauntlet.core import D
from research.gauntlet.data import save
from research.multifeature.providers import environment
from .capital import STORE
from .replay import OUT


def main():
    out={'checked_at':datetime.now(timezone.utc).isoformat(),'orders_submitted':0,
         'historical_margin_evidence':False,'checks':[],'requests':[],'status':'UNKNOWN'}
    env=environment()
    try:
        token=asyncio.run(resolve_dhan_access_token(env['DHAN_CLIENT_ID'],pin=env['DHAN_PIN'],
                                                   totp_secret=env['DHAN_TOTP_SECRET']))
        headers={'access-token':token,'client-id':env['DHAN_CLIENT_ID']}
        def request(path,body=None):
            if path not in ('/v2/fundlimit','/v2/marketfeed/quote','/v2/margincalculator'):
                raise ValueError('READ_ONLY_ALLOWLIST')
            r=httpx.request('GET' if body is None else 'POST','https://api.dhan.co'+path,
                            headers=headers,json=body,timeout=30)
            x=r.json()
            out['requests'].append({'path':path,'http_status':r.status_code,
                                    'sha256':hashlib.sha256(r.content).hexdigest()})
            save(OUT/'cash_capital.json',out)
            if r.status_code!=200: raise ValueError('BROKER_READ_FAILED')
            time.sleep(1.1)
            return x
        funds=request('/v2/fundlimit')
        cash=D(str(funds.get('availabelBalance',funds.get('availableBalance'))))
        out['available_balance']=str(cash)
        p=STORE/'master.csv'; out['master_sha256']=hashlib.sha256(p.read_bytes()).hexdigest()
        rows=list(csv.DictReader(p.open()))
        syms=('RELIANCE','HDFCBANK','SBIN','INFY','TCS')
        chosen=[]
        for sym in syms:
            found=[r for r in rows if r['EXCH_ID']=='NSE' and r['SEGMENT']=='E'
                   and r['SERIES']=='EQ' and r['UNDERLYING_SYMBOL']==sym]
            if len(found)!=1: raise ValueError('AMBIGUOUS_EQUITY_METADATA')
            chosen.append(found[0])
        quotes=request('/v2/marketfeed/quote',{'NSE_EQ':[int(r['SECURITY_ID']) for r in chosen]})['data']['NSE_EQ']
        for r in chosen:
            price=D(str(quotes[r['SECURITY_ID']]['last_price']))
            if price<=0: raise ValueError('UNKNOWN_PRICE')
            q=int(cash*4/price)
            if not q: raise ValueError('ZERO_QUANTITY')
            for side in ('BUY','SELL'):
                body={'exchangeSegment':'NSE_EQ','transactionType':side,'quantity':q,'productType':'INTRADAY',
                      'securityId':r['SECURITY_ID'],'price':float(price)}
                margin=request('/v2/margincalculator',{**body,'dhanClientId':env['DHAN_CLIENT_ID']})
                total=margin.get('totalMargin')
                out['checks'].append({'name':r['UNDERLYING_SYMBOL']+'_CASH_4X_'+side,
                                      'request':body,'margin':margin,'notional':str(price*q),
                                      'reported_margin':str(total) if total is not None else None,
                                      'fits_cash':D(str(total))<=cash if total is not None else None})
                save(OUT/'cash_capital.json',out)
                print(out['checks'][-1]['name'],total,flush=True)
        out['status']='READS_SUCCEEDED'
    except Exception as e:
        out['error_type']=type(e).__name__
        safe=('Dhan authentication account mismatch','Dhan token endpoint returned no accessToken',
              'Dhan access-token request failed; verify network, PIN/TOTP setup and auth endpoint')
        out['error']=str(e) if str(e) in safe else 'REDACTED_READ_FAILURE'
        print('CASH_PROBES_UNKNOWN',out['error_type'],out['error'],flush=True)
    save(OUT/'cash_capital.json',out)


if __name__=='__main__': main()
