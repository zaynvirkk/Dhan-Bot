import csv,json,sys,subprocess,tempfile,importlib.util,collections,time
from pathlib import Path
from datetime import datetime,timezone,timedelta
from decimal import Decimal as D
from types import SimpleNamespace
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from dhan_cas_bot.domain import Instrument,OptionBook,OptionType,Segment,Level
from dhan_cas_bot.seconds_strategies import SecondsTape,NAMES
import argparse,hashlib
parser=argparse.ArgumentParser(description='Diagnostic old/new detector comparison; never simulates or submits real orders.')
parser.add_argument('--archive',type=Path,required=True)
args=parser.parse_args();archive=args.archive
with archive.open() as f:
 meta=json.loads(next(f));spot=json.loads(next(f));records=[json.loads(line) for line in f]
closes={datetime.fromisoformat(b['available']):D(b['close']) for b in spot['rows']}
checks=[]
for row in csv.DictReader((root/'research/results/session_review_20261015_full/pullback_decisions.csv').open()):
 if row['state']!='NO_SIGNAL':continue
 at=datetime.fromisoformat(row['decision_ist']);trend=closes[at]/closes[at-timedelta(minutes=30)]-1;pull=closes[at]/closes[at-timedelta(minutes=10)]-1
 checks.append({'at':at.isoformat(),'trend':str(trend),'pullback':str(pull),'necessary_conditions_met':abs(trend)>=D('.0025') and trend*pull<0,'matches_recorded':abs(trend-D(row['trend_30m']))<D('.00000001') and abs(pull-D(row['pullback_10m']))<D('.00000001')})
insts={i['security_id']:Instrument(i['security_id'],i['underlying'],Segment.NSE_FNO,datetime.fromisoformat(i['expiry']).date(),OptionType(i['option_type']),D(i['strike']),i['lot_size'],D(i['tick_size']),i['freeze_qty']) for i in meta['instruments']}
records.sort(key=lambda r:r['at_ns'])
with tempfile.TemporaryDirectory() as temp:
 path=Path(temp)/'old_seconds.py';path.write_bytes(subprocess.check_output(['git','show','9f829d4:dhan_cas_bot/seconds_strategies.py'],cwd=root))
 spec=importlib.util.spec_from_file_location('dhan_cas_bot._audit_old_seconds',path);old=importlib.util.module_from_spec(spec);sys.modules[spec.name]=old;spec.loader.exec_module(old)
 tapes={'before':old.SecondsTape(),'after':SecondsTape()};books={};next_eval=None
 sums={key:{n:{'reasons':collections.Counter(),'episodes':{},'raw_guard_checks':0} for n in NAMES[:4]} for key in tapes}
 cal=SimpleNamespace(fresh=lambda _:True,is_open=lambda _:True,closes=datetime.fromisoformat('2026-10-15T15:40:00+05:30'))
 def evaluate(stamp):
  at=datetime.fromtimestamp(stamp/1e9,timezone.utc)
  for key,tape in tapes.items():
   samples=tape.evaluate(at,books,(),cal,budget=D('7805.94')*D('.95'))
   for n in NAMES[:4]:
    sample=samples[n];r=sums[key][n];r['reasons'][sample.reason]+=1
    if sample.state=='SIGNAL':r['episodes'].setdefault(sample.details['episode'],{'at':at.isoformat(),'side':sample.side,'security_id':sample.details['security_id'],'target_price':sample.details['target_price']})
 for idx,r in enumerate(records):
  stamp=r['at_ns']
  if next_eval is None:next_eval=stamp
  # All observations used at each decision have already arrived.
  while next_eval<stamp:
   evaluate(next_eval);next_eval+=1_000_000_000
  if r['kind']=='future':
   for tape in tapes.values():tape.future_tick(D(r['price']),stamp,'sampled-archive')
  elif r['security_id'] in insts:
   books[r['security_id']]=OptionBook(insts[r['security_id']],tuple(Level(D(p),q) for p,q in r['bid']),tuple(Level(D(p),q) for p,q in r['ask']),'sampled-archive',stamp,statistics=SimpleNamespace(volume=r.get('volume')) if r.get('volume') is not None else None)
  if idx and idx%25000==0:print('Reviewed',idx,'sampled quote records',flush=True)
 result={'writes_to_broker':False,'kind':'SAMPLED_DIAGNOSTIC_COMPARISON_NOT_BACKTEST','source_before':'9f829d4','archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),
 'after_kernel_sha256':hashlib.sha256((root/'dhan_cas_bot/seconds_strategies.py').read_bytes()).hexdigest(),
 'metadata_observed_at':meta['metadata_observed_at'],'records':len(records),'evaluated_seconds':sum(sums['after'][NAMES[0]]['reasons'].values()),
 'pullback_independent':{'checks':len(checks),'necessary_conditions_met':sum(x['necessary_conditions_met'] for x in checks),'exact_matches_recorded':sum(x['matches_recorded'] for x in checks),'rows':checks},
 'comparison':{key:{n:{'reasons':dict(r['reasons']),'signal_episodes':len(r['episodes']),'first_episodes':list(r['episodes'].values())[:10]} for n,r in values.items()} for key,values in sums.items()},
 'limits':['Half-second sampled quotes are not the complete funded feed.','Socket epochs and invalid packets are absent; continuous-epoch scenario only.','Current same-day contract metadata is used for identity/lot size; historical price bands are omitted equally in both scenarios.','Official event receipts absent; event strategy excluded.','No fills, bankroll returns or missed profits credited.']}
 out=root/'research/results/seconds_repair_review_20261015/diagnostic_comparison.json';out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k] for k in ('records','evaluated_seconds','comparison')},indent=2))
