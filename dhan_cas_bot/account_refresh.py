"""One background account reader; WebSocket events invalidate, REST reconciles."""
from __future__ import annotations

import asyncio
from collections import OrderedDict
from datetime import datetime, timezone
import hashlib
import json
import time

from .orders import ReconciliationChanged, account_changed


class AccountRefresh:
    MAX_AGE = 5.0

    def __init__(self, runtime, wake, *, busy, publish=None, clock=time.monotonic):
        self.runtime, self.wake, self.busy = runtime, wake, busy
        self.publish, self.clock = publish, clock
        self.requested = asyncio.Event()
        self.seen_events = OrderedDict()
        self.observed = None
        self.revision = None
        self.healthy = False
        runtime.account_refresh = self
        runtime.ledger.account_refresh = self.request
        self.request()

    def request(self):
        self.requested.set()

    @property
    def fresh(self):
        return bool(self.healthy and self.observed is not None
                    and 0 <= self.clock()-self.observed <= self.MAX_AGE
                    and self.revision == self.runtime.ledger.account_revision)

    def invalidate(self):
        self.healthy = False
        account_changed(self.runtime.ledger)
        self.wake.set()

    def order_event(self, epoch, data):
        # Notifications have cumulative quantities, not a unique exchange trade
        # ID. Never invent fills from these messages, including replayed ones.
        digest = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).digest()
        identity = (epoch, digest)
        telemetry = self.runtime.telemetry
        if identity in self.seen_events:
            telemetry.reason('DUPLICATE_ORDER_EVENT')
            return
        self.seen_events[identity] = None
        if len(self.seen_events) > 2048:
            self.seen_events.popitem(last=False)
        telemetry.reason('ORDER_EVENT')
        self.invalidate()

    async def refresh(self):
        runtime = self.runtime
        started = self.clock()
        observed_at = datetime.now(timezone.utc)
        revision = runtime.ledger.account_revision
        funds = None
        try:
            funds = await runtime.broker.funds()
            if funds.broker_account != runtime.mandate.account_id:
                raise ValueError('account mismatch')
        except Exception:
            funds = None
        # A cash endpoint failure must not suppress management of held longs.
        positions_started = self.clock()
        snapshot = await runtime.orders.reconcile(expected_revision=revision)
        runtime.reconciled = snapshot
        self.revision = snapshot['revision']
        self.observed, self.healthy = positions_started, True
        runtime.status.current_account_funded = bool(funds and funds.spendable_cash > 0)
        if funds is None:
            runtime.status.reason = 'ACCOUNT_FUNDS_UNAVAILABLE'
        elif runtime.status.reason.startswith('ACCOUNT_FUNDS_UNAVAILABLE'):
            runtime.status.reason = ''
        if runtime.status.state == 'RECOVERING' and not snapshot['unresolved']:
            runtime.status.state = 'ARMED_WAITING_SIGNAL'
        runtime.telemetry.sample('reconcile_ms', (self.clock()-started)*1000)
        if self.publish:
            self.publish(funds, snapshot, observed_at)
        self.wake.set()

    async def run(self):
        while True:
            # Clear before the await: a write/notification during the read must
            # trigger another pass, not disappear at the end of this one.
            self.requested.clear()
            try:
                await self.refresh()
            except ReconciliationChanged:
                self.healthy = False
                self.runtime.telemetry.reason('RECONCILE_SUPERSEDED')
                self.request()
            except Exception:
                self.healthy = False
                self.runtime.status.current_account_funded = False
                self.runtime.status.reason = 'RECOVERY_REQUIRED:ACCOUNT_READ_FAILED'
                self.runtime.telemetry.reason('RECONCILE_FAILED')
                self.wake.set()
                # Bound retries even if a failing endpoint completes immediately.
                await asyncio.sleep(.4)
            interval = .4 if self.busy() else 5.0
            try:
                await asyncio.wait_for(self.requested.wait(), interval)
            except asyncio.TimeoutError:
                pass
