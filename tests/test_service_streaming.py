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


@pytest.mark.parametrize('mode', ['normal', 'cash_failure', 'partial', 'slow_account', 'day_rotation', 'token_rotation', 'shared_token_rotation', 'message_burst', 'transport_reconnect', 'invalid_frames', 'native_status', 'native_missing_status', 'native_rejected_status', 'native_unknown_status', 'native_foreign_account', 'route_reconnect', 'exhausted_route_reconnect', 'probe_rejection_retry', 'probe_rejections_exhausted', 'probe_rejection_reconnect', 'observation_only_nonexpiry', 'observation_only_expiry', 'observation_only_expiry_closed', 'funded_directional_nonexpiry'])
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
            if mode.startswith('probe_rejection') and (len(broker.requests)==1 or mode=='probe_rejections_exhausted'):
                row['orderStatus']='REJECTED'
            event = {'Data': {'ClientId':'TEST', 'OrderNo':row['orderId'],
                'CorrelationId':row['correlationId'], 'Status':row['orderStatus'], 'TradedQty':row['filledQty']}}
            if mode.startswith('native_'):
                # Actual Dhan order_alert observed on 12 October: lower-camel
                # field names and title-case status, unlike its doc example.
                event = {'Type':'order_alert', 'Data': {
                    'clientId':'TEST', 'orderNo':row['orderId'],
                    'correlationId':row['correlationId'], 'status':row['orderStatus'].title()}}
                if mode == 'native_missing_status': event['Data'].pop('status')
                if mode == 'native_rejected_status': event['Data']['status']='Rejected'
                if mode == 'native_unknown_status': event['Data']['status']='Unrecognized'
                if mode == 'native_foreign_account': event['Data']['clientId']='FOREIGN'
            # Notification arrives before submit_order() returns its HTTP ACK.
            await channels['orders'].send(json.dumps(event).encode())
            await channels['orders'].send(json.dumps(event).encode())
            if mode=='probe_rejection_reconnect' and len(broker.requests)==1:
                # The old HTTP reply arrives after a new order socket connects.
                # Its rejection must not permanently poison that new epoch.
                old=channels['orders']
                await old.disconnect()
                await until(lambda:channels['orders'] is not old)
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
                expiry='2026-09-16' if mode.endswith('nonexpiry') else '2026-09-15'
                return httpx.Response(200, text=f'SEGMENT,SECURITY_ID,INSTRUMENT,UNDERLYING_SYMBOL,SM_EXPIRY_DATE,OPTION_TYPE,STRIKE_PRICE,LOT_SIZE,TICK_SIZE,SM_FREEZE_QTY\nNSE_FNO,100,OPTIDX,NIFTY,{expiry},CE,25000,65,0.05,1800\nNSE_FNO,200,OPTIDX,NIFTY,{expiry},PE,25000,65,0.05,1800\n')
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
        if mode in {'message_burst', 'transport_reconnect', 'invalid_frames', 'route_reconnect', 'exhausted_route_reconnect','probe_rejection_reconnect'}:
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
        if mode in {'route_reconnect','probe_rejection_retry','probe_rejections_exhausted','probe_rejection_reconnect'}:
            from dataclasses import replace
            m=replace(m,probe_max_attempts_per_session=2)
        fields=('account_id','allocated_capital','cumulative_entry_debit_cap','debit_cap_scope','reinvest_realized_profit','probe_max_attempts_per_session','probe_entry_debit_cap_per_session','probe_spending_cap_per_mandate','live_order_authority')
        (tmp_path/'mandate.json').write_text(json.dumps(json_safe({key:getattr(m,key) for key in fields})))
        config = {'state_dir':str(tmp_path),'account_id':'TEST','live_order_authority':True,'expected_egress_ip':'127.0.0.1',
                  'dhan_api_base':'https://fixture/v2','dhan_master_url':'https://fixture/master','nse_freeze_url':'https://fixture/freeze',
                  'upstox_authorize_url':'https://fixture/authorize','dhan_market_ws_url':'market','dhan_order_ws_url':'orders'}
        if mode.startswith(('observation_only_', 'funded_directional_')):
            from .test_session_strategies import calendar
            from dhan_cas_bot.strategy_inputs import StrategyInputWorker
            config['strategies']=['CAS_LAG_V1','OPEN_DRIVE_FAST']
            config['funded_strategies']=['OPEN_DRIVE_FAST'] if mode.startswith('funded_directional_') else ['CAS_LAG_V1']
            # Exchange is open, with live books. Scanning an unfunded ordinary
            # strategy must never qualify a money route on a non-expiry day,
            # or bring CAS qualification forward before its own window.
            clock[0]=clock[0].replace(hour=5,minute=0)  # 10:30 IST
            if mode.endswith('expiry_closed'):clock[0]=clock[0].replace(hour=2)  # 07:30 IST
            async def calendar_only(worker):
                worker.calendar=calendar('2026-09-15','2026-09-16')
                await stop.wait()
            monkeypatch.setattr(StrategyInputWorker,'run',calendar_only)
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
            # Route-positive books now explicitly carry observed liquidity;
            # zero/missing OI is covered by separate no-order regressions.
            await channels['market'].send(full_packet(100,ask=9.05,oi=650000,volume=65000)+full_packet(200,ask=9.05,oi=650000,volume=65000))
            if mode.startswith(('observation_only_', 'funded_directional_')):
                await until(lambda:status_file().get('books_observed')==2)
                if mode.startswith('observation_only_'):
                    assert broker.requests==[]
                    assert not status_file()['broker_route_verified']
                    assert status_file()['route_attempts_used']==0
                    if mode.endswith('nonexpiry'):
                        assert status_file()['state']=='NO_TRADE_DAY'
                    if mode.endswith('expiry_closed'):
                        assert status_file()['state']=='WAITING_EXCHANGE_SESSION'
                else:
                    await until(lambda:status_file().get('broker_route_verified'))
                    assert len(broker.requests)==1
                assert status_file()['strategies']==config['strategies']
                assert status_file()['funded_strategies']==config['funded_strategies']
                # Funded CAS may be ineligible, while live observation scans
                # still need visible freshness checks throughout the session.
                assert status_file()['monitoring_mode']==('IDLE' if mode.endswith('expiry_closed') else 'ACTIVE')
                return
            if mode.startswith('probe_rejection'):
                await until(lambda:len(broker.requests)==2 and not ledger.pending_intents())
                assert ledger.counter('probe.attempts:2026-09-15')==2
                assert broker.requests[0]['securityId']!=broker.requests[1]['securityId']
                assert not any(broker.quantities.values())
                if mode!='probe_rejections_exhausted':
                    await until(lambda:status_file().get('broker_route_verified'))
                else:
                    await asyncio.sleep(.5)
                    assert not status_file().get('broker_route_verified')
                assert len(broker.requests)==2
                return
            if mode in {'native_missing_status', 'native_rejected_status', 'native_unknown_status', 'native_foreign_account'}:
                await until(lambda:len(broker.requests)==1 and not ledger.pending_intents())
                await asyncio.sleep(.15)
                assert not status_file().get('broker_route_verified')
                assert len(broker.requests)==1
                assert not any(broker.quantities.values())
                return
            await until(lambda: status_file().get('broker_route_verified'))
            assert len(broker.requests)==1
            if mode in {'route_reconnect','exhausted_route_reconnect'}:
                old=channels['orders']
                await old.disconnect()
                await until(lambda:channels['orders'] is not old)
                if mode=='route_reconnect':
                    await until(lambda:len(broker.requests)==2 and status_file().get('route_attempts_used')==2 and status_file().get('broker_route_verified') and not ledger.pending_intents())
                    assert ledger.counter('probe.attempts:2026-09-15')==2
                else:
                    await until(lambda:not status_file().get('broker_route_verified') and len(broker.requests)==1)
                    await asyncio.sleep(.2)
                    assert len(broker.requests)==1
                    assert ledger.counter('probe.attempts:2026-09-15')==1
                assert not ledger.pending_intents()
                assert not any(broker.quantities.values())
                return
            assert 'observation' in status_file()
            assert status_file()['observation']['iep'] is None
            assert len(status_file()['observation']['watchlist']) == 2
            if mode=='invalid_frames':
                import struct
                initial=channels['market']
                malformed=bytearray(full_packet(200))
                struct.pack_into('<H',malformed,1,70)  # Live-observed 162-byte frame declaring 70.
                await initial.send(full_packet(100)+bytes(malformed))
                await until(lambda:status_file().get('books_observed')==0)
                assert status_file()['feed_health']['market']['last_usable_at'] is None
                assert len(broker.requests)==1
                # Identical valid packets must be accepted again after invalidation.
                await initial.send(full_packet(100)+full_packet(200))
                await until(lambda:status_file().get('books_observed')==2)
                malformed=bytearray(full_packet(200))
                struct.pack_into('<f',malformed,50,float('nan'))
                await initial.send(bytes(malformed))
                await until(lambda:status_file().get('books_observed')==1)
                assert len(broker.requests)==1
                await initial.send(full_packet(200))
                await until(lambda:status_file().get('books_observed')==2)
                assert channels['market'] is initial
                health=status_file()['feed_health']['market']
                assert health['connected'] is True and health['reconnects']==0
                counts=status_file()['telemetry']['decision_counts']
                assert counts['MARKET_FRAME_REJECTED']==1 and counts['MARKET_BOOK_REJECTED']==1
                empty=bytearray(full_packet(200))
                struct.pack_into('<H',empty,1,70);empty[62:]=bytes(100)
                await initial.send(bytes(empty))
                await until(lambda:status_file().get('books_observed')==1)
                assert channels['market'] is initial and len(broker.requests)==1
                counts=status_file()['telemetry']['decision_counts']
                assert counts['MARKET_FRAME_REJECTED']==1 and counts['MARKET_BOOK_REJECTED']==2
                await initial.send(full_packet(200))
                await until(lambda:status_file().get('books_observed')==2)

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
                    # A read-only checker can renew the shared cache before
                    # the running session notices its own token's age. The
                    # fresh cache must not conceal an obsolete HTTP/socket
                    # credential while an unresolved position is retained.
                    shared = mode == 'shared_token_rotation'
                    (tmp_path/'dhan_token.json').write_text(json.dumps({
                        'issued':time.time() if shared else time.time()-21*3600,
                        'account':'TEST','token':'synthetic-next' if shared else 'synthetic-token'}))
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
            if mode in {'message_burst','transport_reconnect','invalid_frames'}:
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
