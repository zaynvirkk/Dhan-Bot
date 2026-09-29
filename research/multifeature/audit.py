"""Probe advertised data fields and retain response shapes, never credentials."""
import json,time
from datetime import datetime,timezone
from .providers import request,dhan_token,STORE,OUT
from research.gauntlet.data import save

def shape(x):
    if isinstance(x,dict):return {k:shape(v) for k,v in x.items()}
    if isinstance(x,list):return {'rows':len(x),'item':shape(x[0]) if x else None}
    return type(x).__name__

def main():
    probes=[('news','/v2/news?category=instrument_keys&instrument_keys=NSE_EQ%7CINE040H01021&page_size=5'),
        ('full_quote','/v3/market-quote/quotes?instrument_key=NSE_INDEX%7CNifty%2050'),
        ('option_chain','/v2/option/chain?instrument_key=NSE_INDEX%7CNifty%2050&expiry_date=2026-09-22'),
        ('pcr_history','/v2/market/pcr?instrument_key=NSE_INDEX%7CNifty%2050&expiry=2026-09-08&date=2026-09-08&bucket_interval=5'),
        ('oi_history','/v2/market/oi?instrument_key=NSE_INDEX%7CNifty%2050&expiry=2026-09-08&date=2026-09-08'),
        ('maxpain_history','/v2/market/max-pain?instrument_key=NSE_INDEX%7CNifty%2050&expiry=2026-09-08&date=2026-09-08&bucket_interval=5'),
        ('fii_history','/v2/market/fii?data_type=NSE_FO%7CINDEX_FUTURES&interval=1D&from=2026-06-01'),
        ('dii_history','/v2/market/dii?data_type=NSE_EQ%7CCASH&interval=1D&from=2026-06-01'),
        ('smartlist','/v2/market/smartlist/options?asset_type=INDEX&category=UNDER_10000&page_size=5')]
    out=[]
    for name,path in probes:
        r=request('upstox',path);out.append({'name':name,'provider':'upstox','path':path,'status':r['status'],'shape':shape(r.get('body'))})
        print(name,r['status'],str(shape(r.get('body')))[:260],flush=True);time.sleep(1.1)
    save(OUT/'capability_probes.json',{'at':datetime.now(timezone.utc).isoformat(),'probes':out,'market_closed':True})
    try:access=dhan_token()
    except Exception:
        save(OUT/'dhan_probe_status.json',{'status':'AUTH_REFRESH_UNAVAILABLE','historical_download_is_separate':True})
        return
    for name,path,body in [('dhan_chain','/v2/optionchain',{'UnderlyingScrip':13,'UnderlyingSeg':'IDX_I','Expiry':'2026-09-22'}),
        ('dhan_quote','/v2/marketfeed/quote',{'IDX_I':[13]})]:
        r=request('dhan',path,body,access);out.append({'name':name,'provider':'dhan','path':path,'status':r['status'],'shape':shape(r.get('body'))})
        print(name,r['status'],str(shape(r.get('body')))[:260],flush=True);time.sleep(3.1)
    save(OUT/'capability_probes.json',{'at':datetime.now(timezone.utc).isoformat(),'probes':out,'market_closed':True})

if __name__=='__main__':main()
