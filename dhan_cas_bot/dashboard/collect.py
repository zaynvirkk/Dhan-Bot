"""Read-only sidecar. Uses the daemon's cached token; never mints or rotates it."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import tempfile

from dhan_cas_bot.broker import DhanBroker
from dhan_cas_bot.config import load_config
from .data import account_view, freshness, local_snapshot, read_json, shared_account, utcnow


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
        return account_view(funds, positions, orders, utcnow())
    finally:
        await broker.close()


def projection(config, previous, *, checked=None):
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
        report['account_error'] = 'BROKER_READ_FAILED'
    if checked:
        report['independent_check'] = {'observed_at': checked['observed_at'], 'ok': checked['ok']}
    report.update(local_snapshot(config['state_dir'], now))
    return report


def write_report(output, report):
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


async def check_account(config):
    try:
        account = await asyncio.wait_for(read_account(config), timeout=20)
        return {'ok': True, 'account': account, 'observed_at': utcnow().isoformat()}
    except Exception:
        return {'ok': False, 'account': None, 'observed_at': utcnow().isoformat()}


async def collect(config, output):
    previous = read_json(output) or {}
    primary = shared_account(read_json(Path(config['state_dir'])/'account-observation.json'), utcnow())
    checked = await check_account(config) if primary is None else None
    return write_report(output, projection(config, previous, checked=checked))


async def watch(config, output):
    """Publish local state each second, independently of slow verification GETs."""
    checked = None
    async def verify():
        nonlocal checked
        while True:
            checked = await check_account(config)
            # Backwards compatible with trader releases without a shared model.
            primary = shared_account(read_json(Path(config['state_dir'])/'account-observation.json'), utcnow())
            await asyncio.sleep(300 if primary is not None else 15)
    task = asyncio.create_task(verify())
    try:
        while True:
            previous = read_json(output) or {}
            write_report(output, projection(config, previous, checked=checked))
            await asyncio.sleep(1)
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


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
