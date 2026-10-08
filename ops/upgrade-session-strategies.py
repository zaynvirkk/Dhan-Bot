#!/usr/bin/env python3
"""Operator-run upgrade of an already-funded service. Defaults to read-only checks."""
import argparse
import asyncio
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import tomllib

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dhan_cas_bot.config import load_config,load_mandate
from dhan_cas_bot.broker import DhanBroker
from dhan_cas_bot.dashboard.data import read_json
from dhan_cas_bot.profile import require_derivatives_profile
from dhan_cas_bot.release import run_verification,current_verification
from dhan_cas_bot.session_strategies import STRATEGIES


def arguments(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true',help='Operator approval to restart the already-funded trader on these session strategies')
    return parser.parse_args(argv)


def require_existing_authority(config,mandate_authority):
    if config.get('live_order_authority') is not True or mandate_authority is not True:
        raise ValueError('This upgrade requires an existing funded mandate; it does not activate an account')


def amend_strategies(text):
    parsed=tomllib.loads(text)
    replacement='strategies = '+json.dumps(list(STRATEGIES))
    if 'strategies' in parsed:
        head,sep,tail=text.partition('\n[')
        pattern=r'(?m)^strategies\s*=\s*\[[^\n]*\][^\n]*$'
        if len(re.findall(pattern,head))!=1:
            raise ValueError('Strategy assignment requires a single unambiguous top-level line')
        updated=re.sub(pattern,lambda _:replacement,head)+sep+tail
    else:
        updated=replacement+'\n'+text
    after=tomllib.loads(updated)
    before={k:v for k,v in parsed.items() if k!='strategies'}
    if {k:v for k,v in after.items() if k!='strategies'}!=before:
        raise ValueError('Upgrade would change unrelated configuration')
    return updated


async def flat_account(config):
    record=read_json(Path(config['state_dir'])/'dhan_token.json')
    if not record or record.get('account')!=config['account_id']:
        raise ValueError('No matching cached broker token')
    broker=DhanBroker(config['account_id'],record['token'],allow_writes=False)
    try:
        require_derivatives_profile(await broker._request('GET','/profile'),config['account_id'])
        positions=await broker.positions()
        orders=await broker.orders()
        if any(int(p.get('netQty',p.get('netQuantity',0))) for p in positions):
            raise ValueError('Upgrade requires a flat broker account')
        if any(o.get('orderStatus') not in {'TRADED','CANCELLED','REJECTED','EXPIRED'} for o in orders):
            raise ValueError('Upgrade requires no pending broker orders')
    finally:
        await broker.close()


def atomic(path,data,mode,owner):
    fd,tmp=tempfile.mkstemp(prefix='.strategy-upgrade-',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as f:
            f.write(data);f.flush();os.fsync(f.fileno())
        os.chmod(tmp,mode);os.chown(tmp,*owner);os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)


def restore_files(records, *, changed):
    # A preflight/lock failure must not overwrite a concurrent operator edit.
    if not changed:
        return
    for path,data,mode,owner in records:
        if data is None:
            path.unlink(missing_ok=True)
        else:
            atomic(path,data,mode,owner)


def systemctl(*args):
    subprocess.run(['systemctl',*args],check=True,stdout=subprocess.DEVNULL)


def main():
    args=arguments()
    if os.geteuid()!=0 or ROOT.parent!=Path('/opt/sablestone-dhan-dashboard/releases') or not re.fullmatch('[0-9a-f]{40}',ROOT.name):
        raise ValueError('Run with sudo from the installed immutable release on the Dhan VM')
    path=Path('/etc/sablestone-dhan/production.toml')
    config=load_config(path);state=Path(config['state_dir'])
    require_existing_authority(config,load_mandate(state/'mandate.json').live_order_authority)
    observer=read_json('/var/lib/sablestone-dhan-dashboard/daily-monitor.json') or {}
    from dhan_cas_bot.dashboard.data import daily_monitor_view,utcnow
    observation=daily_monitor_view(observer,utcnow())
    if not observation or not observation['fresh'] or observer.get('input_error') or not observation.get('opening') or not observation.get('previous_close'):
        raise ValueError('A fresh daily monitor with verified opening and previous-close bars is required')
    original=path.read_bytes();updated=amend_strategies(original.decode()).encode()
    stat=path.stat()
    asyncio.run(flat_account(config))
    with tempfile.TemporaryDirectory(prefix='dhan-session-upgrade-') as temporary:
        # Runs the exact full suite and mutations; no marker or evidence is invented.
        verified=run_verification(ROOT,temporary)
        if not args.apply:
            print(json.dumps({'checks_passed':True,'applied':False,'writes_to_broker':False,'strategies':list(STRATEGIES),'tests':verified['total_count']}))
            return
        override=Path('/etc/systemd/system/dhan-cas.service.d/95-session-strategies.conf')
        prior_override=override.read_bytes() if override.exists() else None
        marker=state/'software_verified.json'
        prior_marker=marker.read_bytes() if marker.exists() else None
        owner=(state.stat().st_uid,state.stat().st_gid)
        records=[(path,original,stat.st_mode & 0o777,(stat.st_uid,stat.st_gid)),
                 (override,prior_override,0o644,(0,0)), (marker,prior_marker,0o600,owner)]
        changed=False
        systemctl('stop','dhan-cas.service')
        lock=os.open(state/'writer.lock',os.O_CREAT|os.O_RDWR,0o600)
        try:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            if path.read_bytes()!=original:
                raise ValueError('Configuration changed during checks; retry against current configuration')
            asyncio.run(flat_account(config))
            override.parent.mkdir(parents=True,exist_ok=True)
            changed=True
            atomic(path,updated,stat.st_mode & 0o777,(stat.st_uid,stat.st_gid))
            unit=f'[Service]\nWorkingDirectory={ROOT}\nExecStart=\nExecStart={ROOT}/.venv/bin/dhan-cas run --mode AUTO_LIVE --config {path}\n'
            atomic(override,unit.encode(),0o644,(0,0))
            atomic(marker,(Path(temporary)/'software_verified.json').read_bytes(),0o600,owner)
            if not current_verification(ROOT,state):
                raise ValueError('Verification marker does not match installed source')
        except Exception:
            os.close(lock)
            restore_files(records,changed=changed)
            systemctl('daemon-reload')
            systemctl('start','dhan-cas.service')
            raise
        else:
            os.close(lock)
        try:
            systemctl('daemon-reload')
            systemctl('start','dhan-cas.service')
            systemctl('is-active','--quiet','dhan-cas.service')
        except Exception:
            systemctl('stop','dhan-cas.service')
            restore_files(records,changed=changed)
            systemctl('daemon-reload')
            systemctl('start','dhan-cas.service')
            raise
        print(json.dumps({'applied':True,'strategies':list(STRATEGIES),'source':ROOT.name,
                          'existing_mandate_preserved':True,'route_and_signal_checks_still_required':True}))


if __name__=='__main__':
    try:main()
    except Exception as exc:
        # Avoid dumping broker responses, private config, or credentials.
        print(json.dumps({'applied':False,'error_type':type(exc).__name__}),file=sys.stderr)
        raise SystemExit(1)
