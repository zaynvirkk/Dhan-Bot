"""Point-in-time contracts from the previous published exchange bhavcopy."""
from __future__ import annotations
import csv,io,json,zipfile
from datetime import date
from functools import lru_cache
from decimal import Decimal as D
from .core import Contract
from .data import CACHE,candles,save,contracts,upstox
from urllib.parse import quote

@lru_cache(maxsize=4)
def exchange_contracts(day):
    path=CACHE/'public'/('BhavCopy_NSE_FO_0_0_0_'+day.replace('-','')+'_F_0000.csv.zip')
    with zipfile.ZipFile(path) as z:
        return list(csv.DictReader(io.StringIO(z.read(z.namelist()[0]).decode('utf-8-sig'))))

@lru_cache(maxsize=128)
def previous_session(day):
    u=json.loads((CACHE/'universe.json').read_text())
    return max(d for d,v in u.items() if d<day and '_error' not in v)

def metadata(row):
    expiry=row.get('FininstrmActlXpryDt') or row['XpryDt']
    base='NSE_FO|'+row['FinInstrmId']
    key=base+'|'+date.fromisoformat(expiry).strftime('%d-%m-%Y') if expiry<'2026-09-19' else base
    index=row['FinInstrmTp']=='IDO'
    # Bhavcopy supplies actual date's lot. Tick/freeze absent: use conservative
    # research tick .05 and ONE LOT per child; exact metadata audit remains.
    lot=int(row['NewBrdLotQty'])
    return Contract(key,row['TckrSymb'],expiry,row['OptnTp'],D(row['StrkPric']),lot,D('.05'),lot,index)

def option_candidates(symbol,day,spot,side,delivery_buffer=True):
    prior=previous_session(day)
    rows=[r for r in exchange_contracts(prior) if r['TckrSymb']==symbol and r['FinInstrmTp'] in ('STO','IDO') and r['OptnTp']==side]
    eligible=[]
    for r in rows:
        c=metadata(r);days=(date.fromisoformat(c.expiry)-date.fromisoformat(day)).days
        if c.index and days>=0:eligible.append(c)
        # E-4 delivery margins cannot be priced from premium alone. Exclude
        # entire pre-expiry week in this conservative, explicitly named variant.
        elif not c.index and days>(7 if delivery_buffer else 0):eligible.append(c)
    if not eligible:return []
    exp=min(c.expiry for c in eligible)
    chain=sorted([c for c in eligible if c.expiry==exp],key=lambda c:c.strike)
    atm=min(chain,key=lambda c:(abs(c.strike-spot),c.strike)).strike
    ordered=sorted([c for c in chain if (c.strike>=atm if side=='CE' else c.strike<=atm)],key=lambda c:abs(c.strike-atm))
    return ordered[:11]

def execution_contract(contract):
    # Resolve each candidate only when the selector reaches it. A missing
    # far-away strike cannot invalidate an earlier, fully known chosen strike.
    meta=exact_metadata(contract.symbol,contract.expiry).get(contract.key)
    if meta is None:raise ValueError('missing exact historical contract metadata: '+contract.key)
    if int(meta['lot_size'])!=contract.lot:raise ValueError('historical lot discrepancy')
    return Contract.parse(meta)

@lru_cache(maxsize=8)
def eod_contracts(day):
    return {r['FinInstrmId']:r for r in exchange_contracts(day)}

def confirmed_no_trades(key,day):
    # Audit only: an official zero-trade day proves that missing candles cannot
    # hide our required three traded-liquidity minutes. It supplies no signal,
    # price, position size or favorable fill from the future.
    from .tape import record
    row=record(key,day)
    return row is not None and row[3]==0 and row[4]==0

def exact_signal_contract(signal):
    row=next((r for r in exchange_contracts(previous_session(signal['at'][:10]))
              if r['FinInstrmTp'] in ('STO','IDO') and metadata(r).key==signal['contract_key']),None)
    if row is None:raise ValueError('signal contract absent from prior universe')
    return metadata(row)

@lru_cache(maxsize=512)
def exact_metadata(symbol,expiry):
    keys=json.loads((CACHE/'keys.json').read_text());key=keys[symbol]
    if expiry<'2026-09-19':rows=contracts(key,expiry)
    else:rows=upstox('/v2/option/contract?instrument_key='+quote(key,safe='')+'&expiry_date='+expiry)
    return {r['instrument_key']:r for r in rows}

def instrument_bars(key,day):
    from .option_history import day_path
    cached=day_path(key,day)
    if cached.exists():
        saved=json.loads(cached.read_text())
        if saved['key']!=key or saved['day']!=day:raise ValueError('option day cache identity mismatch')
        return saved['bars']
    return candles(key,day,day,len(key.split('|'))==3)

def audited_option_bars(key,day):
    from .tape import normalize
    return normalize(key,day,instrument_bars(key,day))

def future_key(symbol,day):
    rows=[r for r in exchange_contracts(previous_session(day)) if r['TckrSymb']==symbol and r['FinInstrmTp'] in ('STF','IDF') and r['XpryDt']>=day]
    if not rows:return None
    row=min(rows,key=lambda r:r['XpryDt']);exp=row['XpryDt'];key='NSE_FO|'+row['FinInstrmId']
    return key+'|'+date.fromisoformat(exp).strftime('%d-%m-%Y') if exp<'2026-09-19' else key
