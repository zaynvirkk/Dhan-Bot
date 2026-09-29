"""Conditional random-direction controls; no invented independent observations."""
import json
from research.gauntlet.data import save
from research.gauntlet.core import D
from research.expiry.replay import run
from .providers import OUT
from .replay import STRATEGIES,inputs,digest

def main():
    sh=digest();days,dh,_=inputs('reported');output=[]
    bases={}
    for period in ('earlier','recent'):
        doc=json.loads((OUT/(period+'_reported.json')).read_text())
        if doc['source_hash']!=sh or doc['data_hash']!=dh:raise ValueError('stale replay before noise controls')
        for r in doc['runs']:bases[period,r['strategy'],r['scenario']]=r
    for period in ('earlier','recent'):
        for name in STRATEGIES:
            for style in ('TARGET','TRAIL'):
                strategy=name+'_'+style;base=bases[period,strategy,'primary']
                row={'period':period,'strategy':strategy,'baseline':base['final_bankroll'],'p_conditional':None,'adjusted_p':None,'controls':[]}
                if base['final_bankroll'] is None:
                    row['status']='UNKNOWN_BASELINE';output.append(row);continue
                if not base['counts'].get('signals'):
                    row['status']='NO_SIGNAL_EVIDENCE';output.append(row);continue
                robust=all(bases[p,strategy,s]['final_bankroll'] is not None and D(bases[p,strategy,s]['final_bankroll'])>D('9411.18') for p in ('earlier','recent') for s in ('primary','delete_best'))
                n=3999 if robust else 499
                for seed in range(n):
                    r=run(days,name,style,period,seed=2026092000+seed)
                    row['controls'].append(r['final_bankroll'])
                if None in row['controls']:row['status']='UNKNOWN_CONTROL_PATH'
                else:
                    row['status']='CONDITIONAL_DIRECTION_TEST'
                    row['p_conditional']=(1+sum(D(v)>=D(row['baseline']) for v in row['controls']))/(n+1)
                output.append(row)
                print('controls',period,strategy,n,'p',row['p_conditional'],flush=True)
                save(OUT/'noise_progress.json',{'source_hash':sh,'completed':len(output),'planned':len(STRATEGIES)*4})
    for period in ('earlier','recent'):
        eligible=sorted([r for r in output if r['period']==period and r['p_conditional'] is not None],key=lambda r:r['p_conditional'])
        prev=0.
        # All 64 trials count, including unknown/untraded variants.
        for i,r in enumerate(eligible):
            prev=max(prev,min(1.,(len(STRATEGIES)*2-i)*r['p_conditional']));r['adjusted_p']=prev
    if sh!=digest():raise ValueError('source drift during noise run')
    save(OUT/'noise.json',{'source_hash':sh,'data_hash':dh,'comparisons':64,'rows':output})

if __name__=='__main__':main()
