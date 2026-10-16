"""Production recovery counterexamples; local brokers and sockets only."""
import asyncio

from dhan_cas_bot.transport import WebSocketRunner
from tests.test_health_runtime import Tape
from tests.test_directional_engine import setup
from tests.test_streaming_runtime import runtime_at
from tests.conftest import FakeBroker


def test_dhan_market_uses_provider_heartbeat_and_still_answers_pings():
    from websockets.asyncio.server import serve
    from dhan_cas_bot.feeds import DhanMarketClient
    async def run():
        pongs=[];seen=[]
        async def provider(socket):
            pong=await socket.ping(b'provider-heartbeat')
            await asyncio.wait_for(pong,1)
            pongs.append(True)
            await socket.send(b'quote')
            await socket.wait_closed()
        async with serve(provider,'127.0.0.1',0) as listener:
            async def quote(payload):seen.append(payload);runner.close()
            client=DhanMarketClient('fixture-token')
            runner=WebSocketRunner(f'ws://127.0.0.1:{listener.sockets[0].getsockname()[1]}',{},quote,
                                   **client.transport_options)
            assert runner.server_heartbeat is True
            await asyncio.wait_for(runner.run(),3)
        assert seen==[b'quote'] and pongs==[True]
        assert WebSocketRunner('fixture',{},quote).server_heartbeat is False
    asyncio.run(run())


def test_busy_decoder_yields_before_a_full_queue_can_starve_other_tasks():
    async def run():
        started=asyncio.Event();seen=[];heartbeat=[]
        async def decode(payload):
            seen.append(payload)
            started.set()
        async def monitor():
            await started.wait()
            heartbeat.append(len(seen))
        runner=WebSocketRunner('fixture',{},decode)
        waiter=asyncio.create_task(monitor())
        await runner.consume(Tape([b'frame']*200))
        await waiter
        assert 0<heartbeat[0]<=16
        assert len(seen)==200
    asyncio.run(run())


def test_dhan_still_has_a_bounded_watchdog_for_a_silent_dead_connection(monkeypatch):
    import websockets.asyncio.client
    async def run():
        options={}
        class Socket(Tape):
            async def __aenter__(self):return self
            async def __aexit__(self,*args):pass
        def connect(*args,**kwargs):
            options.update(kwargs)
            return Socket([b'quote'])
        monkeypatch.setattr(websockets.asyncio.client,'connect',connect)
        async def receive(payload):runner.stop.set()
        runner=WebSocketRunner('fixture',{},receive,server_heartbeat=True)
        await runner.run()
        assert 0<options['ping_interval']<=30
        assert 5<options['ping_timeout']<=40
    asyncio.run(run())


def test_account_batch_starts_positions_without_waiting_for_slow_orders(tmp_path):
    async def run():
        release=asyncio.Event();positions=asyncio.Event();trades=asyncio.Event()
        class Broker(FakeBroker):
            async def orders(self):
                await release.wait()
                return []
            async def positions(self):
                positions.set()
                return []
            async def trades(self):
                trades.set()
                return []
        runtime=runtime_at(tmp_path/'ledger',Broker())
        task=asyncio.create_task(runtime.orders.reconcile())
        try:
            for _ in range(6):await asyncio.sleep(0)
            assert positions.is_set() and trades.is_set()
            assert not task.done()
            release.set()
            result=await task
            assert not result['unresolved']
        finally:
            release.set();task.cancel()
            await asyncio.gather(task,return_exceptions=True)
            runtime.ledger.close()
    asyncio.run(run())


def test_cancelled_unfilled_entry_cannot_keep_a_submitted_status(tmp_path):
    async def run():
        engine,broker,ledger,_,_=setup(tmp_path)
        try:
            broker.next_fill=0
            assert await engine.cycle()
            assert engine.runtime.status.reason.endswith('ENTRY_SUBMITTED')
            assert not await engine.cycle()
            assert engine.active is None
            assert engine.runtime.status.reason.endswith('ENTRY_CANCELLED_NO_FILL')
            assert ledger.db.execute('SELECT COUNT(*) FROM fills').fetchone()[0]==0
        finally:ledger.close()
    asyncio.run(run())


def test_reconcile_cancellation_joins_all_inflight_reads(tmp_path):
    async def run():
        entered=[];finished=[];release=asyncio.Event()
        class Broker(FakeBroker):
            async def read(self,name):
                entered.append(name)
                try:await release.wait()
                finally:finished.append(name)
                return []
            async def orders(self):return await self.read('orders')
            async def trades(self):return await self.read('trades')
            async def positions(self):return await self.read('positions')
        runtime=runtime_at(tmp_path/'ledger',Broker())
        task=asyncio.create_task(runtime.orders.reconcile())
        try:
            for _ in range(6):await asyncio.sleep(0)
            assert set(entered)=={'orders','trades','positions'}
            task.cancel()
            await asyncio.gather(task,return_exceptions=True)
            assert set(finished)==set(entered)
            assert not runtime.ledger.reconcile_lock.locked()
            assert runtime.ledger.account_revision==0
        finally:
            release.set();task.cancel()
            await asyncio.gather(task,return_exceptions=True)
            runtime.ledger.close()
    asyncio.run(run())


def test_stale_account_status_explains_current_block_instead_of_old_order(tmp_path):
    from types import SimpleNamespace
    async def run():
        engine,broker,ledger,_,_=setup(tmp_path)
        try:
            engine.runtime.status.reason='SECONDS_FUTURES_CATCHUP:ENTRY_SUBMITTED'
            engine.runtime.account_refresh=SimpleNamespace(fresh=False,request=lambda:None)
            assert not await engine.cycle(reconcile=False)
            assert engine.runtime.status.reason=='ACCOUNT_REFRESH_REQUIRED'
            assert broker.requests==[]
        finally:ledger.close()
    asyncio.run(run())
