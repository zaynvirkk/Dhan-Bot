"""Cross-source identity and coverage audit, never a signal selector."""
import json
from collections import Counter,defaultdict
from research.gauntlet.core import Bar,D
from research.gauntlet.data import save
from research.expiry.collect import option_file
from research.expiry.signals import stamp
from .providers import STORE,OUT
from .signals import rolling_map,NAMES

def main():
    options=rolling_map();inst=json.loads((STORE/'instruments.json').read_text());signals=json.loads((STORE/'signals.json').read_text())
    jobs=json.loads((STORE/'option_jobs.json').read_text());counts=Counter();examples=[];perday={}
    for j in jobs:
        f=option_file(j['day'],j['key'])
        if not f.exists():counts['missing_option_files']+=1;continue
        raw=json.loads(f.read_text());counts['contract_days']+=1;counts['option_rows']+=len(raw['bars']);counts[raw['audit']['status']]+=1
        m=raw['metadata'];strike=float(m['strike_price']);side=m['instrument_type'];day=j['day']
        close=stamp(day,'15:40' if day>='2026-08-03' else '15:30')
        expected=int((close-stamp(day,'09:15')).total_seconds()/60)
        starts={Bar.parse(r).start for r in raw['bars']}
        if len(starts)==expected:counts['complete_option_sessions']+=1
        else:counts['option_sessions_with_gaps']+=1
        for row in raw['bars']:
            b=Bar.parse(row);match=options.get((b.available,side,strike))
            if match is None:counts['outside_rolling_subset_or_missing']+=1;continue
            counts['cross_broker_matched_identity']+=1
            diff=abs(b.close-D(str(match[0])))
            if diff<=D('.05'):counts['close_agrees_within_tick']+=1
            else:
                counts['close_disagreement']+=1
                if len(examples)<10:examples.append({'day':day,'key':j['key'],'at':b.available.isoformat(),'upstox_close':str(b.close),'dhan_close':match[0]})
            if b.oi==int(match[1]):counts['oi_exact_agreement']+=1
    for period in ('earlier','recent'):
        perday[period]={}
        for name in NAMES:
            rows=[x for d,x in signals.items() if inst[d]['partition']==period]
            perday[period][name]={'sessions':len(rows),'signals':sum(name in x['signals'] for x in rows),
                'unknown_sessions':sum(any(g.startswith(name+':') for g in x['gaps']) for x in rows)}
    market=json.loads((STORE/'market_download.json').read_text())
    covered=sorted({r['day'] for r in market if r['insights']})
    out={'counts':dict(counts),'cross_broker_disagreement_examples':examples,'per_rule_signal_coverage':perday,
        'intraday_analytics_nonempty_sessions':covered,'note':'Price/OI agreement is an audit, not proof of contemporaneous availability or historical depth.'}
    save(OUT/'data_coverage.json',out);print(json.dumps(out['counts']),flush=True)

if __name__=='__main__':main()
