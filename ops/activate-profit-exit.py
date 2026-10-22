#!/usr/bin/env python3
"""Explicit operator upgrade; retain/reconcile the managed long, no trade probe."""
import argparse,asyncio,fcntl,importlib.util,json,os,re,sqlite3,subprocess,sys,tempfile,threading
from pathlib import Path
from datetime import datetime,timezone
from decimal import Decimal

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from dhan_cas_bot.config import load_config,load_mandate
from dhan_cas_bot.broker import DhanBroker
from dhan_cas_bot.ledger import Ledger
from dhan_cas_bot.profit_activation import amend_config,require_managed
from dhan_cas_bot.funded_activation import amend_funded,amend_roster
from dhan_cas_bot.release import run_verification,current_verification
from dhan_cas_bot.dashboard.data import read_json


async def account(config,ledger):
    record=read_json(Path(config['state_dir'])/'dhan_token.json')
    if not record or record.get('account')!=config['account_id']:raise ValueError('matching cached session required')
    broker=DhanBroker(config['account_id'],record['token'],allow_writes=False)
    try:
        positions=await broker.positions();orders=await broker.orders()
        rows=list(ledger.db.execute("SELECT * FROM lifecycles WHERE state!='CLOSED'"))
        if len(rows)>1:raise ValueError('multiple lifecycle obligations')
        active=rows[0] if rows else None
        totals=ledger.lifecycle_totals(active['lifecycle_id']) if active else None
        pending=bool(ledger.pending_intents()) or any(o.get('orderStatus') not in {'TRADED','CANCELLED','REJECTED','EXPIRED'} for o in orders)
        require_managed(active,totals,positions,pending)
        return active
    finally:await broker.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--apply',action='store_true');parser.add_argument('--retain',default='0.50')
    parser.add_argument('--funded-only',nargs='*',default=None,help='Explicit subset permitted to submit new entries; scans remain configured.')
    parser.add_argument('--scan-only',nargs='+',default=None,help='Replace scanned roster; requires an explicit --funded-only subset, including an empty subset.')
    parser.add_argument('--extra-route-attempt-on',default=None,help='Explicit operator grant of one extra route attempt on the named current IST date. Cash caps and normal limits stay unchanged.')
    args=parser.parse_args();retain=Decimal(args.retain)
    if args.extra_route_attempt_on:
        from dhan_cas_bot.session_strategies import IST
        if args.extra_route_attempt_on!=datetime.now(IST).date().isoformat():raise ValueError('extra attempt date must be today in IST')
    if args.scan_only is not None and args.funded_only is None:parser.error('--scan-only requires --funded-only')
    if os.geteuid()!=0 or ROOT.parent!=Path('/opt/sablestone-dhan-dashboard/releases') or not re.fullmatch('[0-9a-f]{40}',ROOT.name):
        raise ValueError('run from the installed immutable release on the VM')
    spec=importlib.util.spec_from_file_location('upgrade',ROOT/'ops/upgrade-session-strategies.py');upgrade=importlib.util.module_from_spec(spec);spec.loader.exec_module(upgrade)
    path=Path('/etc/sablestone-dhan/production.toml');config=load_config(path);state=Path(config['state_dir']);original=path.read_bytes();stat=path.stat()
    upgrade.require_existing_authority(config,load_mandate(state/'mandate.json').live_order_authority)
    updated=amend_config(original.decode(),retain).encode()
    if args.scan_only is not None:updated=amend_roster(updated.decode(),args.scan_only,args.funded_only).encode()
    elif args.funded_only is not None:updated=amend_funded(updated.decode(),args.funded_only).encode()
    with tempfile.TemporaryDirectory(prefix='dhan-profit-activation-') as temporary:
        print('Verifying the complete release while the existing trader continues managing its position.',flush=True)
        verified=run_verification(ROOT,temporary)
        print(json.dumps({'software_tests':verified['total_count'],'acceptance':verified['case_count']}),flush=True)
        ledger=Ledger.__new__(Ledger);ledger._lock=threading.RLock()
        ledger.db=sqlite3.connect('file:'+str(state/'ledger.sqlite3')+'?mode=ro',uri=True)
        ledger.db.row_factory=sqlite3.Row;ledger.db.execute('PRAGMA query_only=ON')
        try:asyncio.run(account(config,ledger))
        finally:ledger.close()
        if not args.apply:print(json.dumps({'applied':False,'checks_passed':True}));return
        override=Path('/etc/systemd/system/dhan-cas.service.d/95-session-strategies.conf');marker=state/'software_verified.json'
        owner=(state.stat().st_uid,state.stat().st_gid)
        records=[(path,original,stat.st_mode&0o777,(stat.st_uid,stat.st_gid)),
                 (override,override.read_bytes() if override.exists() else None,0o644,(0,0)),
                 (marker,marker.read_bytes() if marker.exists() else None,0o600,owner)]
        changed=False;stopped=False;lock=None;ledger=None;migrated=None;extra_added=None
        stop_bound=Path('/run/systemd/system/dhan-cas.service.d/99-profit-upgrade-stop.conf')
        if stop_bound.exists():raise ValueError('another upgrade is in progress')
        stop_bound.parent.mkdir(parents=True,exist_ok=True);stop_bound.write_text('[Service]\nTimeoutStopSec=12\n')
        try:
            upgrade.systemctl('daemon-reload')
            stopped=True;upgrade.systemctl('stop','dhan-cas.service')
            lock=os.open(state/'writer.lock',os.O_CREAT|os.O_RDWR,0o600);fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            if path.read_bytes()!=original:raise ValueError('concurrent configuration change')
            ledger=Ledger(state/'ledger.sqlite3');active=asyncio.run(account(config,ledger))
            if args.extra_route_attempt_on:
                from dhan_cas_bot.route import grant_extra_attempt
                key='probe.extra_attempt:'+args.extra_route_attempt_on
                old=ledger.metadata(key)
                grant_extra_attempt(ledger,args.extra_route_attempt_on,load_mandate(state/'mandate.json').probe_max_attempts_per_session,datetime.now(timezone.utc))
                if old is None:extra_added=key
            # New policy starts from future fresh quotes. Do not replay the old
            # peak into an immediate sale against the operator's latest intent.
            if active and json.loads(active['payload']).get('strategy')!='VOLATILITY_SHOCK_V1':
                payload=json.loads(active['payload'])
                policy={'version':'NET_PROFIT_RATCHET_V1','retain':str(retain)}
                if payload.get('profit_exit') and payload['profit_exit']!=policy:
                    raise ValueError('different recorded profit policy requires a separate migration')
                if not payload.get('profit_exit'):
                    migrated=(active['lifecycle_id'],active['payload']);payload['profit_exit']=policy
                    payload['profit_policy_activated_at']=datetime.now(timezone.utc).isoformat()
                    with ledger.transaction() as db:db.execute('UPDATE lifecycles SET payload=? WHERE lifecycle_id=?',(json.dumps(payload),active['lifecycle_id']))
            changed=True
            override.parent.mkdir(parents=True,exist_ok=True)
            upgrade.atomic(path,updated,stat.st_mode&0o777,(stat.st_uid,stat.st_gid))
            upgrade.atomic(override,upgrade.service_override(ROOT,path).encode(),0o644,(0,0))
            upgrade.atomic(marker,(Path(temporary)/'software_verified.json').read_bytes(),0o600,owner)
            if not current_verification(ROOT,state):raise ValueError('release verification mismatch')
            ledger.close();ledger=None;os.close(lock);lock=None
            stop_bound.unlink();upgrade.systemctl('daemon-reload');upgrade.systemctl('start','dhan-cas.service')
            upgrade.systemctl('is-active','--quiet','dhan-cas.service')
        except Exception:
            if ledger is None and (migrated or extra_added):
                upgrade.systemctl('stop','dhan-cas.service');ledger=Ledger(state/'ledger.sqlite3')
            if ledger and migrated:
                with ledger.transaction() as db:db.execute('UPDATE lifecycles SET payload=? WHERE lifecycle_id=?',(migrated[1],migrated[0]))
            if ledger and extra_added:
                with ledger.transaction() as db:db.execute('DELETE FROM metadata WHERE key=?',(extra_added,))
            if ledger:ledger.close();ledger=None
            if lock is not None:os.close(lock);lock=None
            upgrade.restore_files(records,changed=changed)
            stop_bound.unlink(missing_ok=True);upgrade.systemctl('daemon-reload')
            if stopped:upgrade.systemctl('start','dhan-cas.service')
            raise
        finally:
            if ledger:ledger.close()
            if lock is not None:os.close(lock)
            stop_bound.unlink(missing_ok=True)
        print(json.dumps({'applied':True,'source':ROOT.name,'profit_exit_policy':'NET_PROFIT_RATCHET_V1',
            'owner_specific_exit':'SHOCK_EXIT_V1' if args.scan_only==['VOLATILITY_SHOCK_V1'] else None,
            'allocation_policy':'SHOCK_FULL_CASH_V1' if args.scan_only==['VOLATILITY_SHOCK_V1'] else None,
            'scanned_strategies':args.scan_only if args.scan_only is not None else config['strategies'],
            'retention':str(retain),'existing_position_migrated_forward_only':migrated is not None,
            'funded_strategies':args.funded_only if args.funded_only is not None else config.get('funded_strategies',config['strategies']),
            'mandate_and_probe_caps_unchanged':args.extra_route_attempt_on is None,
            'normal_probe_limit_and_cash_caps_unchanged':True,'extra_route_attempt_date':args.extra_route_attempt_on,
            'broker_orders_submitted_by_upgrade':0}),flush=True)


if __name__=='__main__':
    try:main()
    except Exception as exc:
        print(json.dumps({'applied':False,'error_type':type(exc).__name__}),file=sys.stderr)
        raise SystemExit(1)
