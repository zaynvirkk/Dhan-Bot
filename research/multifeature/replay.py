"""Independent 90-day bankrolls using the existing execution kernel."""
import argparse,hashlib,json
from pathlib import Path
from collections import Counter
from datetime import date
from research.gauntlet.core import Bar,Contract,D
from research.gauntlet.data import save
from research.expiry.collect import option_file,selected_chain
from research.expiry.signals import NAMES as OLD_NAMES,option_signals
from research.expiry.replay import run
from .providers import STORE,OUT
from .signals import NAMES
from .collect import WINDOWS
from .quality import tape_issues

STRATEGIES=tuple('EXPIRY_'+n for n in OLD_NAMES)+tuple(scope+'_'+n for scope in ('EXPIRY','ORDINARY') for n in NAMES)

def digest():
    parent=Path(__file__).resolve().parents[1]
    paths=list(Path(__file__).parent.glob('*.py'))+[Path(__file__).with_name('PROTOCOL.md')]
    paths+=list((parent/'expiry').glob('*.py'))+[parent/'gauntlet/core.py',parent.parent/'dhan_cas_bot/risk.py']
    return hashlib.sha256(b''.join(str(p.relative_to(parent.parent)).encode()+p.read_bytes() for p in sorted(paths))).hexdigest()

def inputs(quality='reported',lag5=False):
    inst=json.loads((STORE/'instruments.json').read_text());sigs=json.loads((STORE/'signals.json').read_text())
    jobs=json.loads((STORE/'option_jobs.json').read_text());files={};hashes=[]
    for j in jobs:files.setdefault(j['day'],[]).append((j['key'],option_file(j['day'],j['key'])))
    days={};audits=Counter()
    for day,x in inst.items():
        if 'error' in x:days[day]=x;continue
        chain=[Contract.parse(m) for m in x['chain'].values()];bars={};errors={}
        for k,f in files.get(day,[]):
            if not f.exists():errors[k]='UNKNOWN_REQUEST';audits['MISSING_FILE']+=1;continue
            raw=json.loads(f.read_text());hashes.append(hashlib.sha256(f.read_bytes()).hexdigest())
            if raw['key']!=k or raw['day']!=day:raise ValueError('wrong tape identity')
            audits[raw['audit']['status']]+=1
            bars[k]=[Bar.parse(r) for r in raw['bars']]
            issues=tape_issues(raw,bars[k])
            audits.update(i for i in issues if i!=raw['audit']['status'])
            if quality=='strict' and issues:errors[k]=';'.join(issues)
        row=sigs[day];signals={};gaps=[];scope='EXPIRY' if x['expiry_day'] else 'ORDINARY'
        for name,s in row['lag5_signals' if lag5 else 'signals'].items():
            full=scope+'_'+name;signals[full]=dict(s,name=full)
        gaps+=[scope+'_'+g for g in row['lag5_gaps' if lag5 else 'gaps']]
        if x['expiry_day']:
            for name,s in row['old_signals'].items():
                full='EXPIRY_'+name;signals[full]=dict(s,name=full)
            gaps+=['EXPIRY_'+g for g in row['old_gaps']]
            anchor=D(row['anchor']) if row['anchor'] else None
            if anchor is None:
                gaps+=['EXPIRY_'+n+':MISSING_ANCHOR' for n in ('OPTION_ACCEL','OPTION_ACCEL_OI')]
            else:
                anchors={side:selected_chain(chain,anchor,side)[0] for side in ('CE','PE')}
                os,og=option_signals({s:bars[c.key] for s,c in anchors.items() if c.key in bars and c.key not in errors},day,anchor)
                for n,s in os.items():signals['EXPIRY_'+n]=dict(s,name='EXPIRY_'+n)
                gaps+=['EXPIRY_'+g for g in og]
        days[day]={'partition':x['partition'],'signals':signals,'gaps':gaps,'chain':chain,'bars':bars,'errors':errors,'expiry_day':x['expiry_day']}
    raw=[hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(STORE.rglob('*.json')) if 'auth' not in f.relative_to(STORE).parts]
    raw+=hashes
    return days,hashlib.sha256(''.join(raw).encode()).hexdigest(),dict(audits)

def main(period,quality):
    days,dh,audits=inputs(quality);runs=[]
    start,finish=WINDOWS[period]
    assert (date.fromisoformat(finish)-date.fromisoformat(start)).days+1==90
    sh=digest()
    for name in STRATEGIES:
        for style in ('TARGET','TRAIL'):
            base=run(days,name,style,period);base.update(scenario='primary',quality=quality);runs.append(base)
            for delay,adverse,label in [(2,True,'delay2'),(3,True,'delay3'),(1,False,'open_plus_1pct')]:
                r=run(days,name,style,period,delay,adverse);r.update(scenario=label,quality=quality);runs.append(r)
            r=run(days,name,style,period,skip=base['best_trade_day']);r.update(scenario='delete_best',quality=quality);runs.append(r)
            print(period,quality,name,style,base['final_bankroll'],base['counts'].get('trades',0),base['unknown'],flush=True)
    delayed,_,_=inputs(quality,True)
    for name in STRATEGIES:
        for style in ('TARGET','TRAIL'):
            r=run(delayed,name,style,period);r.update(scenario='features_lag5',quality=quality);runs.append(r)
    if sh!=digest():raise RuntimeError('source drift during replay')
    save(OUT/(period+'_'+quality+'.json'),{'source_hash':sh,'data_hash':dh,'quality':quality,'window':[start,finish],
        'calendar_days':90,'sessions':sum(x['partition']==period for x in days.values()),
        'expiry_sessions':sum(x['partition']==period and x.get('expiry_day',False) for x in days.values()),'audits':audits,'runs':runs})

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--period',choices=list(WINDOWS),required=True);p.add_argument('--quality',choices=['strict','reported'],default='reported');a=p.parse_args();main(a.period,a.quality)
