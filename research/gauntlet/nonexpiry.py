"""Resumable full NSE non-expiry crossing queue, without winner selection."""
import argparse,bisect,json
from collections import defaultdict
from datetime import datetime,timedelta,date,timezone
from decimal import Decimal as D
from .data import CACHE,save
from .contracts import exchange_contracts,previous_session,metadata,instrument_bars
from .core import Bar
from .signals import forced_rule
from .collect import START,END
from .option_history import plan_ranges,fetch_range
from functools import lru_cache

@lru_cache(maxsize=4)
def underlying_days(symbol):
    byday=defaultdict(list)
    for r in json.loads((CACHE/'underlying'/f'{symbol}.json').read_text()):
        byday[r[0][:10]].append(Bar.parse(r))
    return byday

def build():
    keys=json.loads((CACHE/'keys.json').read_text())
    underlying={}
    for symbol in keys:
        f=CACHE/'underlying'/f'{symbol}.json'
        if not f.exists():continue
        byday=defaultdict(list)
        for r in json.loads(f.read_text()):
            if str(START)<=r[0][:10]<=str(END):byday[r[0][:10]].append(r)
        underlying[symbol]=byday
    universe=json.loads((CACHE/'universe.json').read_text())
    days=sorted(d for d,v in universe.items() if '_error' not in v and str(START)<=d<=str(END))
    jobs={}
    for day in days:
        grouped=defaultdict(list)
        for r in exchange_contracts(previous_session(day)):
            if r['FinInstrmTp'] not in ('STO','IDO'):continue
            exp=r.get('FininstrmActlXpryDt') or r['XpryDt']
            days_left=(date.fromisoformat(exp)-date.fromisoformat(day)).days
            if days_left<=(0 if r['FinInstrmTp']=='IDO' else 7):continue
            grouped[r['TckrSymb']].append(r)
        for symbol,chain in grouped.items():
            rows=underlying.get(symbol,{}).get(day,[])
            if len(rows)<34:continue
            exp=min(r.get('FininstrmActlXpryDt') or r['XpryDt'] for r in chain)
            contracts={(D(r['StrkPric']),r['OptnTp']):r for r in chain if (r.get('FininstrmActlXpryDt') or r['XpryDt'])==exp}
            strikes=sorted(set(k[0] for k in contracts))
            for i in range(33,len(rows)):
                if rows[i][0][11:16]>'15:09':break
                a,b,c=[D(str(r[4])) for r in rows[i-2:i+1]]
                ce=strikes[bisect.bisect_left(strikes,a):bisect.bisect_left(strikes,min(b,c))] if min(b,c)>a else []
                pe=strikes[bisect.bisect_right(strikes,max(b,c)):bisect.bisect_right(strikes,a)] if max(b,c)<a else []
                for side,levels in [('CE',ce),('PE',pe)]:
                    for strike in levels:
                        row=contracts.get((strike,side))
                        if row is None:continue
                        contract=metadata(row);key=day+':'+contract.key
                        j=jobs.setdefault(key,{'day':day,'symbol':symbol,'contract_key':contract.key,'side':side,'strike':str(strike),
                            'lot':contract.lot,'expiry':contract.expiry,'cross_bar_starts':[]})
                        j['cross_bar_starts'].append(rows[i][0])
        print('queued',day,len(jobs),flush=True)
    save(CACHE/'nonexpiry_jobs.json',list(jobs.values()))
    print('nonexpiry_jobs',len(jobs),'minimum_api_seconds',round(len(jobs)*1.05),flush=True)

def completed_path(job):
    name=job['day']+'_'+job['contract_key'].replace('|','_')+'.json'
    return CACHE/'nonexpiry_completed_v2'/name

def check_job(job):
    result={'job':job,'status':'CHECKED','signals':[]}
    try:
        options=sorted([Bar.parse(r) for r in instrument_bars(job['contract_key'],job['day'])],key=lambda b:b.start)
        u=underlying_days(job['symbol']).get(job['day'],[])
        for stamp in job['cross_bar_starts']:
            at=datetime.fromisoformat(stamp)+timedelta(minutes=1)
            visible=[b for b in options if b.available<=at]
            if not visible or visible[-1].available!=at:
                result['status']='UNKNOWN_OPTION_CROSS_BAR';continue
            if len(visible)<33 or any(a.available!=b.start for a,b in zip(visible[-33:],visible[-32:])):
                result['status']='UNKNOWN_OPTION_LOOKBACK';continue
            if forced_rule([b for b in u if b.available<=at],visible,D(job['strike']),job['side']):
                result['signals'].append(at.isoformat())
    except Exception as e:
        result['status']='UNKNOWN';result['error']=type(e).__name__+':'+str(e)
    save(completed_path(job),result)
    return result

def run(limit,batch=False,workers=4):
    from concurrent.futures import ThreadPoolExecutor,wait,FIRST_COMPLETED
    jobs=json.loads((CACHE/'nonexpiry_jobs.json').read_text())
    completed=CACHE/'nonexpiry_completed_v2';completed.mkdir(exist_ok=True)
    done={p.name for p in completed.glob('*.json')}
    remaining=[j for j in jobs if completed_path(j).name not in done][:limit]
    ranges=plan_ranges(jobs)
    grouped=defaultdict(list)
    plan_by_day={(p['key'],d):n for n,p in enumerate(ranges) for d in p['days']}
    for j in remaining:grouped[plan_by_day[(j['contract_key'],j['day'])]].append(j)
    tasks=iter(grouped.items())
    save(CACHE/'option_range_plan.json',ranges)
    count=0;failures=0;initial=len(done);stopped=False
    progress=CACHE/'nonexpiry_progress.json'
    def checkpoint(status):
        save(progress,{'status':status,'updated_at':datetime.now(timezone.utc).isoformat(),
            'total_contract_days':len(jobs),'completed_contract_days':initial+count,
            'planned_range_requests':len(ranges),'batch_limit':limit,'batch_processed':count,
            'batched_downloads':batch,'workers':workers})
    def process(task):
        n,group=task
        try:
            if batch:fetch_range(ranges[n])
        except Exception as e:
            # A failed source is not an empty market. Keep the range retryable.
            return [],type(e).__name__+':'+str(e)
        return [check_job(j) for j in group],None
    checkpoint('RUNNING')
    with ThreadPoolExecutor(max_workers=workers) as pool:
        pending=set()
        for _ in range(workers):
            task=next(tasks,None)
            if task is not None:pending.add(pool.submit(process,task))
        while pending:
            finished,pending=wait(pending,return_when=FIRST_COMPLETED)
            for future in finished:
                results,error=future.result()
                count+=len(results)
                failures=failures+1 if error else 0
                checkpoint('RUNNING')
                print('nonexpiry_checked',initial+count,'of',len(jobs),'range_error',error,flush=True)
                if failures>=3 or error and any(code in error for code in ('HTTP 401','HTTP 403')):
                    stopped=True
                if not stopped:
                    task=next(tasks,None)
                    if task is not None:pending.add(pool.submit(process,task))
    checkpoint('STOPPED_SOURCE_ERRORS' if stopped else 'BATCH_COMPLETE')
    print('nonexpiry_batch_complete',count,flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['build','run']);p.add_argument('--limit',type=int,default=100);p.add_argument('--batch',action='store_true');p.add_argument('--workers',type=int,choices=range(1,5),default=4);a=p.parse_args()
    build() if a.stage=='build' else run(a.limit,a.batch,a.workers)
