"""Collect historical universe, public announcements and all underlying bars."""
import argparse
import csv
import io
import json
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from .data import CACHE, public, save, candles

START = date(2026,7,20)
END = date(2026,9,18)
WARMUP = date(2026,6,15)

def universe_day(day):
    name = f'BhavCopy_NSE_FO_0_0_0_{day:%Y%m%d}_F_0000.csv.zip'
    try:
        raw = public('https://nsearchives.nseindia.com/content/fo/'+name, name)
        z = zipfile.ZipFile(io.BytesIO(raw))
        rows = list(csv.DictReader(io.StringIO(z.read(z.namelist()[0]).decode('utf-8-sig'))))
        return str(day), {r['TckrSymb']: r['FinInstrmTp'] for r in rows}
    except Exception as e:
        return str(day), {'_error':type(e).__name__+':'+str(e)}

def bootstrap():
    days = [WARMUP+timedelta(days=i) for i in range((END-WARMUP).days+1) if (WARMUP+timedelta(days=i)).weekday()<5]
    out = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        for day, values in pool.map(universe_day, days):
            out[day] = values
    save(CACHE/'universe.json', out)
    for start,end in [('01-07-2026','31-07-2026'),('01-08-2026','31-08-2026'),('01-09-2026','18-09-2026')]:
        name='announcements_'+start+'_'+end+'.json'
        raw=public(f'https://www.nseindia.com/api/corporate-announcements?index=equities&from_date={start}&to_date={end}',name)
        rows=json.loads(raw)
        print('announcements',start,len(rows),flush=True)
    master=json.loads((CACHE/'master.json').read_text())
    by_symbol={r['trading_symbol']:r['instrument_key'] for r in master if r.get('segment')=='NSE_EQ' and r.get('instrument_type')=='EQ'}
    by_symbol.update({r['trading_symbol']:r['instrument_key'] for r in master if r.get('segment')=='NSE_INDEX'})
    by_symbol.update({'NIFTY':'NSE_INDEX|Nifty 50','BANKNIFTY':'NSE_INDEX|Nifty Bank','FINNIFTY':'NSE_INDEX|Nifty Fin Service','MIDCPNIFTY':'NSE_INDEX|NIFTY MID SELECT','NIFTYNXT50':'NSE_INDEX|Nifty Next 50'})
    symbols=set().union(*(set(v) for v in out.values()))-{'_error'}
    # Current master is ONLY a key lookup. Historical membership comes from bhavcopies.
    keys={s:by_symbol.get(s) for s in sorted(symbols)}
    save(CACHE/'keys.json',keys)
    print('universe',len(symbols),'missing_keys',[s for s,k in keys.items() if k is None],
          'sessions',sum('_error' not in v for v in out.values()),'missing_days',[d for d,v in out.items() if '_error' in v],flush=True)

def download_symbol(symbol,key):
    file=CACHE/'underlying'/f'{symbol}.json'
    if file.exists():
        return symbol,len(json.loads(file.read_text())),'cached'
    rows=[]
    at=WARMUP
    try:
        while at<=END:
            until=min(at+timedelta(days=27),END)
            rows.extend(candles(key,str(at),str(until)))
            at=until+timedelta(days=1)
        # Duplicate timestamps with differing values must not be silently overwritten.
        seen={}
        for r in rows:
            if r[0] in seen and seen[r[0]]!=r:
                raise ValueError('conflicting candle')
            seen[r[0]]=r
        save(file,sorted(seen.values(),key=lambda r:r[0]))
        return symbol,len(seen),'ok'
    except Exception as e:
        return symbol,0,type(e).__name__+':'+str(e)

def underlying():
    keys=json.loads((CACHE/'keys.json').read_text())
    results=[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs=[pool.submit(download_symbol,s,k) for s,k in keys.items() if k]
        for job in as_completed(jobs):
            result=job.result(); results.append(result)
            print('underlying',len(results),'/',len(jobs),*result,flush=True)
            save(CACHE/'underlying_download.json',results)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['bootstrap','underlying']); a=p.parse_args()
    globals()[a.stage]()
