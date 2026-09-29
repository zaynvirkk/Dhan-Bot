"""Bounded finishing sweep: each strategy keeps an independent bankroll."""
import argparse,json,time
from concurrent.futures import ThreadPoolExecutor,as_completed
from decimal import Decimal as D
from datetime import datetime,timezone
from research.gauntlet.data import CACHE,save
from research.gauntlet.replay import replay,SOURCES
from research.gauntlet.finish_inputs import forced_candidates
from research.gauntlet.provenance import source_manifest,digest

def resume_or_replay(engine,**kwargs):
    delay=kwargs.get('delay',1);adverse=kwargs.get('adverse',True)
    skip=kwargs.get('skip_id');control=kwargs.get('control');seed=kwargs.get('seed',0)
    suffix=f'v5_{engine}_{delay}_{"high" if adverse else "open"}'+('_delete_best' if skip else '')+(f'_random_{seed}' if control else '')
    path=CACHE/'results'/(suffix+'.json')
    if path.exists():
        r=json.loads(path.read_text())
        deleted=[x['signal']['id'] for x in r['ledger'] if x['status']=='BEST_TRADE_DELETED']
        if (r['source_manifest']['sha256']==source_manifest()['sha256'] and
            not r['source_drift_during_run'] and
            r['signal_input_sha256']==digest(CACHE/SOURCES[engine]) and
            r['ban_lists_sha256']==digest(CACHE/'ban_lists.json') and
            deleted==([skip] if skip else [])):
            print('RESUMED_COMPLETED',suffix,flush=True)
            return r
    return replay(engine,**kwargs)

def run_one(engine):
    baseline=resume_or_replay(engine)
    trades=[r for r in baseline['ledger'] if r['status']=='MODELED_ROUND_TRIP']
    if trades:
        best=max(trades,key=lambda r:D(r['net_pnl']))
        resume_or_replay(engine,skip_id=best['signal']['id'])
    if baseline['signals']:
        for delay in (2,3):resume_or_replay(engine,delay=delay)
        resume_or_replay(engine,adverse=False)
        # Small matched controls are diagnostics only; five random paths cannot
        # establish p<0.05, much less survive testing nine families.
        for seed in range(5):resume_or_replay(engine,control='RANDOM_SIDE_MATCHED_TIME',seed=seed)
    return {'engine':engine,'baseline_status':baseline['status'],'trades':baseline['trades'],
            'final_cash':baseline['final_cash'],'last_conditional_cash':baseline['last_resolved_cash']}

def main(wait_for_reconciliation=False):
    if wait_for_reconciliation:
        deadline=time.monotonic()+7200
        while not (CACHE/'nonexpiry_reconciliation.json').exists():
            if time.monotonic()>deadline:raise RuntimeError('Reconciliation did not finish; no full-suite completion claimed')
            time.sleep(5)
    forced_candidates()
    started=datetime.now(timezone.utc).isoformat();results=[]
    with ThreadPoolExecutor(max_workers=3) as pool:
        for future in as_completed([pool.submit(run_one,e) for e in SOURCES]):
            results.append(future.result())
            save(CACHE/'suite_progress.json',{'started_at':started,'status':'RUNNING','completed_engines':results})
    save(CACHE/'suite_progress.json',{'started_at':started,'finished_at':datetime.now(timezone.utc).isoformat(),
        'status':'COMPLETED_DISCOVERY_SWEEP','completed_engines':results,'winner':None,
        'note':'A completed sweep is not complete universe coverage or validation.'})
    print('DISCOVERY_SWEEP_FINISHED',len(results),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--wait-for-reconciliation',action='store_true');a=p.parse_args()
    main(a.wait_for_reconciliation)
