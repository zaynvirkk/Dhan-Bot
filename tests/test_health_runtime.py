import asyncio
from datetime import datetime, timedelta, timezone
import json
import time

import httpx
import pytest

from dhan_cas_bot.broker import DhanBroker
from dhan_cas_bot.domain import ContractError
from dhan_cas_bot.read_scheduler import ReadScheduler, account_reads, read_priority
from dhan_cas_bot.transport import WebSocketRunner, message_received_ns
from dhan_cas_bot.dashboard.data import runtime_view
from .test_streaming_runtime import runtime_at
from .conftest import FakeBroker


def test_execution_overtakes_queued_monitoring_with_shared_spacing():
    async def run():
        gate = ReadScheduler(.025)
        events = []
        await gate.acquire()
        async def request(name, priority):
            with read_priority(priority):
                await gate.acquire()
            events.append((name, time.monotonic()))
        background = asyncio.create_task(request('monitor',10))
        cancelled = asyncio.create_task(request('cancelled',0))
        await asyncio.sleep(0)
        cancelled.cancel()
        foreground = asyncio.create_task(request('execution',0))
        await asyncio.gather(background, foreground, cancelled, return_exceptions=True)
        assert [e[0] for e in events] == ['execution','monitor']
        assert events[1][1]-events[0][1] >= .024
        assert account_reads('TEST','https://fixture') is account_reads('TEST','https://fixture')
        assert account_reads('OTHER','https://fixture') is not account_reads('TEST','https://fixture')
    asyncio.run(run())


def test_actual_broker_clients_share_scheduler_and_do_not_retry_requests():
    async def run():
        paths=[]
        async def handler(req):
            paths.append(req.url.path)
            return httpx.Response(200,json=[])
        clients=[DhanBroker('TEST','fake','https://fixture') for _ in range(2)]
        for client in clients: client.client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            await clients[0].orders()
            with read_priority(10): background=asyncio.create_task(clients[0].orders())
            await asyncio.sleep(0)
            await clients[1].positions()
            await background
            assert paths==['/orders','/positions','/orders']
        finally:
            for client in clients: await client.close()
    asyncio.run(run())


def test_stalled_cash_does_not_delay_position_reconciliation(tmp_path):
    from dhan_cas_bot.account_refresh import AccountRefresh
    async def run():
        entered, release = asyncio.Event(), asyncio.Event()
        class Broker(FakeBroker):
            async def funds(self):
                entered.set()
                await release.wait()
                raise TimeoutError()
        broker=Broker();broker._positions=[{'securityId':'100','netQty':65}]
        runtime=runtime_at(tmp_path/'ledger',broker)
        worker=AccountRefresh(runtime,asyncio.Event(),busy=lambda:True)
        task=asyncio.create_task(worker.refresh())
        try:
            await entered.wait()
            assert worker.fresh
            assert runtime.reconciled['positions'][0]['netQty']==65
            assert not task.done()
            release.set();await task
            assert worker.fresh and not runtime.status.current_account_funded
        finally:
            task.cancel();await asyncio.gather(task,return_exceptions=True)
            runtime.ledger.close()
    asyncio.run(run())


class Tape:
    def __init__(self, frames): self.frames=iter(frames)
    def __aiter__(self): return self
    async def __anext__(self):
        try: return next(self.frames)
        except StopIteration: raise StopAsyncIteration


def test_burst_replay_preserves_every_frame_and_original_receipt_time():
    async def run():
        release=asyncio.Event(); seen=[]; receipt=[]
        clock=[0.0]
        async def consume(payload):
            if not seen: await release.wait()
            seen.append(int(payload));receipt.append(message_received_ns(0))
        runner=WebSocketRunner('fixture',{},consume)
        runner.clock=lambda:clock[0]
        runner.wall_clock=lambda:1_000_000_000+int(clock[0]*1e9)
        task=asyncio.create_task(runner.consume(Tape([str(i).encode() for i in range(200)])))
        try:
            for _ in range(5):await asyncio.sleep(0)
            clock[0]=2
            health=runner.snapshot()
            assert 0 < health['pending_messages'] <= 66
            assert health['oldest_pending_ms']==2000
            assert health['last_processed_at'] is None
            release.set();await task
            assert seen==list(range(200))
            assert receipt[0]==1_000_000_000  # Not delayed processing time.
            assert runner.snapshot()['pending_messages']==0
            assert runner.high_water<=66
        finally:
            task.cancel();await asyncio.gather(task,return_exceptions=True)
    asyncio.run(run())


def test_bad_frame_cancels_pending_consumer_and_cannot_be_reported_processed():
    async def run():
        async def parse(payload): raise ContractError('malformed fixture')
        runner=WebSocketRunner('fixture',{},parse)
        with pytest.raises(ContractError): await runner.consume(Tape([b'bad']*200))
        assert runner.processed==0 and not runner.pending_times
        assert runner.last_processed_at is None
    asyncio.run(run())


def test_flapping_sockets_back_off_until_a_stable_processed_connection(monkeypatch):
    async def run():
        import websockets.asyncio.client
        waits=[];times=[0.0]; attempts=[0]; callbacks=[]
        async def parsed(payload): pass
        runner=WebSocketRunner('fixture',{},parsed,on_connect=lambda:callbacks.append('up'),on_disconnect=lambda:callbacks.append('down'))
        runner.clock=lambda:times[0];runner.jitter=lambda low,high:high
        class Socket(Tape):
            async def __aenter__(self):return self
            async def __aexit__(self,*args):
                times[0]+=31 if attempts[0]==3 else .01
            async def send(self,payload):pass
        def connect(*args,**kwargs):
            attempts[0]+=1
            return Socket([b'frame'])
        monkeypatch.setattr(websockets.asyncio.client,'connect',connect)
        async def wait(delay):
            waits.append(delay)
            if len(waits)==4:runner.stop.set()
        runner.wait_retry=wait
        await runner.run()
        assert waits==[1,2,1,2]
        assert callbacks==['up','down']*4
        assert runner.snapshot()['connected'] is False
        assert runner.snapshot()['reconnects']==3
    asyncio.run(run())


def test_health_projection_excludes_endpoints_tokens_and_does_not_invent_unknowns():
    now=datetime.now(timezone.utc)
    result=runtime_view({'observed_at':now.isoformat(),'feed_health':{
        'market':{'connected':True,'last_usable_at':now.isoformat(),'queue_delay_ms':'NaN',
                  'pending_messages':4,'url':'SECRET','token':'SECRET'},'secret':'SECRET'}},now)
    assert result['feed_health']['market']['pending_messages']==4
    assert result['feed_health']['market']['queue_delay_ms'] is None
    assert 'signal' not in result['feed_health']
    assert 'SECRET' not in json.dumps(result)


def test_disconnect_revokes_connection_before_pending_decoding_finishes():
    async def run():
        released, entered, disconnected = asyncio.Event(),asyncio.Event(),asyncio.Event()
        async def slow(payload):
            entered.set()
            await released.wait()
        runner=WebSocketRunner('fixture',{},slow,on_disconnect=disconnected.set)
        runner.socket=object()
        task=asyncio.create_task(runner.consume(Tape([b'frame'])))
        try:
            await entered.wait()
            assert disconnected.is_set()
            assert runner.snapshot()['connected'] is False
            assert not task.done()
            released.set();await task
        finally:
            task.cancel();await asyncio.gather(task,return_exceptions=True)
    asyncio.run(run())
