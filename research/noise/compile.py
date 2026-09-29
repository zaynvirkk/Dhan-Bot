"""Compile market observations once, without selecting contracts from outcomes."""
import argparse
import hashlib
import json
from dataclasses import asdict
from datetime import datetime
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal as D

from research.gauntlet.data import CACHE, save
from research.gauntlet.core import Bar
from research.gauntlet.contracts import (option_candidates,exact_signal_contract,
    confirmed_no_trades,audited_option_bars,execution_contract)
from research.gauntlet.replay import SOURCES,invalidate
from research.gauntlet.provenance import source_manifest,digest

NOISE=CACHE/'noise'

def adapted(signal,side):
    s=dict(signal)
    if side!=s['side']:
        s['side']=side;s['extreme']=str(2*D(s['reference'])-D(s['extreme']))
        s.pop('contract_key',None)
    return s

@lru_cache(maxsize=4)
def underlying(symbol):
    return json.loads((CACHE/'underlying'/f'{symbol}.json').read_text())

def compile_one(args):
    signal,side=args;s=adapted(signal,side)
    name=hashlib.sha256((s['id']+':'+side).encode()).hexdigest()+'.json'
    file=NOISE/'compiled'/name
    source_sha=source_manifest()['sha256']
    spec_sha=digest(__file__)
    if file.exists():
        x=json.loads(file.read_text())
        if x['signal']==s and x['source_sha']==source_sha and x['compiler_sha']==spec_sha:return x
    x={'signal':s,'source_sha':source_sha,'compiler_sha':spec_sha,'contracts':[]}
    if s['materiality'] not in ('QUALIFYING_TEXT','NOT_REQUIRED'):
        x['excluded']='OUTSIDE_METADATA_VARIANT';save(file,x);return x
    day=s['at'][:10];at=datetime.fromisoformat(s['at'])
    try:
        u=[Bar.parse(r) for r in underlying(s['symbol']) if r[0][:10]==day]
        inv=invalidate(s,u,at)
        x['invalid_at']=inv.isoformat() if inv is not None else None
        chain=[exact_signal_contract(s)] if 'contract_key' in s else option_candidates(s['symbol'],day,D(s['spot']),s['side'])
        for c in chain:
            item={'key':c.key}
            try:
                if confirmed_no_trades(c.key,day):item['skip']='OFFICIAL_ZERO_TRADES_AUDIT'
                else:
                    bars,audit=audited_option_bars(c.key,day)
                    item.update(bars=bars,audit=audit)
                    # Metadata errors occur only when this contract is reached.
                    # Known missing quotes must remain distinguishable.
                    if any(Bar.parse(r).available<=at for r in bars):
                        item['contract']={k:str(v) if isinstance(v,D) else v for k,v in asdict(execution_contract(c)).items()}
            except Exception as e:item['error']=type(e).__name__+':'+str(e)
            x['contracts'].append(item)
    except Exception as e:x['error']=type(e).__name__+':'+str(e)
    save(file,x)
    return x

def run():
    for engine,source in SOURCES.items():
        signals=sorted([s for s in json.loads((CACHE/source).read_text()) if s['engine']==engine],
                       key=lambda s:(s['at'],s['symbol'],s['side']))
        compiled=[]
        with ThreadPoolExecutor(max_workers=3) as pool:
            for i,x in enumerate(pool.map(compile_one,[(s,side) for s in signals for side in ('CE','PE')]),1):
                compiled.append(x)
                if i%20==0:print('COMPILE',engine,i,'/',len(signals)*2,flush=True)
        save(NOISE/(engine+'_compiled.json'),{'engine':engine,'signals':signals,'observations':compiled,
            'source_sha':source_manifest()['sha256'],'input_sha':digest(CACHE/source),
            'compiler_sha':digest(__file__),'ban_sha':digest(CACHE/'ban_lists.json')})
        print('COMPILE_FINISHED',engine,len(signals),flush=True)

if __name__=='__main__':run()
