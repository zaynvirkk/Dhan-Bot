"""Bounded read-only broker feasibility survey; never imports order placement."""
import csv
import hashlib
import json
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import httpx

from research.gauntlet.core import D
from research.gauntlet.data import CACHE, save
from research.multifeature.providers import environment
from research.rebound_validation.dhan_history import access
from .replay import OUT

STORE = CACHE/'execution_frontier'
ALLOWED = {'/v2/fundlimit', '/v2/positions', '/v2/marketfeed/quote',
           '/v2/margincalculator', '/v2/margincalculator/multi'}


def main():
    env = environment(); token = access()
    headers = {'access-token': token, 'client-id': env['DHAN_CLIENT_ID']}
    receipts = []; checks = []
    out = {'checked_at': datetime.now(timezone.utc).isoformat(), 'market_hours_execution_evidence': False,
           'orders_submitted': 0, 'checks': checks}
    def request(path, body=None):
        if path not in ALLOWED: raise ValueError('READ_ONLY_ALLOWLIST')
        r = httpx.request('POST' if body is not None else 'GET', 'https://api.dhan.co'+path,
                          headers=headers, json=body, timeout=30)
        try: data = r.json()
        except ValueError: data = {'error': 'NON_JSON'}
        def redact(x):
            if isinstance(x, dict): return {k:redact(v) for k,v in x.items() if 'clientid' not in k.lower()}
            if isinstance(x, list): return [redact(v) for v in x]
            return x
        safe = redact(data)
        if path == '/v2/positions': safe = {'count': len(data)} if isinstance(data,list) else {'error':'UNKNOWN'}
        receipts.append({'at':datetime.now(timezone.utc).isoformat(), 'path':path, 'request':redact(body),
                         'http_status':r.status_code, 'response':safe, 'sha256':hashlib.sha256(r.content).hexdigest()})
        save(STORE/'capital_requests.json', receipts)
        time.sleep(1.1)
        if r.status_code != 200: raise ValueError('BROKER_READ_HTTP_'+str(r.status_code))
        return data
    funds = request('/v2/fundlimit'); positions = request('/v2/positions')
    cash = D(str(funds.get('availabelBalance', funds.get('availableBalance'))))
    out.update(available_balance=str(cash), positions_count=len(positions))
    r = httpx.get('https://images.dhan.co/api-data/api-scrip-master-detailed.csv', timeout=60)
    r.raise_for_status(); STORE.mkdir(parents=True, exist_ok=True)
    (STORE/'master.csv').write_bytes(r.content)
    out['master_sha256'] = hashlib.sha256(r.content).hexdigest()
    rows = list(csv.DictReader(r.text.splitlines()))
    today = datetime.now(ZoneInfo('Asia/Kolkata')).date().isoformat()
    futs = [x for x in rows if x['EXCH_ID']=='NSE' and x['INSTRUMENT'].startswith('FUT') and x['SM_EXPIRY_DATE']>today]
    near = {}
    for x in futs:
        sym=x['UNDERLYING_SYMBOL']
        if sym not in near or x['SM_EXPIRY_DATE'] < near[sym]['SM_EXPIRY_DATE']: near[sym]=x
    commodities=[]
    for sym in ('GOLDPETAL','GOLDTEN','GOLDM','SILVERMIC','CRUDEOILM','NATGASMINI'):
        eligible=[x for x in rows if x['EXCH_ID']=='MCX' and x['UNDERLYING_SYMBOL']==sym
                  and x['INSTRUMENT'].startswith('FUT') and x['SM_EXPIRY_DATE']>='2026-10-15']
        if eligible: commodities.append(min(eligible,key=lambda x:x['SM_EXPIRY_DATE']))
    def segment(x): return 'MCX_COMM' if x['EXCH_ID']=='MCX' else 'NSE_EQ' if x['SEGMENT']=='E' else 'NSE_FNO'
    equity=[]
    for sym in ('RELIANCE','HDFCBANK','SBIN','INFY','TCS'):
        eligible=[x for x in rows if x['EXCH_ID']=='NSE' and x['SEGMENT']=='E' and x['SERIES']=='EQ'
                  and x['UNDERLYING_SYMBOL']==sym]
        if eligible: equity.append(eligible[0])
    if len(equity) != 5: raise ValueError('MISSING_EQUITY_METADATA')
    body={}
    for x in list(near.values())+commodities+equity: body.setdefault(segment(x),[]).append(int(x['SECURITY_ID']))
    quotes=request('/v2/marketfeed/quote',body)['data']
    def price(x): return D(str(quotes.get(segment(x),{}).get(x['SECURITY_ID'],{}).get('last_price',0)))
    def leg(x,side,quantity=None,product='MARGIN'):
        p=price(x)
        if p<=0: raise ValueError('UNKNOWN_QUOTE')
        return {'exchangeSegment':segment(x),'transactionType':side,
                'quantity':quantity if quantity is not None else int(D(x['LOT_SIZE'])),
                'productType':product,'securityId':x['SECURITY_ID'],'price':float(p)}
    def margin(legs):
        if len(legs)==1: return request('/v2/margincalculator',{**legs[0],'dhanClientId':env['DHAN_CLIENT_ID']})
        return request('/v2/margincalculator/multi',{'dhanClientId':env['DHAN_CLIENT_ID'],
                'includePosition':False,'includeOrder':False,'scripList':legs})
    def check(name,xs,sides,quantity=None,product='MARGIN'):
        rec={'name':name,'contracts':[x['DISPLAY_NAME'] for x in xs], 'product':product}
        try:
            legs=[leg(x,side,quantity,product) for x,side in zip(xs,sides)]
            m=margin(legs); rec.update(legs=legs, margin=m)
            total=m.get('totalMargin',m.get('data',{}).get('totalMargin'))
            rec['reported_margin']=str(total) if total is not None else None
            rec['basket_fits_cash']=D(str(total))<=cash if total is not None else None
            # The long hedge must itself fit before introducing a short leg.
            buys=[v for v in legs if v['transactionType']=='BUY']
            if len(xs)>1 and buys:
                initial=margin(buys[:1]); rec['first_hedge_margin']=initial
                value=initial.get('totalMargin',initial.get('data',{}).get('totalMargin'))
                rec['first_hedge_fits_cash']=D(str(value))<=cash if value is not None else None
            rec['historical_feasibility']='UNKNOWN'
        except Exception as e: rec['error_type']=type(e).__name__
        checks.append(rec); save(OUT/'capital.json',out)
        print(name,rec.get('reported_margin'),rec.get('basket_fits_cash'),rec.get('error_type'),flush=True)
    indices=[x for x in near.values() if x['INSTRUMENT']=='FUTIDX']
    stocks=sorted((x for x in near.values() if x['INSTRUMENT']=='FUTSTK' and price(x)>0),
                  key=lambda x:price(x)*D(x['LOT_SIZE']))[:10]
    out['quoted_stock_futures']=sum(x['INSTRUMENT']=='FUTSTK' and price(x)>0 for x in near.values())
    for x in indices+stocks+commodities: check(x['UNDERLYING_SYMBOL']+'_FUTURE',[x],['BUY'])
    for future in indices:
        sym=future['UNDERLYING_SYMBOL']; p=price(future)
        eligible=[x for x in rows if x['EXCH_ID']=='NSE' and x['UNDERLYING_SYMBOL']==sym
                  and x['INSTRUMENT']=='OPTIDX' and x['SM_EXPIRY_DATE']>today]
        if not eligible or p<=0: continue
        expiry=min(x['SM_EXPIRY_DATE'] for x in eligible)
        options=[x for x in eligible if x['SM_EXPIRY_DATE']==expiry]
        strikes=sorted({D(x['STRIKE_PRICE']) for x in options}); atm=min(strikes,key=lambda k:abs(k-p))
        i=strikes.index(atm)
        if i==0 or i+1>=len(strikes): continue
        wanted=[(atm,'CE'),(strikes[i+1],'CE'),(atm,'PE'),(strikes[i-1],'PE')]
        xs=[next(x for x in options if D(x['STRIKE_PRICE'])==k and x['OPTION_TYPE']==side) for k,side in wanted]
        quotes.setdefault('NSE_FNO',{}).update(request('/v2/marketfeed/quote',{'NSE_FNO':[int(x['SECURITY_ID']) for x in xs]})['data']['NSE_FNO'])
        for kind, subset in [('CALL',xs[:2]),('PUT',xs[2:])]:
            check(sym+'_'+kind+'_DEBIT',subset,['BUY','SELL'])
            # Buy the hedge first in the requested order; then introduce short.
            check(sym+'_'+kind+'_CREDIT',subset[::-1],['BUY','SELL'])
    for x in equity:
        if price(x)<=0: continue
        q=int(cash*4/price(x))
        if q:
            for side in ('BUY','SELL'): check(x['UNDERLYING_SYMBOL']+'_CASH_4X_'+side,[x],[side],q,'INTRADAY')
    out['request_receipts_sha256']=hashlib.sha256((STORE/'capital_requests.json').read_bytes()).hexdigest()
    save(OUT/'capital.json',out)


if __name__ == '__main__':
    try: main()
    except Exception as e:
        print('FEASIBILITY_STOPPED',type(e).__name__,flush=True)
        raise SystemExit(1)
