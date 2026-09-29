"""Fetch every candidate's confirmation inputs without examining its outcome."""
import json
from concurrent.futures import ThreadPoolExecutor,as_completed
from .data import CACHE,save
from .contracts import future_key,instrument_bars

def future_job(symbol,day):
    file=CACHE/'futures'/f'{symbol}_{day}.json'
    if file.exists():return symbol,day,'cached'
    try:
        key=future_key(symbol,day)
        if not key:return symbol,day,'UNKNOWN_CONTRACT'
        bars=instrument_bars(key,day)
        save(file,{'key':key,'bars':bars})
        return symbol,day,len(bars)
    except Exception as e:return symbol,day,type(e).__name__+':'+str(e)

if __name__=='__main__':
    rows=json.loads((CACHE/'event_candidates.json').read_text())
    jobs=sorted(set((s['symbol'],s['at'][:10]) for s in rows))
    with ThreadPoolExecutor(max_workers=3) as pool:
        for result in pool.map(lambda args:future_job(*args),jobs):print('future',*result,flush=True)
