#!/usr/bin/env python3
"""Explicit operator repair: confirm flat, broker cancel-all, reconcile, resume.

Never fabricates the original order outcome or grants another probe attempt.
"""
import argparse
import asyncio
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
import threading

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dhan_cas_bot.broker import DhanBroker
from dhan_cas_bot.config import load_config,load_mandate
from dhan_cas_bot.dashboard.data import read_json
from dhan_cas_bot.egress import require_expected_egress
from dhan_cas_bot.ledger import Ledger
from dhan_cas_bot.profile import require_derivatives_profile
from dhan_cas_bot.release import current_verification
from dhan_cas_bot.route_recovery import recover_owned_route


async def recovery(config,ledger,*,apply):
    state=Path(config['state_dir']);record=read_json(state/'dhan_token.json')
    if not record or record.get('account')!=config['account_id']:
        raise ValueError('matching cached broker session required')
    broker=DhanBroker(config['account_id'],record['token'],allow_writes=apply)
    try:
        require_derivatives_profile(await broker._request('GET','/profile'),config['account_id'])
        if apply:await require_expected_egress(config['expected_egress_ip'])
        return await recover_owned_route(ledger,broker,expected_account=config['account_id'],apply=apply)
    finally:await broker.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    if os.geteuid()!=0 or ROOT.parent!=Path('/opt/sablestone-dhan-dashboard/releases') or not re.fullmatch('[0-9a-f]{40}',ROOT.name):
        raise ValueError('run from the installed immutable release on the VM')
    path=Path('/etc/sablestone-dhan/production.toml');config=load_config(path);state=Path(config['state_dir'])
    if not current_verification(ROOT,state):raise ValueError('current complete release verification required')
    mandate=load_mandate(state/'mandate.json')
    if config.get('live_order_authority') is not True or mandate.live_order_authority is not True:
        raise ValueError('existing operator-funded mandate required')
    if mandate.account_id!=config['account_id']:raise ValueError('configured account and mandate account differ')
    spec=importlib.util.spec_from_file_location('upgrade',ROOT/'ops/upgrade-session-strategies.py')
    upgrade=importlib.util.module_from_spec(spec);spec.loader.exec_module(upgrade)
    pre=Ledger.__new__(Ledger);pre._lock=threading.RLock()
    pre.db=sqlite3.connect('file:'+str(state/'ledger.sqlite3')+'?mode=ro',uri=True);pre.db.row_factory=sqlite3.Row
    try:result=asyncio.run(recovery(config,pre,apply=False))
    finally:pre.close()
    if not args.apply or result.get('already_resolved'):
        print(json.dumps(result),flush=True);return
    original=path.read_bytes();stat=(state/'ledger.sqlite3').stat()
    stop_bound=Path('/run/systemd/system/dhan-cas.service.d/99-route-recovery-stop.conf')
    if stop_bound.exists():raise ValueError('another route recovery is in progress')
    stop_bound.parent.mkdir(parents=True,exist_ok=True);stop_bound.write_text('[Service]\nTimeoutStopSec=12\n')
    ledger=None;lock=None;stopped=False
    try:
        upgrade.systemctl('daemon-reload');stopped=True;upgrade.systemctl('stop','dhan-cas.service')
        lock=os.open(state/'writer.lock',os.O_CREAT|os.O_RDWR,0o600);fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if path.read_bytes()!=original:raise ValueError('configuration changed during repair')
        ledger=Ledger(state/'ledger.sqlite3')
        result=asyncio.run(recovery(config,ledger,apply=True))
        print(json.dumps({**result,'source':ROOT.name}),flush=True)
    finally:
        if ledger:ledger.close()
        if lock is not None:os.close(lock)
        # A root-run maintenance connection must not leave root-owned WAL files
        # behind when the unprivileged writer resumes.
        for suffix in ('','-wal','-shm'):
            file=state/('ledger.sqlite3'+suffix)
            if file.exists():os.chown(file,stat.st_uid,stat.st_gid)
        stop_bound.unlink(missing_ok=True);upgrade.systemctl('daemon-reload')
        if stopped:upgrade.systemctl('start','dhan-cas.service');upgrade.systemctl('is-active','--quiet','dhan-cas.service')


if __name__=='__main__':
    try:main()
    except Exception as exc:
        from dhan_cas_bot.broker import request_failure_receipt
        from dhan_cas_bot.domain import ContractError
        report={'resolved':False,**request_failure_receipt(exc)}
        if isinstance(exc,ContractError):report['reason']=str(exc)
        print(json.dumps(report),file=sys.stderr)
        raise SystemExit(1)
