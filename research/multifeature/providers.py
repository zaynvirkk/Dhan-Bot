"""Bounded, cached, read-only provider requests. Never imports an order client."""
import asyncio, hashlib, json, os, shlex, time, threading
from datetime import datetime, timezone
from pathlib import Path
import httpx
from research.gauntlet.data import CACHE, ROOT, save, token
from dhan_cas_bot.auth import session_token

STORE=CACHE/'multifeature90'
OUT=ROOT/'research/results/multifeature90'
DHAN_PATHS={'/v2/charts/rollingoption','/v2/charts/intraday','/v2/optionchain','/v2/optionchain/expirylist','/v2/marketfeed/quote'}
UP_PATHS=('/v2/news?','/v2/market-quote/','/v3/market-quote/','/v2/option/','/v2/market-info/','/v2/market/','/v2/fundamentals/')
RATE_LOCK=threading.Lock()
NEXT_DHAN=0.

def environment():
    vals={}
    for line in (ROOT/'.env').read_text().splitlines():
        parts=shlex.split(line,comments=True)
        if parts and '=' in parts[0]:
            k,v=parts[0].split('=',1);vals[k]=v
    return vals

def dhan_token():
    # The old .env access token is stale. PIN/TOTP session issuance was already
    # authorized for read-only research. Secrets never enter result receipts.
    env=environment()
    os.environ.pop('DHAN_ACCESS_TOKEN',None)
    os.environ['DHAN_PIN']=env.get('DHAN_PIN','')
    os.environ['DHAN_TOTP_SECRET']=env.get('DHAN_TOTP_SECRET','')
    return asyncio.run(session_token({'account_id':env['DHAN_CLIENT_ID']},STORE/'auth'))

def request(provider,path,body=None,access=None):
    global NEXT_DHAN
    if provider not in ('dhan','upstox'):raise ValueError('unknown data provider')
    if provider=='dhan' and path not in DHAN_PATHS:raise ValueError('not a read-only Dhan data endpoint')
    if provider=='upstox' and not path.startswith(UP_PATHS):raise ValueError('not a read-only Upstox data endpoint')
    identity=json.dumps([provider,path,body],sort_keys=True)
    f=STORE/'api'/(hashlib.sha256(identity.encode()).hexdigest()+'.json')
    if f.exists():
        cached=json.loads(f.read_text())
        if cached.get('status')==200:return cached
    headers={'Accept':'application/json'}
    if provider=='dhan':
        headers['access-token']=access
        headers['client-id']=environment()['DHAN_CLIENT_ID']
    else:headers['Authorization']='Bearer '+token()
    host='https://api.dhan.co' if provider=='dhan' else 'https://api.upstox.com'
    for attempt in range(3):
        if provider=='dhan':
            with RATE_LOCK:
                wait=max(0.,NEXT_DHAN-time.monotonic())
                NEXT_DHAN=max(NEXT_DHAN,time.monotonic())+.26
            if wait:time.sleep(wait)
        start=time.monotonic()
        try:
            r=httpx.request('POST' if body is not None else 'GET',host+path,json=body,headers=headers,timeout=45)
            try:response=r.json()
            except ValueError:response={'non_json':True}
            receipt={'provider':provider,'path':path,'request':body,'status':r.status_code,'body':response,
                'retrieved_at':datetime.now(timezone.utc).isoformat(),'elapsed_ms':round((time.monotonic()-start)*1000),
                'sha256':hashlib.sha256(r.content).hexdigest()}
            if r.status_code not in (429,500,502,503,504):save(f,receipt);return receipt
        except httpx.HTTPError:
            receipt={'provider':provider,'path':path,'status':None,'error':'TRANSPORT_FAILURE'}
        time.sleep(2**attempt)
    save(f,receipt);return receipt

def rolling(start,end,offset,side,access):
    body={'exchangeSegment':'NSE_FNO','interval':'1','securityId':'13','instrument':'OPTIDX',
        'expiryFlag':'WEEK','expiryCode':1,'strike':'ATM' if offset==0 else f'ATM{offset:+d}',
        'drvOptionType':'CALL' if side=='CE' else 'PUT',
        'requiredData':['open','high','low','close','volume','oi','iv','strike','spot'],
        'fromDate':start,'toDate':end}
    return request('dhan','/v2/charts/rollingoption',body,access)
