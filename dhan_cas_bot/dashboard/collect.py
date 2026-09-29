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
from .data import account_view, local_snapshot, read_json, utcnow


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


async def collect(config, output):
    now = utcnow()
    report = {'schema': 1, 'collector_observed_at': now.isoformat(), 'writes_to_broker': False,
              'account': None, 'account_read_ok': False}
    try:
        report['account'] = await asyncio.wait_for(read_account(config), timeout=20)
        report['account_read_ok'] = True
    except Exception:
        # Preserve last observed values, labelled as failed/stale by the view.
        previous = read_json(output)
        report['account'] = previous.get('account') if previous else None
        report['account_error'] = 'BROKER_READ_FAILED'
    now = utcnow()
    report.update(local_snapshot(config['state_dir'], now))
    report['collector_observed_at'] = now.isoformat()
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default='/etc/sablestone-dhan/production.toml')
    parser.add_argument('--output', default='/var/lib/sablestone-dhan-dashboard/snapshot.json')
    args = parser.parse_args()
    try:
        report = asyncio.run(collect(load_config(args.config), args.output))
        print(json.dumps({'observed_at': report['collector_observed_at'], 'account_read_ok': report['account_read_ok'], 'writes': False}))
    except Exception as exc:
        print(json.dumps({'error': type(exc).__name__, 'writes': False}))
        raise SystemExit(1)


if __name__ == '__main__': main()
