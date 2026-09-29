"""Conditional random-side bankroll controls; not independent market samples."""
import argparse,json
from decimal import Decimal as D
from research.gauntlet.data import save
from .replay import dataset,run,digest,RESULTS
from .signals import NAMES

def holm(ps):
    ordered=sorted(ps,key=ps.get);out={};previous=0
    for i,k in enumerate(ordered):
        previous=max(previous,min(1.,ps[k]*(len(ordered)-i)));out[k]=previous
    return out

def main():
    p=argparse.ArgumentParser();p.add_argument('--period',required=True);p.add_argument('--controls',type=int,default=999)
    p.add_argument('--quality',choices=['strict','reported'],default='reported');a=p.parse_args()
    days,dh=dataset(a.quality);summary=[];paths=[]
    for name in NAMES:
        for style in ('TARGET','TRAIL'):
            base=run(days,name,style,a.period);known=[];unknown=0
            for seed in range(a.controls):
                r=run(days,name,style,a.period,seed=seed+120260920)
                paths.append({'strategy':r['strategy'],'period':a.period,'seed':seed,'bankroll':r['final_bankroll'],'unknown':r['unknown'],'trades':r['counts'].get('trades',0)})
                if r['final_bankroll'] is None:unknown+=1
                else:known.append(D(r['final_bankroll']))
            # An incomplete denominator cannot supply a favorable p-value.
            score=None if base['final_bankroll'] is None else D(base['final_bankroll'])
            pval=None if score is None or unknown else (1+sum(k>=score for k in known))/(1+a.controls)
            item={'strategy':base['strategy'],'baseline':base['final_bankroll'],'randomizations':a.controls,'unknown_controls':unknown,
                  'p_conditional':pval,'median_random_bankroll':None if not known else str(sorted(known)[len(known)//2]),
                  'expiry_count':base['counts'].get('sessions',0),'observed_trades':base['counts'].get('trades',0)}
            summary.append(item);print(a.period,item,flush=True)
    adjusted=holm({x['strategy']:x['p_conditional'] if x['p_conditional'] is not None else 1 for x in summary})
    for x in summary:x['holm_12']=None if x['p_conditional'] is None else adjusted[x['strategy']]
    save(RESULTS/(a.period+'_'+a.quality+'_noise.json'),{'source_hash':digest(),'data_hash':dh,'quality':a.quality,'summary':summary,'paths':paths,
        'interpretation':'Conditional random-side test at observed signal times; estimates direction/contract selection contribution, not independence of signal timing. Monte Carlo paths are not additional independent market histories.'})

if __name__=='__main__':main()
