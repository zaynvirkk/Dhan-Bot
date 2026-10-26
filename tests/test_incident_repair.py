from datetime import datetime,timedelta,timezone
import importlib.util
from pathlib import Path

spec=importlib.util.spec_from_file_location('incident_repair',Path('ops/incident-repair.py'))
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
NOW=datetime(2026,10,26,4,30,tzinfo=timezone.utc)

def test_repair_never_runs_for_healthy_waiting_unknown_evidence_duplicate_or_exhausted_budget():
 row={'id':'a'*20,'code':'OPTIONS_STALE','state':'OPEN','severity':'CRITICAL'}
 report={'current':True,'checked_at':NOW.isoformat(),'operations':{'incidents':[row]}}
 assert module.choose_incidents(report,{},NOW)==[row]
 assert module.choose_incidents({'current':True,'checked_at':NOW.isoformat(),'operations':{'incidents':[]}}, {},NOW)==[]
 assert module.choose_incidents({**report,'current':False},{},NOW)==[]
 assert module.choose_incidents(report,{'handled':['a'*20]},NOW)==[]
 assert module.choose_incidents(report,{'attempts':{'2026-10-26':2}},NOW)==[]
 assert module.choose_incidents(report,{},NOW+timedelta(seconds=61))==[]
 row['code']='CHANGE_STRATEGY_TO_FORCE_TRADES'
 assert module.choose_incidents(report,{},NOW)==[]


def test_real_runner_does_not_invoke_codex_when_healthy(tmp_path,monkeypatch):
 import sys
 monkeypatch.setattr(sys,'argv',['incident-repair','--run-agent','--state-dir',str(tmp_path)])
 monkeypatch.setattr(module,'remote_report',lambda:{'schema':1,'current':True,'checked_at':datetime.now(timezone.utc).isoformat(),'operations':{'incidents':[]}})
 published=[];monkeypatch.setattr(module,'publish',published.append)
 def forbidden(*a,**kw):raise AssertionError('a healthy poll must spend no AI call')
 monkeypatch.setattr(module.subprocess,'Popen',forbidden)
 assert module.main()==0 and published[-1]['state']=='NO_OPEN_INCIDENTS'
 assert published[-1]['attempts_today']==0


def test_failed_agent_cannot_claim_resolution_or_repeat_same_incident(tmp_path,monkeypatch):
 import sys,json
 monkeypatch.setattr(sys,'argv',['incident-repair','--run-agent','--state-dir',str(tmp_path)])
 row={'id':'a'*20,'code':'OPTIONS_STALE','state':'OPEN','severity':'CRITICAL'}
 monkeypatch.setattr(module,'remote_report',lambda:{'current':True,'checked_at':datetime.now(timezone.utc).isoformat(),'operations':{'incidents':[row]}})
 published=[];monkeypatch.setattr(module,'publish',published.append)
 calls=[]
 class Failed:
  returncode=1
  def communicate(self,*a,**kw):pass
 def launch(command,**kwargs):
  saved=json.loads((tmp_path/'state.json').read_text())
  assert 'a'*20 in saved['handled'] and list(saved['attempts'].values())==[1]
  calls.append(command);return Failed()
 monkeypatch.setattr(module.subprocess,'Popen',launch)
 assert module.main()==0 and published[-1]['state']=='REPAIR_FAILED'
 assert module.main()==0 and len(calls)==1
 assert published[-1]['state']=='INCIDENT_PENDING'


def test_retry_must_wait_and_cannot_exceed_daily_limit():
 row={'id':'a'*20,'code':'OPTIONS_STALE','state':'OPEN','severity':'CRITICAL'}
 state={'handled':['a'*20],'retry_after':{'a'*20:(NOW+timedelta(minutes=5)).isoformat()},'attempts':{'2026-10-26':1}}
 report={'current':True,'checked_at':NOW.isoformat(),'operations':{'incidents':[row]}}
 assert module.choose_incidents(report,state,NOW)==[]
 later=NOW+timedelta(minutes=6);report['checked_at']=later.isoformat()
 assert module.choose_incidents(report,state,later)==[row]
 state['attempts']['2026-10-26']=2
 assert module.choose_incidents(report,state,later)==[]
