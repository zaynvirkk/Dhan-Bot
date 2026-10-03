"""Adversarial timing tests use only local fake brokers; never live orders."""
import asyncio
from decimal import Decimal
import json

import pytest

from dhan_cas_bot.account_refresh import AccountRefresh
from dhan_cas_bot.orders import OrderManager, ReconciliationChanged
from dhan_cas_bot.runtime import AutoLive
from dhan_cas_bot.ledger import Ledger
from dhan_cas_bot.telemetry import Telemetry
from .conftest import FakeBroker
from .test_ledger_orders import intent
from .acceptance.cas.support import mandate


def runtime_at(path, broker):
    return AutoLive(Ledger(path), broker, mandate(live=True), software_verified=True)


def test_slow_account_read_does_not_own_writer_lock_and_old_batch_is_discarded(tmp_path):
    async def run():
        entered, release = asyncio.Event(), asyncio.Event()
        class Broker(FakeBroker):
            async def orders(self):
                stale = list(self._orders)
                entered.set()
                await release.wait()
                return stale
        broker = Broker()
        runtime = runtime_at(tmp_path/'ledger', broker)
        work = asyncio.create_task(runtime.orders.reconcile())
        await entered.wait()
        assert not runtime.ledger.order_lock.locked()
        # A different manager (exit/route code) shares the same version and lock.
        await asyncio.wait_for(OrderManager(runtime.ledger, broker).submit(intent(), reserved_cash=Decimal('700')), .2)
        release.set()
        with pytest.raises(ReconciliationChanged):
            await work
        assert runtime.ledger.pending_intents()[0]['state'] == 'SENT'
        await runtime.orders.reconcile()
        assert not runtime.ledger.pending_intents()
        runtime.ledger.close()
    asyncio.run(run())


def test_notification_during_background_read_survives_and_duplicates_never_invent_fills(tmp_path):
    async def run():
        entered, release = asyncio.Event(), asyncio.Event()
        class Broker(FakeBroker):
            calls = 0
            async def orders(self):
                self.calls += 1
                if self.calls == 1:
                    entered.set()
                    await release.wait()
                return []
        runtime = runtime_at(tmp_path/'ledger', Broker())
        wake = asyncio.Event()
        worker = AccountRefresh(runtime, wake, busy=lambda: False)
        task = asyncio.create_task(worker.run())
        try:
            await entered.wait()
            update = {'OrderNo': 'manual', 'Status': 'PART_TRADED', 'TradedQty': 65}
            worker.order_event('epoch1', update)
            revision = runtime.ledger.account_revision
            worker.order_event('epoch1', update)
            assert runtime.ledger.account_revision == revision
            assert wake.is_set()
            assert not worker.fresh
            release.set()
            async def refreshed():
                while not worker.fresh:
                    await asyncio.sleep(.001)
            # Event wakes a second pass now, not the five-second fallback.
            await asyncio.wait_for(refreshed(), .3)
            assert runtime.broker.calls == 2
            assert runtime.ledger.db.execute('SELECT COUNT(*) FROM fills').fetchone()[0] == 0
            assert runtime.telemetry.counts['RECONCILE_SUPERSEDED'] == 1
            # Replayed notification after reconnect invalidates old observations.
            worker.order_event('epoch2', update)
            assert not worker.fresh
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            runtime.ledger.close()
    asyncio.run(run())


def test_failed_cash_still_reconciles_positions_and_stale_revision_blocks_entry(tmp_path):
    async def run():
        class Broker(FakeBroker):
            fail_cash = True
            async def funds(self):
                if self.fail_cash:
                    clock[0] += 6  # Slow cash failure must not age newer position facts.
                    raise TimeoutError()
                return await super().funds()
        broker = Broker()
        broker._positions = [{'securityId': '100', 'netQty': 65}]
        runtime = runtime_at(tmp_path/'ledger', broker)
        clock = [100.0]
        worker = AccountRefresh(runtime, asyncio.Event(), busy=lambda: True, clock=lambda: clock[0])
        await worker.refresh()
        assert worker.fresh and runtime.reconciled['positions'][0]['netQty'] == 65
        assert not runtime.status.current_account_funded
        assert not runtime.permit_entry()
        broker.fail_cash = False
        runtime.status.broker_route_verified = runtime.status.official_cas_signal_seen = True
        await worker.refresh()
        assert runtime.permit_entry()
        # A cash preflight cannot authorize an entry from old position evidence.
        clock[0] += 5.01
        assert not runtime.permit_entry()
        assert worker.requested.is_set()
        await worker.refresh()
        worker.invalidate()
        assert not runtime.permit_entry()
        runtime.ledger.close()
    asyncio.run(run())


def test_funds_read_spanning_order_change_cannot_publish_account(tmp_path):
    async def run():
        entered, release = asyncio.Event(), asyncio.Event()
        class Broker(FakeBroker):
            async def funds(self):
                funds = await super().funds()
                entered.set()
                await release.wait()
                return funds
        runtime = runtime_at(tmp_path/'ledger', Broker())
        published = []
        worker = AccountRefresh(runtime, asyncio.Event(), busy=lambda: False, publish=lambda *args: published.append(args))
        task = asyncio.create_task(worker.refresh())
        await entered.wait()
        worker.order_event('epoch', {'OrderNo': 'X', 'Status': 'CANCELLED'})
        release.set()
        with pytest.raises(ReconciliationChanged):
            await task
        assert not published and not worker.fresh
        runtime.ledger.close()
    asyncio.run(run())


def test_cancelled_worker_releases_locks(tmp_path):
    async def run():
        entered = asyncio.Event()
        class Broker(FakeBroker):
            async def orders(self):
                entered.set()
                await asyncio.Event().wait()
        runtime = runtime_at(tmp_path/'ledger', Broker())
        worker = AccountRefresh(runtime, asyncio.Event(), busy=lambda: True)
        task = asyncio.create_task(worker.run())
        await entered.wait()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        assert not runtime.ledger.order_lock.locked()
        assert not runtime.ledger.reconcile_lock.locked()
        runtime.ledger.close()
    asyncio.run(run())


def test_telemetry_is_bounded_and_has_no_identifiers_or_duplicate_first_fills():
    clock = [0.0]
    telemetry = Telemetry(clock=lambda: clock[0], size=4)
    telemetry.decision()
    telemetry.submitted('private-account-order-id')
    clock[0] = .025
    telemetry.filled('private-account-order-id')
    telemetry.filled('private-account-order-id')
    for i in range(100):
        telemetry.sample('http_ack_ms', i)
        telemetry.sample('token=secret', i)
        telemetry.reason('secret')
        telemetry.submitted('private-'+str(i))
    snapshot = telemetry.snapshot()
    assert snapshot['latency']['first_fill_recorded_ms'] == {'samples': 1, 'p50': 25.0, 'p95': 25.0, 'p99': 25.0}
    assert snapshot['latency']['http_ack_ms']['samples'] == 4
    assert len(telemetry.orders) == 4
    assert 'private' not in json.dumps(snapshot) and 'secret' not in json.dumps(snapshot)
