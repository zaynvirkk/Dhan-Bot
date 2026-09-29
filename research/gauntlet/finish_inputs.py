"""Complete bounded candidate datasets from collected, timestamped inputs."""
import json
from collections import Counter
from datetime import datetime
from .data import CACHE,save

def forced_candidates():
    candidates=[];counts=Counter();gaps=[]
    folder='nonexpiry_reconciled' if (CACHE/'nonexpiry_reconciliation.json').exists() else 'nonexpiry_completed_v2'
    for f in sorted((CACHE/folder).glob('*.json')):
        x=json.loads(f.read_text());job=x['job'];counts[x['status']]+=1
        if x['status'] not in ('CHECKED','CHECKED_RECONCILED'):gaps.append({'symbol':job['symbol'],'day':job['day'],'key':job['contract_key'],'reason':x['status']})
        for at in x['signals']:
            candidates.append({'id':f"NONEXPIRY_FORCED_FLOW:{job['contract_key']}:{at}",
                'engine':'NONEXPIRY_FORCED_FLOW','symbol':job['symbol'],'at':at,'side':job['side'],
                'spot':job['strike'],'reference':job['strike'],'extreme':job['strike'],
                'contract_key':job['contract_key'],'strike':job['strike'],'expiry':job['expiry'],
                'lot':job['lot'],'materiality':'NOT_REQUIRED','futures_confirmation':'NOT_REQUIRED',
                'variant':'EXACT_CONTRACT_REGULAR_SPOT_FORCED_FLOW','exit_rule':'STRIKE_CROSS_BACK'})
    candidates.sort(key=lambda x:(x['at'],x['symbol'],x['contract_key']))
    save(CACHE/'nonexpiry_candidates.json',candidates)
    save(CACHE/'nonexpiry_scan.json',{'status_counts':dict(counts),'signals':len(candidates),'gaps':gaps,
        'full_data_coverage':not gaps,'scope':'NSE exact-contract persistent strike crosses; seven-day stock expiry buffer'})
    print('forced candidates',len(candidates),'coverage',dict(counts))

if __name__=='__main__':forced_candidates()
