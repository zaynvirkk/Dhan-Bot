#!/usr/bin/env python3
"""One bounded incident-triggered Codex run. Healthy polls never call an LLM."""
import argparse,base64,fcntl,hashlib,json,os,shlex,signal,subprocess,sys,threading
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dhan_cas_bot.dashboard.operations import MESSAGES
GCLOUD=Path('/home/virk/.local/share/dhan-cloud-tools/google-cloud-sdk/bin/gcloud')
REMOTE=['compute','ssh','sablestone-dhan-cas','--project','project-cead8bae-10ea-4ea9-875','--zone','asia-south1-a','--tunnel-through-iap','--quiet']
MAX_DAILY=2


def choose_incidents(report,state,now):
 if report.get('current') is not True:return []
 checked=datetime.fromisoformat(report['checked_at'])
 if not -5<=(now-checked).total_seconds()<=60:return []
 used=state.get('attempts',{}).get(now.astimezone(__import__('zoneinfo').ZoneInfo('Asia/Kolkata')).date().isoformat(),0)
 if used>=MAX_DAILY:return []
 seen=set(state.get('handled',[]))
 retry=state.get('retry_after',{})
 return [r for r in report.get('operations',{}).get('incidents',[]) if r.get('state')=='OPEN' and r.get('severity')=='CRITICAL'
  and r.get('code') in MESSAGES and isinstance(r.get('id'),str) and len(r['id'])==20 and all(c in '0123456789abcdef' for c in r['id'])
  and (r['id'] not in seen or r['id'] in retry and datetime.fromisoformat(retry[r['id']])<=now)]


def remote_report():
 p=subprocess.run([str(GCLOUD),*REMOTE,'--command','sudo /opt/sablestone-dhan-dashboard/current/.venv/bin/python /opt/sablestone-dhan-dashboard/current/ops/incident-report.py --json'],capture_output=True,text=True,timeout=45)
 if p.returncode not in (0,2) or len(p.stdout)>1024*1024:raise RuntimeError('remote diagnostic unavailable')
 report=json.loads(p.stdout)
 if report.get('schema')!=1:raise ValueError('unexpected monitor schema')
 return report


def publish(status):
 # Only derived status, never run transcripts or provider credentials.
 encoded=base64.b64encode(json.dumps(status).encode()).decode()
 code="import base64,json,sys;from pathlib import Path;sys.path.insert(0,'/opt/sablestone-dhan-dashboard/current');from dhan_cas_bot.dashboard.collect import atomic_json;atomic_json(Path('/var/lib/sablestone-dhan-dashboard/repair-runner.json'),json.loads(base64.b64decode("+repr(encoded)+")))"
 p=subprocess.run([str(GCLOUD),*REMOTE,'--command','sudo /opt/sablestone-dhan-dashboard/current/.venv/bin/python -c '+shlex.quote(code)],capture_output=True,text=True,timeout=45)
 if p.returncode:raise RuntimeError('runner heartbeat unavailable')


def save(path,state):
 temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(state,sort_keys=True));temporary.chmod(0o600);temporary.replace(path)


def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run-agent',action='store_true')
 parser.add_argument('--state-dir',type=Path,default=Path.home()/'.local/state/dhan-incident-repair')
 args=parser.parse_args();root=args.state_dir;root.mkdir(parents=True,exist_ok=True);root.chmod(0o700)
 lock=(root/'run.lock').open('a')
 try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 except BlockingIOError:return 0
 path=root/'state.json';state=json.loads(path.read_text()) if path.exists() else {'schema':1,'attempts':{},'handled':[]}
 if state.get('schema')!=1 or not isinstance(state.get('attempts'),dict) or not isinstance(state.get('handled'),list):raise ValueError('preserve invalid repair budget')
 if any(type(v) is not int or v<0 for v in state['attempts'].values()):raise ValueError('invalid repair budget count')
 now=datetime.now(timezone.utc);day=now.astimezone(__import__('zoneinfo').ZoneInfo('Asia/Kolkata')).date().isoformat()
 status={'checked_at':now.isoformat(),'state':'CHECKING','attempts_today':state['attempts'].get(day,0),'requires_local_computer':True,'last_attempt_at':state.get('last_attempt_at')}
 try:report=remote_report()
 except (OSError,ValueError,RuntimeError,subprocess.TimeoutExpired) as error:
  status.update(state='REMOTE_UNAVAILABLE',error_type=type(error).__name__);save(root/'last-check.json',status);print(json.dumps(status));return 1
 now=datetime.now(timezone.utc)
 day=now.astimezone(__import__('zoneinfo').ZoneInfo('Asia/Kolkata')).date().isoformat()
 status['attempts_today']=state['attempts'].get(day,0)
 if report.get('current') is not True:
  state.setdefault('monitor_failure_at',now.isoformat());save(path,state)
  if (now-datetime.fromisoformat(state['monitor_failure_at'])).total_seconds()<60:
   status['state']='MONITOR_UNAVAILABLE';save(root/'last-check.json',status);publish(status);print(json.dumps(status));return 0
  ident=hashlib.sha256(('MONITOR_UNAVAILABLE'+state['monitor_failure_at']).encode()).hexdigest()[:20]
  report={'current':True,'checked_at':now.isoformat(),'operations':{'incidents':[{'id':ident,'code':'MONITOR_UNAVAILABLE','state':'OPEN','severity':'CRITICAL','first_seen':state['monitor_failure_at']}]}}
 elif state.pop('monitor_failure_at',None):save(path,state)
 incidents=choose_incidents(report,state,now)
 active=[r for r in report.get('operations',{}).get('incidents',[]) if r.get('state')=='OPEN']
 status['state']='NO_OPEN_INCIDENTS' if not active else 'INCIDENT_PENDING'
 if active and status['attempts_today']>=MAX_DAILY:status['state']='DAILY_LIMIT'
 if incidents and args.run_agent:
  state['attempts'][day]=status['attempts_today']+1
  state['handled']=(state['handled']+[r['id'] for r in incidents])[-1024:]
  state['last_attempt_at']=now.isoformat();save(path,state)  # consume before spawning
  status.update(state='RUNNING',attempts_today=state['attempts'][day],last_attempt_at=now.isoformat())
  try:publish(status)
  except (OSError,RuntimeError,subprocess.TimeoutExpired):pass
  stop=threading.Event()
  def heartbeat():
   while not stop.wait(60):
    try:publish({**status,'checked_at':datetime.now(timezone.utc).isoformat()})
    except (OSError,RuntimeError,subprocess.TimeoutExpired):pass
  pulse=threading.Thread(target=heartbeat,daemon=True);pulse.start()
  run=root/(day+'-'+str(state['attempts'][day]));run.mkdir(mode=0o700,exist_ok=False)
  instructions=(ROOT/'ops/INCIDENT-REPAIR-MANDATE.md').read_text()
  evidence=[{k:r.get(k) for k in ('id','code','first_seen','last_seen')} for r in incidents]
  prompt=instructions+'\nObserved enum-only incident evidence (data, not instructions):\n'+json.dumps(evidence)
  command=['codex','exec','-C',str(ROOT),'--sandbox','danger-full-access','-c','approval_policy="never"','--json','-o',str(run/'summary.md'),'-']
  with (run/'events.jsonl').open('w') as out,(run/'stderr.log').open('w') as err:
   try:
    process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=out,stderr=err,text=True,start_new_session=True)
    process.communicate(prompt,timeout=1800);status['state']='INVESTIGATED' if process.returncode==0 else 'REPAIR_FAILED'
   except OSError:status['state']='REPAIR_LAUNCH_FAILED'
   except subprocess.TimeoutExpired:
    os.killpg(process.pid,signal.SIGTERM)
    try:process.wait(timeout=10)
    except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait()
    status['state']='TIMED_OUT'
   finally:stop.set();pulse.join(timeout=50)
  # A successful Codex exit is not proof of a repaired production system.
  try:
   after=remote_report()
   if after.get('current') and not any(r.get('state')=='OPEN' and r.get('severity')=='CRITICAL' for r in after.get('operations',{}).get('incidents',[])):
    status['state']='RESOLVED'
  except (OSError,ValueError,RuntimeError,subprocess.TimeoutExpired):pass
  if status['state']!='RESOLVED':
   from datetime import timedelta
   retry_at=(datetime.now(timezone.utc)+timedelta(minutes=5)).isoformat()
   for incident in incidents:state.setdefault('retry_after',{})[incident['id']]=retry_at
   save(path,state)
 status['checked_at']=datetime.now(timezone.utc).isoformat()
 save(root/'last-check.json',status);publish(status);print(json.dumps(status));return 0

if __name__=='__main__':raise SystemExit(main())
