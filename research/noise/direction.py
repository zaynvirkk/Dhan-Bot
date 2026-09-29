"""Day-clustered underlying-return diagnostics; never option-return estimates."""
import json,random,math
from collections import defaultdict
from datetime import datetime,timedelta,timezone
from functools import lru_cache
from statistics import mean,median
from research.gauntlet.data import CACHE,save
from research.gauntlet.replay import SOURCES
from research.gauntlet.provenance import digest
from research.noise.compile import NOISE

@lru_cache(maxsize=4)
def tape(symbol):
    return {r[0]:r for r in json.loads((CACHE/'underlying'/f'{symbol}.json').read_text())}

def holm(pvalues,total_tests=9):
    ordered=sorted((p,k) for k,p in pvalues.items() if p is not None);out={};last=0
    for i,(p,k) in enumerate(ordered):
        last=max(last,min(1,p*(total_tests-i)));out[k]=last
    return out

def clustered(values,seed=20260920,draws=9999):
    """One equally weighted mean per date; no fake per-trade independence."""
    days=defaultdict(list)
    for row in values:days[row['day']].append(row['signed_return'])
    means=[mean(v) for _,v in sorted(days.items())]
    if len(means)<2:return {'observations':len(values),'days':len(means),'p':None,'ci':None}
    rng=random.Random(seed);observed=mean(means)
    extreme=0;boots=[]
    for _ in range(draws):
        null=mean(v*(1 if rng.getrandbits(1) else -1) for v in means)
        extreme+=null>=observed
        boots.append(mean(means[rng.randrange(len(means))] for _ in means))
    boots.sort()
    return {'observations':len(values),'days':len(means),'mean_signed_return':observed,
            'median_day_signed_return':median(means),'positive_days':sum(v>0 for v in means),
            'p':(extreme+1)/(draws+1),'ci':[boots[int(draws*.025)],boots[min(draws-1,int(draws*.975))]],
            'day_means':dict(zip(sorted(days),means))}

def run():
    inputs=sorted(set([CACHE/'ban_lists.json']+[CACHE/s for s in SOURCES.values()]+
                      list((CACHE/'underlying').glob('*.json'))))
    input_hashes={str(p.relative_to(CACHE)):digest(p) for p in inputs}
    bans=json.loads((CACHE/'ban_lists.json').read_text());summaries={}
    for engine,source in SOURCES.items():
        signals=[s for s in json.loads((CACHE/source).read_text()) if s['engine']==engine]
        metrics={};excluded=defaultdict(int)
        for horizon in (5,15,30):
            values=[];gaps=[]
            for s in signals:
                if s['materiality'] not in ('QUALIFYING_TEXT','NOT_REQUIRED'):
                    if horizon==15:excluded['outside_metadata_variant']+=1
                    continue
                if s['futures_confirmation'] not in ('CONFIRMED','NOT_REQUIRED'):
                    gaps.append({'id':s['id'],'reason':'UNKNOWN_CONFIRMATION'});continue
                ban=bans.get(s['at'][:10],{})
                if ban.get('status')!='VERIFIED_DATE':gaps.append({'id':s['id'],'reason':'UNKNOWN_BAN'});continue
                if s['symbol'] in ban['symbols']:
                    if horizon==15:excluded['banned']+=1
                    continue
                at=datetime.fromisoformat(s['at']);start=at+timedelta(minutes=1)
                end=start+timedelta(minutes=horizon-1)
                regular_close=at.replace(hour=15,minute=15 if at.date().isoformat()>='2026-08-03' else 30,second=0,microsecond=0)
                if end+timedelta(minutes=1)>regular_close:
                    if horizon==15:excluded['insufficient_regular_session_time']+=1
                    continue
                rows=tape(s['symbol']);a=rows.get(start.isoformat());b=rows.get(end.isoformat())
                # Require the whole interval so missing minutes cannot be ignored.
                if a is None or b is None or any((start+timedelta(minutes=i)).isoformat() not in rows for i in range(horizon)):
                    gaps.append({'id':s['id'],'reason':'MISSING_HORIZON_TAPE'});continue
                if float(a[1])<=0:gaps.append({'id':s['id'],'reason':'ZERO_ENTRY'});continue
                value=(float(b[4])/float(a[1])-1)*(1 if s['side']=='CE' else -1)
                values.append({'id':s['id'],'day':s['at'][:10],'symbol':s['symbol'],
                    'entry_time':start.isoformat(),'exit_available':(end+timedelta(minutes=1)).isoformat(),
                    'signed_return':value})
            result=clustered(values);result.update(horizon=horizon,gaps=gaps,rows=values)
            metrics[str(horizon)]=result
        summaries[engine]={'metrics':metrics,'excluded':dict(excluded),'source_sha':digest(CACHE/source)}
        print('DIRECTION',engine,metrics['15'].get('mean_signed_return'),metrics['15']['p'],flush=True)
    adjusted=holm({e:x['metrics']['15']['p'] for e,x in summaries.items()})
    for engine,x in summaries.items():x['primary_holm_p']=adjusted.get(engine)
    if any(digest(CACHE/p)!=sha for p,sha in input_hashes.items()):
        raise RuntimeError('Directional input data changed during calculation')
    save(NOISE/'direction.json',{'engines':summaries,'draws':9999,'primary_minutes':15,
        'generated_at':datetime.now(timezone.utc).isoformat(),'script_sha':digest(__file__),
        'input_hashes':input_hashes,
        'interpretation':'Underlying directional predictability under day sign-symmetry; conditional discovery, not option profitability or holdout.'})

if __name__=='__main__':run()
