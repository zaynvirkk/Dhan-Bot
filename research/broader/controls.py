"""Matched-clock random-side controls; identical executable bankroll replay."""
import json,hashlib
from functools import lru_cache
from . import replay
from .prepare import OUT
from research.gauntlet.data import save,ROOT
from research.gauntlet.core import D

def main():
    results=json.loads((OUT/'options.json').read_text());assert results['source_sha256']==replay.digest()
    candidates=[r for r in results['runs'] if r['scenario']=='primary' and r['final_bankroll'] and D(r['final_bankroll'])>D('12566.43')]
    ds=replay.Dataset();base_trade=replay.trade;stats=[]
    @lru_cache(maxsize=20000)
    def cached(encoded,o,quality,delay,slip):
        return base_trade(ds,json.loads(encoded),o,quality,delay,slip)
    def fast_trade(dataset,s,o,quality='reported',delay=1,slip=1):
        assert dataset is ds
        return dict(cached(json.dumps(s,sort_keys=True),o,quality,delay,slip))
    for c in candidates:
        if not c['strategy'].startswith('NIFTY_'):
            stats.append({'strategy':c['strategy'],'period':c['period'],'status':'UNKNOWN_QUALIFYING_UNIVERSE_CONTROL_COVERAGE'});continue
        paths=[]
        # Equality check before memoization; speed must not change trade selection.
        expected=replay.run(ds,c['strategy'],c['period'])
        assert expected['final_bankroll']==c['final_bankroll'] and expected['ledger']==c['ledger']
        replay.trade=fast_trade
        check=replay.run(ds,c['strategy'],c['period'])
        assert check==expected
        for seed in range(999):
            r=replay.run(ds,c['strategy'],c['period'],seed=seed)
            paths.append({'seed':seed,'final_bankroll':r['final_bankroll'],'unknown':r['unknown'],'trades':r['counts'].get('trades',0)})
            if (seed+1)%100==0:print(c['strategy'],c['period'],'controls',seed+1,flush=True)
        unknown=sum(p['final_bankroll'] is None for p in paths)
        better=sum(p['final_bankroll'] is not None and D(p['final_bankroll'])>=D(c['final_bankroll']) for p in paths)
        upper=(better+unknown+1)/1000;lower=(better+1)/1000
        stats.append({'strategy':c['strategy'],'period':c['period'],'observed':c['final_bankroll'],'status':'CONDITIONAL_RANDOMIZATION',
                      'paths':paths,'at_least_observed':better,'unknown':unknown,'p_lower':lower,'p_upper':upper,'adjusted_144_upper':min(1,144*upper)})
        replay.trade=base_trade
        save(OUT/'controls_progress.json',{'source_sha256':replay.digest(),'results':stats})
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(ds.used)}
    save(OUT/'controls.json',{'source_sha256':replay.digest(),'base_input_hashes':results['input_hashes'],'control_input_hashes':hashes,'results':stats})
    print('control cases',len(stats),flush=True)

if __name__=='__main__':main()
