"""Read-only operational checks and complete-day counters; never broker writes."""
from copy import deepcopy
from datetime import datetime,timedelta
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from zoneinfo import ZoneInfo

IST=ZoneInfo('Asia/Kolkata')
MESSAGES={
 'TRADER_STALE':'The trader stopped publishing current status.',
 'ACCOUNT_READ_FAILED':'The latest broker account read failed.',
 'ACCOUNT_NOT_RECONCILED':'The trader cannot confirm a current reconciled account.',
 'SOFTWARE_UNVERIFIED':'The funded trader has no matching software verification.',
 'OPTIONS_DISCONNECTED':'The options connection is disconnected during an active session.',
 'OPTIONS_STALE':'The connected options feed has stopped producing usable books.',
 'ORDERS_DISCONNECTED':'The order-update connection is disconnected while it is needed.',
 'FUTURES_UNUSABLE':'The strategy has no current usable futures input.',
 'ROUTE_UNQUALIFIED':'The order connection has not qualified during an active session.',
 'ROUTE_OUTCOME_UNKNOWN':'An order-check outcome is unknown and requires reconciliation.',
 'REPLAY_FAILED':'The market-data recorder reported a failure.',
 'STRATEGY_INPUT_UNAVAILABLE':'A funded strategy cannot evaluate its required inputs.',
 'STRATEGY_CHECK_STALE':'A funded strategy stopped producing current evaluations.',
 'SESSION_STATE_MISMATCH':'The strategy reports a closed exchange while the verified session is open.',
 'READY_NOT_DISPATCHED':'A ready contract assessment has no recorded final dispatch outcome.',
 'MONITOR_UNAVAILABLE':'The operational monitor is unavailable and needs investigation.',
 'DAY_AUDIT_UNAVAILABLE':'The monitor cannot reconstruct the complete recorded trading day.',
}


def stamp(value):
 t=datetime.fromisoformat(value)
 if t.tzinfo is None:raise ValueError('timestamp must include timezone')
 return t


def day_summary(path,now,strategies):
 day=now.astimezone(IST).date().isoformat()
 result={'date':day,'status':'UNAVAILABLE','observed_at':now.isoformat()}
 if not Path(path).is_file():return result
 try:
  with sqlite3.connect('file:'+str(Path(path).resolve())+'?mode=ro',uri=True,timeout=.2) as db:
   db.row_factory=sqlite3.Row;db.execute('PRAGMA query_only=ON');db.execute('BEGIN')
   latest={};episodes=[];partial=False
   from .data import STRATEGY_NAMES,STRATEGY_REASONS
   for name in strategies[:16]:
    if name not in STRATEGY_NAMES:continue
    prefix=f'strategy-evaluation:{name}:{day}'
    records=list(db.execute('SELECT payload,received_at FROM observations WHERE identity>=? AND identity<? LIMIT 5001',(prefix,prefix+'~')))
    partial|=len(records)>5000
    for r in records[:5000]:
     if len(r['payload'])>100000:raise ValueError('oversized evaluation')
     raw=json.loads(r['payload']);at=stamp(raw['evaluated_at']);received=stamp(r['received_at'])
     if at>now or received>now or at.astimezone(IST).date().isoformat()!=day:continue
     if raw.get('strategy')!=name:continue
     key=(name,at)
     if key not in latest or received>latest[key][0]:latest[key]=(received,raw.get('state'))
    prefix=f'directional-signal:{day}:{name}'
    episode_rows=list(db.execute('SELECT key,value FROM metadata WHERE key>=? AND key<? LIMIT 3001',(prefix,prefix+'~')))
    partial|=len(episode_rows)>3000
    for r in episode_rows[:3000]:
     if r['key'].endswith((':assessment',':consumed')):continue
     raw=json.loads(r['value']);at=stamp(raw['evaluated_at'])
     if raw.get('state')!='SIGNAL' or raw.get('strategy')!=name or at>now:continue
     def meta(suffix):
      value=db.execute('SELECT value FROM metadata WHERE key=?',(r['key']+suffix,)).fetchone()
      return json.loads(value[0]) if value else {}
     assessment=meta(':assessment');consumed=meta(':consumed');checks=assessment.get('candidate_checks',[])
     multiples=[Decimal(str(c['scenario_multiple'])) for c in checks if c.get('scenario_multiple') is not None]
     if any(not x.is_finite() for x in multiples):raise ValueError('invalid scenario')
     reason=assessment.get('reason');reason=reason if reason in STRATEGY_REASONS else 'UNKNOWN'
     if reason=='NO_AFFORDABLE_LIQUID_CONTRACT' and any(c.get('reason')=='SHOCK_SCENARIO_BELOW_FLOOR' for c in checks):reason='SHOCK_SCENARIO_BELOW_FLOOR'
     outcome=consumed.get('reason');outcome=outcome if outcome in {'DECISION_COMMITTED','ENTRY_DEADLINE_MISSED','SHOCK_RECONNECT_INVALIDATED'} else None
     episodes.append({'strategy':name,'at':at.isoformat(),'reason':reason,'outcome':outcome,
      'contracts_checked':len(checks),'best_scenario_multiple':str(max(multiples)) if multiples else None})
   counts={'entry_attempts':0,'filled_entries':0,'route_attempts':0}
   for r in db.execute("SELECT i.created_at,i.lifecycle_id,EXISTS(SELECT 1 FROM attempts a WHERE a.intent_id=i.intent_id) sent,EXISTS(SELECT 1 FROM fills f WHERE f.intent_id=i.intent_id) filled FROM intents i WHERE i.side='BUY' AND i.created_at>=? AND i.created_at<?",(day,day+'~')):
    at=stamp(r['created_at'])
    if at>now or at.astimezone(IST).date().isoformat()!=day:continue
    if r['lifecycle_id']=='route-probe':counts['route_attempts']+=r['sent']
    else:counts['entry_attempts']+=r['sent'];counts['filled_entries']+=r['filled']
   values=[v[1] for v in latest.values()]
   result.update(status='PARTIAL' if partial else 'AVAILABLE',completed_checks=sum(x in {'SIGNAL','NO_SIGNAL'} for x in values),
    signal_minutes=values.count('SIGNAL'),data_warning_minutes=sum(x in {'UNKNOWN','INPUT_UNAVAILABLE'} for x in values),
    episodes=len(episodes),episode_reviews=sorted(episodes,key=lambda r:stamp(r['at'])),**counts)
 except (sqlite3.Error,ValueError,TypeError,KeyError,AttributeError):return result
 return result


def fault_candidates(report,now):
 rt=report.get('runtime') or {};account=report.get('account') or {};found=[]
 held=(account.get('open_position_count') or 0)>0
 required=rt.get('exchange_session_open') is True or held
 funded=rt.get('authority')=='ENABLED' and bool(rt.get('funded_strategies'))
 def add(code,immediate=False):found.append({'code':code,'severity':'CRITICAL','immediate':immediate})
 if not rt.get('fresh'):add('TRADER_STALE')
 if ((report.get('ledger') or {}).get('route_check') or {}).get('state')=='SEND_UNKNOWN':add('ROUTE_OUTCOME_UNKNOWN',True)
 if rt.get('recorder_failed') is True:add('REPLAY_FAILED',True)
 if required:
  if report.get('account_read_ok') is not True:add('ACCOUNT_READ_FAILED')
  if rt.get('account_snapshot_fresh') is not True:add('ACCOUNT_NOT_RECONCILED')
  if rt.get('software_verified') is False:add('SOFTWARE_UNVERIFIED',True)
  for name,code in [('market','OPTIONS_DISCONNECTED'),('order','ORDERS_DISCONNECTED')]:
   if (rt.get('feed_health') or {}).get(name,{}).get('connected') is not True:add(code)
  market=(rt.get('feed_health') or {}).get('market') or {}
  if market.get('connected') is True:
   try:
    if not 0<=(now-stamp(market.get('last_usable_at'))).total_seconds()<=5:add('OPTIONS_STALE')
   except (ValueError,TypeError):add('OPTIONS_STALE')
  if funded:
   if rt.get('broker_route_verified') is not True:add('ROUTE_UNQUALIFIED')
   if not (rt.get('future_input') or {}).get('current'):add('FUTURES_UNUSABLE')
   evaluations=rt.get('strategy_evaluations') or []
   if set(rt['funded_strategies'])-{r.get('strategy') for r in evaluations}:add('STRATEGY_CHECK_STALE')
   for row in evaluations:
    if row.get('strategy') not in rt.get('funded_strategies',[]):continue
    if row.get('reason')=='EXCHANGE_CLOSED' and rt.get('exchange_session_open') is True:add('SESSION_STATE_MISMATCH')
    elif row.get('state') in {'UNKNOWN','INPUT_UNAVAILABLE'}:add('STRATEGY_INPUT_UNAVAILABLE')
    try:
     if not 0<=(now-stamp(row.get('evaluated_at'))).total_seconds()<=120:add('STRATEGY_CHECK_STALE')
    except (ValueError,TypeError):add('STRATEGY_CHECK_STALE')
 return list({r['code']:r for r in found}.values())


def advance_incidents(previous,candidates,now):
 if previous is not None and (previous.get('schema')!=1 or not isinstance(previous.get('incidents'),list)):
  raise ValueError('preserve corrupt incident evidence')
 result=deepcopy(previous) if previous is not None else {'schema':1,'incidents':[]}
 live={r['code']:r for r in result['incidents'] if r.get('state') in {'OPEN','PENDING'}}
 seen={c['code'] for c in candidates}
 for candidate in candidates:
  code=candidate['code']
  if code not in MESSAGES:raise ValueError('unknown incident code')
  record=live.get(code)
  if record is None:
   record={'id':sha256((code+now.isoformat()).encode()).hexdigest()[:20],'code':code,'severity':candidate['severity'],
    'message':MESSAGES[code],'first_seen':now.isoformat(),'state':'PENDING'}
   result['incidents'].append(record)
  record['last_seen']=now.isoformat()
  if candidate.get('immediate') or (now-stamp(record['first_seen'])).total_seconds()>=30:record['state']='OPEN'
 for code,record in live.items():
  if code not in seen:record.update(state='RESOLVED',resolved_at=now.isoformat())
 # Preserve every unresolved incident and bound the resolved tail.
 unresolved=[r for r in result['incidents'] if r['state']!='RESOLVED']
 resolved=[r for r in result['incidents'] if r['state']=='RESOLVED'][-128:]
 result.update(observed_at=now.isoformat(),incidents=resolved+unresolved,status='AVAILABLE')
 return result


def build_operations(config,output,report,now):
 from .data import read_json
 from .collect import atomic_json
 target=Path(output).with_name('operations.json')
 previous=read_json(target,1024*1024)
 if target.exists() and previous is None:raise ValueError('unreadable operations evidence')
 summary=day_summary(Path(config['state_dir'])/'ledger.sqlite3',now,(report.get('runtime') or {}).get('strategies') or [])
 faults=fault_candidates(report,now)
 if summary['status']!='AVAILABLE':faults.append({'code':'DAY_AUDIT_UNAVAILABLE','severity':'CRITICAL','immediate':False})
 for episode in summary.get('episode_reviews',[]):
  if episode['reason']=='READY' and episode['outcome']!='DECISION_COMMITTED' and (now-stamp(episode['at'])).total_seconds()>60:
   faults.append({'code':'READY_NOT_DISPATCHED','severity':'CRITICAL','immediate':True})
 result=advance_incidents(previous,faults,now)
 prior_open={r['id'] for r in (previous or {}).get('incidents',[]) if r.get('state')=='OPEN'}
 for incident in result['incidents']:
  if incident['state']=='OPEN' and incident['id'] not in prior_open:
   print(json.dumps({'event':'DHAN_INCIDENT_OPEN','code':incident['code'],'id':incident['id']}),flush=True)
 result['session']=summary
 runner=read_json(Path(output).with_name('repair-runner.json'),8192)
 if runner:result['repair_runner']={k:runner.get(k) for k in ('checked_at','state','last_attempt_at','attempts_today','requires_local_computer')}
 atomic_json(target,result)
 # Durable daily counters are separate from the bounded UI ring.
 if summary['status']=='AVAILABLE':atomic_json(Path(output).with_name('operations-day-'+summary['date']+'.json'),summary)
 return result
