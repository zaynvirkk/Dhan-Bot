"""Read-only inspection of the existing VM; no install/restart/config write."""
import base64
import json
import shlex
import subprocess
from datetime import datetime, timezone
from research.gauntlet.data import save
from .data import OUT

REMOTE = r'''
import json,os,subprocess,time,tomllib
from pathlib import Path
from datetime import datetime,timezone
import httpx
p=Path('/var/lib/sablestone-dhan')
config=tomllib.loads(Path('/etc/sablestone-dhan/production.toml').read_text())
out={'checked_at':datetime.now(timezone.utc).isoformat(),'read_only_check':True,
     'config_live_order_authority':config.get('live_order_authority'),
     'source_revision':subprocess.check_output(['git','-C','/opt/sablestone-dhan-cas-bot','rev-parse','HEAD'],text=True).strip()}
for name in ('status.json','mandate.json'):
 try:
  x=json.loads((p/name).read_text())
  out[name]={k:x[k] for k in ('state','status','phase','live_order_authority','auto_live_armed','broker_route_verified','updated_at','last_error') if k in x and k!='last_error'}
 except Exception as e:out[name]={'error':type(e).__name__}
props=subprocess.check_output(['systemctl','show','dhan-cas.service','--property=ActiveState,NRestarts,Environment','--no-pager'],text=True)
out['service']={'active': 'ActiveState=active' in props,'read_only_interlock':'DHAN_BROKER_READ_ONLY=1' in props}
try:
 record=json.loads((p/'dhan_token.json').read_text())
 out['cached_token_age_seconds']=int(time.time()-record['issued'])
 out['cache_matches_config_account']=str(record.get('account'))==str(config.get('account_id'))
 out['cache_mode']=oct((p/'dhan_token.json').stat().st_mode & 0o777)
 headers={'access-token':record['token']}
 for label,path in [('profile','/profile'),('funds','/fundlimit'),('positions','/positions'),('orders','/orders'),('trades','/trades'),('whitelist','/ip/getIP')]:
  try:
   r=httpx.get('https://api.dhan.co/v2'+path,headers=headers,timeout=12)
   x=r.json();v={'http_status':r.status_code}
   if r.status_code==200:
    if label=='profile':v.update(identity_matches=str(x.get('dhanClientId'))==str(config.get('account_id')),active_segments=x.get('activeSegment'),data_plan=x.get('dataPlan'))
    elif label=='funds':v['available_balance']=x.get('availabelBalance',x.get('availableBalance'))
    elif isinstance(x,list):v['count']=len(x)
    elif label=='whitelist':v['configured_ip_present']='34.100.255.111' in json.dumps(x)
   elif isinstance(x,dict):v['error_code']=x.get('errorCode')
   out[label]=v
  except Exception as e:out[label]={'error':type(e).__name__}
except Exception as e:out['token_probe']={'error':type(e).__name__}
print(json.dumps(out))
'''


def main():
    exe = '/home/virk/.local/share/dhan-cloud-tools/google-cloud-sdk/bin/gcloud'
    common = ['--zone=asia-south1-a', '--project=project-cead8bae-10ea-4ea9-875']
    out = {'checked_at': datetime.now(timezone.utc).isoformat(), 'writes': False}
    try:
        r = subprocess.run([exe, 'compute', 'instances', 'describe', 'sablestone-dhan-cas', *common,
                            '--format=json(status,machineType,networkInterfaces[].accessConfigs[].natIP)'],
                           capture_output=True, text=True, timeout=45)
        out['instance'] = json.loads(r.stdout) if r.returncode == 0 else {'error': 'DESCRIBE_FAILED'}
        encoded = base64.b64encode(REMOTE.encode()).decode()
        code = 'import base64;exec(base64.b64decode('+repr(encoded)+'))'
        command = 'sudo /opt/sablestone-dhan-cas-bot/.venv/bin/python -c '+shlex.quote(code)
        r = subprocess.run([exe, 'compute', 'ssh', 'sablestone-dhan-cas', *common,
                            '--tunnel-through-iap', '--quiet', '--command='+command],
                           capture_output=True, text=True, timeout=180)
        out['daemon'] = json.loads(r.stdout) if r.returncode == 0 else {'error': 'READ_ONLY_SSH_CHECK_FAILED', 'exit_code': r.returncode}
    except Exception as e:
        out['error'] = type(e).__name__
    save(OUT/'cloud_check.json', out)
    print(json.dumps(out))


if __name__ == '__main__':
    main()
