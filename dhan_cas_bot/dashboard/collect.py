"""Read-only sidecar. Uses the daemon's cached token; never mints or rotates it."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sqlite3
from pathlib import Path
import tempfile
import time

from dhan_cas_bot.broker import DhanBroker
from dhan_cas_bot.config import load_config
from .data import account_view, daily_monitor_view, freshness, local_snapshot, read_json, shared_account, utcnow, seconds_view, order_purposes
from .history import advance_history
from .session_audit import append_session_audit


async def read_account(config):
    record = read_json(Path(config['state_dir'])/'dhan_token.json')
    if not record or record.get('account') != config['account_id'] or not isinstance(record.get('token'), str):
        raise ValueError('No matching daemon token')
    broker = DhanBroker(config['account_id'], record['token'], 'https://api.dhan.co/v2', allow_writes=False)
    try:
        profile = await broker._request('GET', '/profile')
        if not isinstance(profile, dict) or str(profile.get('dhanClientId')) != config['account_id']:
            raise ValueError('Account mismatch')
        funds = await broker.funds()
        positions = await broker.positions()
        orders = await broker.orders()
        purposes={}
        try:
            with sqlite3.connect('file:'+str(Path(config['state_dir'])/'ledger.sqlite3')+'?mode=ro',uri=True,timeout=.2) as db:
                purposes=order_purposes(db)
        except sqlite3.Error:pass
        return account_view(funds, positions, orders, utcnow(),purposes=purposes)
    finally:
        await broker.close()


def projection(config, previous, *, checked=None, monitor=None):
    now = utcnow()
    primary = shared_account(read_json(Path(config['state_dir'])/'account-observation.json'), now)
    report = {'schema': 1, 'collector_observed_at': now.isoformat(), 'writes_to_broker': False,
              'account': None, 'account_read_ok': False}
    if primary is not None:
        report.update(primary, account_source='trader')
        if primary['account'] is None:
            report['account'] = previous.get('account')
    elif checked:
        report.update(account=checked.get('account') or previous.get('account'),
                      account_read_ok=checked['ok'] and freshness(checked['observed_at'], now, 60)['fresh'], account_source='independent')
    else:
        report['account'] = previous.get('account')
    if not report['account_read_ok']:
        report['account_error'] = ('BROKER_READ_FAILED' if primary is not None or (checked and not checked['ok'])
            else 'ACCOUNT_OBSERVATION_STALE' if checked else 'ACCOUNT_OBSERVATION_UNAVAILABLE')
    if checked:
        report['independent_check'] = {'observed_at': checked['observed_at'], 'ok': checked['ok']}
    report.update(local_snapshot(config['state_dir'], now))
    report['daily_monitor'] = daily_monitor_view(monitor, now)
    runtime=report.get('runtime') or {}
    candidate=Path(__file__).resolve().parents[2].name
    report['release']={'dashboard_source':candidate if len(candidate)==40 and all(c in '0123456789abcdef' for c in candidate) else None,
        'funded_source':runtime.get('source_commit'),'required_runtime_revision':9,
        'funded_runtime_revision':runtime.get('runtime_revision'),
        'upgrade_required':runtime.get('fresh') is True and (runtime.get('runtime_revision') or 0)<9}
    return report


def atomic_json(output, report):
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.snapshot-', dir=target.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(report, stream, allow_nan=False, sort_keys=True)
            stream.flush(); os.fsync(stream.fileno())
        os.chmod(temporary, 0o640)
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)
    return report


def write_report(output, report, *, embed_history=True,history_cache=None,update_history=True):
    """History failures cannot stop current monitoring or modify the trader."""
    if update_history:report={**report,'session_audit_status':append_session_audit(output,report,utcnow())}
    history_path = Path(output).with_name('history.json')
    try:
        previous = history_cache if history_cache is not None else read_json(history_path)
        if previous is None and history_path.exists():
            raise ValueError('unreadable history; preserve existing evidence')
        history = advance_history(previous, report, utcnow()) if update_history else previous
        if history is None:raise ValueError('history unavailable')
        if history != previous:
            atomic_json(history_path, history)
        report = {**report, 'history': history}
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        report = {**report, 'history': {'status': 'UNAVAILABLE', 'days': [], 'events': []}}
    # A live quote snapshot must not copy the entire retained journal. Full
    # journal requests load the separate allowlisted file at the HTTP boundary.
    compact={k:v for k,v in report.items() if k!='history'}
    compact.update(history_external=True,history_status=report['history'].get('status','UNAVAILABLE'))
    atomic_json(output,report if embed_history else compact)
    return report


def history_signature(report):
    runtime,account,ledger=(report.get(k) or {} for k in ('runtime','account','ledger'))
    return json.dumps({'runtime':{k:runtime.get(k) for k in ('state','reason','authority','account_snapshot_fresh','broker_route_verified')},
        'account':{k:account.get(k) for k in ('available_cash','open_position_count','order_count')},
        'counts':ledger.get('counts'),'settled':ledger.get('cash_reconciliation'),
        'phase':(runtime.get('observation') or {}).get('phase'),
        'strategies':[(r.get('strategy'),r.get('state'),r.get('reason'),r.get('evaluated_at') if r.get('state')=='SIGNAL' else None)
                      for r in runtime.get('strategy_evaluations',[]) if isinstance(r,dict)]},sort_keys=True)


async def check_account(config):
    try:
        account = await asyncio.wait_for(read_account(config), timeout=20)
        return {'ok': True, 'account': account, 'observed_at': utcnow().isoformat()}
    except Exception:
        return {'ok': False, 'account': None, 'observed_at': utcnow().isoformat()}


def independent_check_due(primary,checked,now):
    return checked is None or primary is None or not freshness(checked['observed_at'],now,300)['fresh']


async def collect(config, output):
    previous = read_json(output) or {}
    primary = shared_account(read_json(Path(config['state_dir'])/'account-observation.json'), utcnow())
    checked = await check_account(config) if primary is None else None
    report=projection(config, previous, checked=checked, monitor=read_json(Path(output).with_name('daily-monitor.json')))
    from .learning import build_learning
    atomic_json(Path(output).with_name('learning.json'),build_learning(config,output,report,utcnow()))
    return write_report(output, report)


async def watch(config, output):
    """Publish local state each second, independently of slow verification GETs."""
    checked = None
    async def verify():
        nonlocal checked
        while True:
            primary = shared_account(read_json(Path(config['state_dir'])/'account-observation.json'), utcnow())
            # Reassess local shared-source health without making extra API calls.
            # A source lost just after a successful check cannot strand the
            # fallback for five minutes while its own observation expires.
            if independent_check_due(primary,checked,utcnow()):
                checked = await check_account(config)
            await asyncio.sleep(15)
    async def learning():
        from .learning import build_learning
        while True:
            value=await asyncio.to_thread(build_learning,config,output,read_json(output) or {},utcnow())
            atomic_json(Path(output).with_name('learning.json'),value)
            await asyncio.sleep(30)
    learning_task=asyncio.create_task(learning())
    task = asyncio.create_task(verify())
    history_cache=None
    last_history_time=-float('inf')
    last_signature=None
    try:
        while True:
            previous = read_json(output) or {}
            report=projection(config,previous,checked=checked,monitor=read_json(Path(output).with_name('daily-monitor.json')))
            report['seconds_experiments']=seconds_view(read_json(Path(output).with_name('seconds-strategies.json')),utcnow())
            signature=history_signature(report)
            due=signature!=last_signature or time.monotonic()-last_history_time>=5
            result=write_report(output,report,embed_history=False,history_cache=history_cache,update_history=due)
            history_cache=result['history'] if result['history'].get('status')=='AVAILABLE' else None
            if due:last_history_time=time.monotonic();last_signature=signature
            await asyncio.sleep(1)
    finally:
        task.cancel();learning_task.cancel()
        await asyncio.gather(task,learning_task, return_exceptions=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default='/etc/sablestone-dhan/production.toml')
    parser.add_argument('--output', default='/var/lib/sablestone-dhan-dashboard/snapshot.json')
    parser.add_argument('--watch', action='store_true')
    args = parser.parse_args()
    try:
        if args.watch:
            asyncio.run(watch(load_config(args.config), args.output))
            return
        report = asyncio.run(collect(load_config(args.config), args.output))
        print(json.dumps({'observed_at': report['collector_observed_at'], 'account_read_ok': report['account_read_ok'], 'writes': False}))
    except Exception as exc:
        print(json.dumps({'error': type(exc).__name__, 'writes': False}))
        raise SystemExit(1)


if __name__ == '__main__': main()
