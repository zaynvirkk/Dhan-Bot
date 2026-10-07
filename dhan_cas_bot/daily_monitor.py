"""Observe daily strategies without an OMS, order endpoint, or trading ledger."""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
from json import loads as decode_json
import os
from pathlib import Path

import httpx

from .config import load_config
from .dashboard.collect import atomic_json
from .dashboard.data import read_json
from .rules import RuleSource, DHAN_MASTER_URL, NSE_FREEZE_URL
from .session_strategies import GAP, REBOUND, IST, Evaluation, evaluate
from .strategy_inputs import CalendarSource, MinuteSource, selected_contracts


class ChartReader:
    """A capability limited to historical charts, even if its caller is wrong."""
    def __init__(self, token, *, client):
        self.token, self.client = token, client

    async def _request(self, method, path, *, json):
        if (method, path) != ('POST', '/charts/intraday'):
            raise ValueError('Only the chart endpoint is available')
        response = await self.client.post('https://api.dhan.co/v2/charts/intraday',
            headers={'access-token': self.token}, json=json, follow_redirects=False)
        response.raise_for_status()
        return decode_json(response.text, parse_float=Decimal)


def serializable(value):
    if isinstance(value, (datetime,)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    raise TypeError('Unsupported monitor value')


def monitor_report(now, calendar, spot, future, expiries, *, error=None):
    local = now.astimezone(IST)
    rows=[]
    for strategy in (GAP, REBOUND):
        sample = (Evaluation(strategy, 'UNKNOWN', 'STRATEGY_INPUT_UNAVAILABLE', local)
                  if error else evaluate(strategy, now, calendar, spot, future, expiries))
        rows.append({**asdict(sample), 'enabled': True})
    latest = max((at for at in spot if at <= now), default=None)
    opening = spot.get(calendar.opens+timedelta(minutes=1)) if calendar and calendar.opens else None
    previous = spot.get(calendar.previous_spot_closes or calendar.previous_closes) if calendar else None
    report = {'schema':1, 'observed_at':now, 'mode':'READ_ONLY', 'writes_to_broker':False,
              'strategies':[GAP, REBOUND], 'strategy_evaluations':rows,
              'calendar_checked_at':calendar.checked_at if calendar else None,
              'session_open':calendar.opens if calendar else None,
              'session_close':calendar.closes if calendar else None,
              'exchange_open':calendar.is_open(now) if calendar else None,
              'expiries':sorted(expiries), 'input_error':error,
              'spot_at':latest, 'spot':spot[latest].close if latest else None,
              'opening':opening.open if opening else None,
              'previous_close':previous.close if previous else None,
              'spot_bars':len(spot), 'future_bars':len(future)}
    return json.loads(json.dumps(report,default=serializable))


class DailyMonitor:
    def __init__(self, config, token, *, now_fn=None):
        self.config=config
        self.calendar_source=CalendarSource(token)
        self.now=now_fn or (lambda:datetime.now(timezone.utc))
        self.calendar=None
        self.metadata_day=None
        self.expiries=set()
        self.future_id=None
        self.closed_snapshot=None
        self.last_decisions={}

    async def refresh(self):
        now=self.now()
        local=now.astimezone(IST)
        spot,future={},{}
        error=None
        try:
            if self.calendar is None or not self.calendar.fresh(now) or (now-self.calendar.checked_at).total_seconds()>=3600:
                self.calendar=None
                self.closed_snapshot=None
                self.calendar=await self.calendar_source.fetch(now)
            if self.metadata_day!=local.date():
                self.expiries=set()
                source=RuleSource(timeout=15)
                master=await source.fetch(DHAN_MASTER_URL)
                freeze=await source.fetch(NSE_FREEZE_URL)
                contracts,self.future_id=selected_contracts(master.payload,source.parse_freeze(freeze.payload),local.date())
                self.expiries={i.expiry for i in contracts}
                self.metadata_day=local.date()
            if self.closed_snapshot is not None and not self.calendar.is_open(now):
                spot,future=self.closed_snapshot
            else:
                record=read_json(Path(self.config['state_dir'])/'dhan_token.json')
                if not record or record.get('account')!=self.config['account_id'] or not isinstance(record.get('token'),str):
                    raise ValueError('Matching cached token unavailable')
                async with httpx.AsyncClient(timeout=10,follow_redirects=False) as client:
                    minutes=MinuteSource(ChartReader(record['token'],client=client),now_fn=self.now)
                    end=min(now,self.calendar.spot_closes) if self.calendar.spot_closes else self.calendar.previous_spot_closes or self.calendar.previous_closes
                    spot=await minutes.fetch('13','IDX_I','INDEX',self.calendar.previous_opens,end)
                    if self.calendar.is_open(now) and local.hour<12 and self.future_id:
                        await asyncio.sleep(.3)
                        future=await minutes.fetch(self.future_id,'NSE_FNO','FUTIDX',self.calendar.opens,now,oi=True)
                if not self.calendar.is_open(now):
                    self.closed_snapshot=(spot,future)
        except Exception:
            # No exception body, credential, account ID or provider URL is published.
            error='INPUTS_UNAVAILABLE'
            spot,future={},{}
        report=monitor_report(now,self.calendar,spot,future,self.expiries,error=error)
        for row in report['strategy_evaluations']:
            if row['state'] in ('SIGNAL','NO_SIGNAL','UNKNOWN'):
                self.last_decisions[row['strategy']]=row
        # These are observations actually made by this process, never backfilled.
        report['last_decisions']=[v for v in self.last_decisions.values()
                                  if datetime.fromisoformat(v['evaluated_at']).astimezone(IST).date()==local.date()]
        return report


async def run(config, output, *, once=False):
    monitor=DailyMonitor(config,os.environ.get('UPSTOX_ANALYTICS_TOKEN',''))
    while True:
        report=await monitor.refresh()
        atomic_json(output,report)
        if once:
            return report
        now=datetime.now(timezone.utc)
        await asyncio.sleep(max(2,min(60,62-now.second-now.microsecond/1e6)))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',default='/etc/sablestone-dhan/production.toml')
    parser.add_argument('--output',default='/var/lib/sablestone-dhan-dashboard/daily-monitor.json')
    parser.add_argument('--once',action='store_true')
    args=parser.parse_args()
    if os.environ.get('DHAN_BROKER_READ_ONLY')!='1':
        parser.error('DHAN_BROKER_READ_ONLY=1 is required')
    asyncio.run(run(load_config(args.config),args.output,once=args.once))


if __name__=='__main__':
    main()
