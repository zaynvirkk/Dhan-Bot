"""Production session with HTTP MockTransport and queued official feed frames.

These supplement the socket integration cases; they do not certify networking.
"""
import asyncio
from datetime import datetime, timedelta, timezone
import json

import httpx
import pytest

from dhan_cas_bot import service
from dhan_cas_bot.domain import json_safe
from dhan_cas_bot.ledger import Ledger
from dhan_cas_bot.proto import FeedResponse
from .test_connected_service import full_packet
from .test_production_lifecycles import MatchingBroker
from .acceptance.cas.support import mandate


@pytest.mark.parametrize('mode', ['normal', 'cash_failure', 'partial', 'slow_account', 'day_rotation', 'token_rotation', 'message_burst', 'transport_reconnect'])
def test_background_reconciliation_through_production_session(tmp_path, monkeypatch, mode):
    async def run():
        ledger = Ledger(tmp_path/'ledger.sqlite3')
        broker = MatchingBroker(ledger)
        clock = [datetime(2026, 9, 15, 9, 35, tzinfo=timezone.utc)]
        stop = asyncio.Event()
        channels = {}
        read_started, release_read = asyncio.Event(), asyncio.Event()
        failure = {'cash': False, 'orders': False, 'failed_reads': 0}
        class Feed:
            def __init__(self, url, headers, on_message, **kwargs):
                self.url, self.on_message, self.options = url, on_message, kwargs
                self.messages = asyncio.Queue()
            async def run(self):
                url = await self.url() if callable(self.url) else self.url
                channels[url] = self
                self.options['on_connect']()
                try:
                    while True:
                        await self.on_message(await self.messages.get())
                finally:
                    self.options['on_disconnect']()
            def close(self): pass
            async def send(self, payload):
                await self.messages.put(payload)
                await asyncio.sleep(.02)
        async def accepted(row):
            event = {'Data': {'ClientId':'TEST', 'OrderNo':row['orderId'],
                'CorrelationId':row['correlationId'], 'Status':row['orderStatus'], 'TradedQty':row['filledQty']}}
            # Notification arrives before submit_order() returns its HTTP ACK.
            await channels['orders'].send(json.dumps(event).encode())
            await channels['orders'].send(json.dumps(event).encode())
        broker.accepted = accepted
        async def handler(request):
            path = request.url.path
            if request.method == 'POST':
                assert path == '/v2/orders'
                order = json.loads(request.content, parse_float=str)
                if order['correlationId'].startswith('p'):
                    broker.next_fill = 0
                elif mode == 'partial' and order['transactionType'] == 'BUY':
                    broker.next_fill = 65
                return httpx.Response(200, json=await broker.submit_order(order))
            assert request.method == 'GET'
            if path == '/master':
                return httpx.Response(200, text='SEGMENT,SECURITY_ID,INSTRUMENT,UNDERLYING_SYMBOL,SM_EXPIRY_DATE,OPTION_TYPE,STRIKE_PRICE,LOT_SIZE,TICK_SIZE,SM_FREEZE_QTY\nNSE_FNO,100,OPTIDX,NIFTY,2026-09-15,CE,25000,65,0.05,1800\nNSE_FNO,200,OPTIDX,NIFTY,2026-09-15,PE,25000,65,0.05,1800\n')
            if path == '/freeze': return httpx.Response(200, text='SYMBOL,VOL_FRZ_QTY\nNIFTY,1800\n')
            if path == '/authorize': return httpx.Response(200, json={'data':{'authorized_redirect_uri':'signal'}})
            if path == '/v2/profile': return httpx.Response(200, json={'dhanClientId':'TEST','dataPlan':'Active','activeSegment':'E, D, '})
            if path == '/v2/ip/getIP': return httpx.Response(200, json={'primaryIP':'127.0.0.1'})
            if path == '/v2/fundlimit':
                return httpx.Response(503 if failure['cash'] else 200, json={'dhanClientId':'TEST','availabelBalance':str(broker.cash),'withdrawableBalance':str(broker.cash)})
            if path == '/v2/orders':
                if failure.get('slow'):
                    read_started.set()
                    await release_read.wait()
                if failure['orders']:
                    failure['failed_reads'] += 1
                    return httpx.Response(503)
                return httpx.Response(200, json=broker.order_rows)
            if path == '/v2/positions': return httpx.Response(200, json=await broker.positions())
            if path == '/v2/trades': return httpx.Response(200, json=broker.trade_rows)
            if path.startswith('/v2/trades/'): return httpx.Response(200, json=broker.trade_rows if path.endswith('/0') else [])
            raise AssertionError(path)
        real_client = httpx.AsyncClient
        monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs))
        if mode in {'message_burst', 'transport_reconnect'}:
            # Replay official binary frames through the real transport queue,
            # parser and production execution loop. Only network I/O is a fixture.
            import websockets.asyncio.client
            from dhan_cas_bot.transport import WebSocketRunner
            class Channel:
                def __init__(self, socket): self.socket=socket
                async def send(self,payload):
                    await self.socket.incoming.put(payload)
                    await asyncio.sleep(.02)
                async def burst(self,frames):
                    for frame in frames: await self.socket.incoming.put(frame)
                async def disconnect(self): await self.socket.close()
            class Socket:
                def __init__(self,url): self.url=url;self.incoming=asyncio.Queue()
                async def __aenter__(self):
                    channels[self.url]=Channel(self)
                    return self
                async def __aexit__(self,*args): pass
                async def send(self,payload): pass  # Subscription/login only.
                async def close(self): await self.incoming.put(None)
                def __aiter__(self): return self
                async def __anext__(self):
                    item=await self.incoming.get()
                    if item is None: raise StopAsyncIteration
                    return item
            class Runner(WebSocketRunner):
                async def wait_retry(self,delay): await asyncio.sleep(.01)
            monkeypatch.setattr(websockets.asyncio.client,'connect',lambda url,**kwargs:Socket(url))
            monkeypatch.setattr(service,'WebSocketRunner',Runner)
        else:
            monkeypatch.setattr(service, 'WebSocketRunner', Feed)
        # This harness exercises scheduling and adapters, not recorder thread
        # wake-ups (the restricted environment disallows socket-based wake-ups).
        async def local_io(function, *args): return function(*args)
        monkeypatch.setattr(asyncio, 'to_thread', local_io)
        monkeypatch.setattr(service, 'current_verification', lambda *args: True)
        async def zero(*args): return 0
        monkeypatch.setattr(service, 'clock_uncertainty', zero)
        monkeypatch.setattr(service, 'require_expected_egress', zero)
        monkeypatch.setenv('DHAN_ACCESS_TOKEN', 'synthetic-token')
        monkeypatch.setenv('UPSTOX_ANALYTICS_TOKEN', 'synthetic-token')
        monkeypatch.delenv('DHAN_BROKER_READ_ONLY', raising=False)
        m = mandate(live=True)
        fields=('account_id','allocated_capital','cumulative_entry_debit_cap','debit_cap_scope','reinvest_realized_profit','probe_max_attempts_per_session','probe_entry_debit_cap_per_session','probe_spending_cap_per_mandate','live_order_authority')
        (tmp_path/'mandate.json').write_text(json.dumps(json_safe({key:getattr(m,key) for key in fields})))
        config = {'state_dir':str(tmp_path),'account_id':'TEST','live_order_authority':True,'expected_egress_ip':'127.0.0.1',
                  'dhan_api_base':'https://fixture/v2','dhan_master_url':'https://fixture/master','nse_freeze_url':'https://fixture/freeze',
                  'upstox_authorize_url':'https://fixture/authorize','dhan_market_ws_url':'market','dhan_order_ws_url':'orders'}
        task = asyncio.create_task(service.serve_session(config, ledger, stop, now_fn=lambda:clock[0]))
        async def until(predicate):
            async def wait():
                while not predicate():
                    if task.done(): task.result()
                    await asyncio.sleep(.01)
            await asyncio.wait_for(wait(), 8)
        def status_file():
            return json.loads((tmp_path/'status.json').read_text()) if (tmp_path/'status.json').exists() else {}
        async def index(value, iep=False):
            frame=FeedResponse(); frame.type=1; frame.currentTs=int(clock[0].timestamp()*1000)
            ltpc=frame.feeds['NSE_INDEX|Nifty 50'].fullFeed.indexFF.ltpc
            ltpc.ltp=value
            if iep: ltpc.iep.value=value
            await channels['signal'].send(frame.SerializeToString())
        async def status(name):
            frame=FeedResponse(); frame.type=2; frame.currentTs=int(clock[0].timestamp()*1000)
            event=frame.marketInfo.casMarketStatus['NSE_EQ']; event.status=name; event.updatedTime=frame.currentTs
            await channels['signal'].send(frame.SerializeToString())
        try:
            await until(lambda:len(channels)==3)
            await channels['market'].send(full_packet(100)+full_packet(200))
            await until(lambda: status_file().get('broker_route_verified'))
            assert len(broker.requests)==1
            if mode=='transport_reconnect':
                old=channels['market']
                await old.disconnect()
                await until(lambda:channels['market'] is not old)
                await channels['market'].send(full_packet(100)+full_packet(200))
            if mode=='message_burst':
                await channels['market'].burst([full_packet(100)+full_packet(200)]*200)
            clock[0]=datetime(2026,9,15,9,44,53,tzinfo=timezone.utc)
            await index(27000)  # first snapshot is excluded from reference
            for second in range(54,59):
                clock[0]=datetime(2026,9,15,9,44,second,tzinfo=timezone.utc)
                await index(25000)
            clock[0]=datetime(2026,9,15,9,45,tzinfo=timezone.utc)
            await status('CTS_CLOSE')
            if mode=='slow_account':
                failure['slow']=True
                ledger.account_refresh()  # Refresh while prior evidence is fresh.
                await asyncio.wait_for(read_started.wait(), 2)
            clock[0]=datetime(2026,9,15,9,50,tzinfo=timezone.utc)
            await status('CAS_LM_START')
            clock[0]+=timedelta(seconds=1); await index(25100,True)
            clock[0]+=timedelta(seconds=1); await index(25100,True)
            await until(lambda:len(broker.requests)==2)
            assert broker.requests[1]['transactionType']=='BUY'
            if mode=='slow_account':
                assert read_started.is_set() and not release_read.is_set()
                # Decision + fresh cash + submit completed while routine GET
                # was still blocked. It must not hold the writer/decision loop.
                failure['slow']=False
                release_read.set()
            if mode.endswith('rotation'):
                failure['orders']=True
                ledger.put_metadata('reconcile_requested',True)
                await until(lambda:failure['failed_reads']>0)
                if mode=='day_rotation': clock[0]+=timedelta(days=1)
                else:
                    import time
                    monkeypatch.delenv('DHAN_ACCESS_TOKEN')
                    (tmp_path/'dhan_token.json').write_text(json.dumps({'issued':time.time()-21*3600,'account':'TEST','token':'synthetic'}))
                await until(task.done)
                assert any(broker.quantities.values()) and len(broker.requests)==2
                return
            if mode=='cash_failure':
                failure['cash']=True
                await until(lambda:status_file().get('current_account_funded') is False)
            await channels['market'].send(full_packet(100,bid=50))
            clock[0]+=timedelta(seconds=1);await index(24900,True)
            await until(lambda:len(broker.requests)==3)
            assert broker.requests[2]['transactionType']=='SELL'
            if mode=='partial': assert broker.requests[2]['quantity']==65
            failure['cash']=False
            await until(lambda:ledger.db.execute("SELECT COUNT(*) FROM lifecycles WHERE state='CLOSED'").fetchone()[0]==1)
            assert not any(broker.quantities.values())
            assert ledger.db.execute('SELECT COUNT(*) FROM fills').fetchone()[0]==2
            assert 'synthetic' not in (tmp_path/'account-observation.json').read_text()
            if mode in {'message_burst','transport_reconnect'}:
                await until(lambda:bool(status_file().get('feed_health',{}).get('market',{}).get('last_usable_at')))
                health=status_file()['feed_health']['market']
                assert health['connected'] is True
                if mode=='message_burst': assert health['queue_high_water']>1
                if mode=='transport_reconnect': assert health['reconnects']==1
        finally:
            stop.set()
            await asyncio.wait_for(task,5)
            ledger.close()
    asyncio.run(run())
