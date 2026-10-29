from datetime import datetime,timedelta,timezone
import hashlib,json,sqlite3
import pytest
from copy import deepcopy
from dhan_cas_bot.ledger import SCHEMA
from dhan_cas_bot.dashboard.operations import day_summary, advance_incidents, fault_candidates

NOW=datetime(2026,10,26,4,30,tzinfo=timezone.utc)
NAME='VOLATILITY_SHOCK_V1'

def healthy(open=True):
 return {'account_read_ok':True,'account':{'open_position_count':0},'runtime':{'fresh':True,'observed_at':NOW.isoformat(),
  'exchange_session_open':open,'authority':'ENABLED','funded_strategies':[NAME],'software_verified':True,
  'account_snapshot_fresh':True,'broker_route_verified':True,'recorder_failed':False,
  'future_input':{'current':open},'feed_health':{k:{'connected':True,'last_usable_at':NOW.isoformat()} for k in ('market','order')},
  'strategy_evaluations':[{'strategy':NAME,'state':'NO_SIGNAL','reason':'SHOCK_RULE_NOT_MET','evaluated_at':NOW.isoformat()}]}}

def test_closed_market_and_normal_filters_are_not_engineering_incidents():
 report=healthy(False);report['runtime']['broker_route_verified']=False
 report['runtime']['strategy_evaluations'][0].update(state='WAITING',reason='EXCHANGE_CLOSED')
 assert fault_candidates(report,NOW)==[]
 assert fault_candidates(healthy(),NOW)==[]

def test_real_faults_are_debounced_persisted_and_resolved_without_trading():
 report=healthy();report['runtime']['feed_health']['market']['connected']=False
 first=advance_incidents(None,fault_candidates(report,NOW),NOW)
 assert first['incidents'][0]['state']=='PENDING'
 second=advance_incidents(first,fault_candidates(report,NOW+timedelta(seconds=31)),NOW+timedelta(seconds=31))
 assert second['incidents'][0]['state']=='OPEN'
 third=advance_incidents(json.loads(json.dumps(second)),[],NOW+timedelta(seconds=40))
 assert third['incidents'][0]['state']=='RESOLVED' and third['incidents'][0]['first_seen']==NOW.isoformat()
 assert second['incidents'][0]['state']=='OPEN'  # input snapshots are immutable

def test_unknown_order_outcome_is_immediate_even_after_close():
 report=healthy(False);report['ledger']={'route_check':{'state':'SEND_UNKNOWN'}}
 state=advance_incidents(None,fault_candidates(report,NOW),NOW)
 assert any(r['code']=='ROUTE_OUTCOME_UNKNOWN' and r['state']=='OPEN' for r in state['incidents'])

def test_missing_or_invalid_monitor_evidence_is_not_a_healthy_empty_day(tmp_path):
 assert day_summary(tmp_path/'missing.sqlite3',NOW,[NAME])['status']=='UNAVAILABLE'
 try:advance_incidents({'schema':1,'incidents':'broken'},[],NOW)
 except ValueError:pass
 else:raise AssertionError('corrupt monitor evidence must not be overwritten')

def test_full_day_counts_keep_morning_episode_after_256_recent_checks(tmp_path):
 path=tmp_path/'ledger.sqlite3';db=sqlite3.connect(path);db.executescript(SCHEMA)
 for n in range(300):
  t=NOW+timedelta(minutes=n);state='SIGNAL' if n<5 else 'NO_SIGNAL'
  payload={'strategy':NAME,'evaluated_at':t.isoformat(),'state':state,'reason':'SHOCK_CONFIRMED','token':'PRIVATE'}
  db.execute('INSERT INTO observations VALUES(?,?,?,?)',(f'strategy-evaluation:{NAME}:{t.isoformat()}:{state}','STRATEGY_EVALUATION',t.isoformat(),json.dumps(payload)))
 prefix='directional-signal:2026-10-26:'+NAME+':episode'
 for k,v in [(prefix,{'evaluated_at':NOW.isoformat(),'state':'SIGNAL','strategy':NAME}),
  (prefix+':assessment',{'reason':'SHOCK_SCENARIO_BELOW_FLOOR','candidate_checks':[{'scenario_multiple':'1.725211','reason':'SHOCK_SCENARIO_BELOW_FLOOR','token':'PRIVATE'}]})]:
  db.execute('INSERT INTO metadata VALUES(?,?)',(k,json.dumps(v)))
 db.commit();db.close();before=hashlib.sha256(path.read_bytes()).hexdigest()
 result=day_summary(path,NOW+timedelta(hours=6),[NAME])
 assert result['status']=='AVAILABLE'
 assert result['signal_minutes']==5 and result['episodes']==1 and result['completed_checks']==300
 assert result['episode_reviews'][0]['best_scenario_multiple']=='1.725211'
 assert result['entry_attempts']==0 and result['filled_entries']==0
 assert 'PRIVATE' not in json.dumps(result)
 assert hashlib.sha256(path.read_bytes()).hexdigest()==before

def test_future_and_other_day_evidence_never_count_as_observed(tmp_path):
 path=tmp_path/'db';db=sqlite3.connect(path);db.executescript(SCHEMA)
 for n,t in enumerate((NOW-timedelta(days=1),NOW+timedelta(minutes=1))):
  payload={'strategy':NAME,'state':'SIGNAL','evaluated_at':t.isoformat()}
  db.execute('INSERT INTO observations VALUES(?,?,?,?)',(f'strategy-evaluation:{NAME}:{t.isoformat()}:SIGNAL','STRATEGY_EVALUATION',t.isoformat(),json.dumps(payload)))
 db.commit();db.close()
 assert day_summary(path,NOW,[NAME])['signal_minutes']==0


def test_failed_operations_sidecar_is_visible_and_evidence_is_preserved(tmp_path):
 from dhan_cas_bot.dashboard.operations import build_operations
 from dhan_cas_bot.dashboard.collect import operations_view
 target=tmp_path/'operations.json';target.write_text('broken-private-evidence')
 try:build_operations({'state_dir':str(tmp_path)},tmp_path/'snapshot.json',healthy(),NOW)
 except ValueError:pass
 else:raise AssertionError('must preserve unreadable incident history')
 assert target.read_text()=='broken-private-evidence'
 assert operations_view(tmp_path/'snapshot.json',NOW)['status']=='UNAVAILABLE'


def test_missing_funded_evaluation_and_silent_connected_book_are_flagged():
 report=healthy();report['runtime']['strategy_evaluations']=[]
 report['runtime']['feed_health']['market']['last_usable_at']=(NOW-timedelta(seconds=60)).isoformat()
 codes={r['code'] for r in fault_candidates(report,NOW)}
 assert {'STRATEGY_CHECK_STALE','OPTIONS_STALE'}<=codes


@pytest.mark.parametrize('reported_open',[None,False])
def test_missing_calendar_cannot_masquerade_as_a_normal_closed_market(reported_open):
 report=healthy(False);report['runtime']['exchange_session_open']=reported_open
 report['runtime']['strategy_evaluations'][0].update(state='INPUT_UNAVAILABLE',reason='CALENDAR_UNAVAILABLE')
 assert 'MARKET_SESSION_UNKNOWN' in {r['code'] for r in fault_candidates(report,NOW)}


def test_completed_bar_waiting_outside_strategy_window_is_not_stale():
 report=healthy()
 report['runtime']['strategy_evaluations'][0].update(
  state='WAITING',reason='OUTSIDE_STRATEGY_WINDOW',
  evaluated_at=(NOW-timedelta(minutes=10)).isoformat())
 assert 'STRATEGY_CHECK_STALE' not in {r['code'] for r in fault_candidates(report,NOW)}


def test_native_cas_status_is_reported_without_inventing_a_signal():
 from dhan_cas_bot.observation_view import cas_evaluation
 row=cas_evaluation(NOW,True,False,True)
 assert row['strategy']=='CAS_LAG_V1' and row['state']=='NOT_APPLICABLE'
 assert row['evaluated_at']==NOW.isoformat()
 assert cas_evaluation(NOW,True,True,True)['state']=='WAITING'
 assert cas_evaluation(NOW,None,True,True)['state']=='INPUT_UNAVAILABLE'
 report=healthy();report['runtime']['funded_strategies'].append('CAS_LAG_V1')
 assert 'STRATEGY_CHECK_STALE' in {r['code'] for r in fault_candidates(report,NOW)}
 report['runtime']['strategy_evaluations'].append(row)
 assert 'STRATEGY_CHECK_STALE' not in {r['code'] for r in fault_candidates(report,NOW)}
