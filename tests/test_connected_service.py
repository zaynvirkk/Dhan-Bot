"""Actual production service, HTTP broker, official protobuf and binary sockets."""
import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import struct
import threading

from websockets.asyncio.server import serve

from dhan_cas_bot import service
from dhan_cas_bot.domain import json_safe
from dhan_cas_bot.ledger import Ledger
from dhan_cas_bot.proto import FeedResponse
from tests.test_production_lifecycles import MatchingBroker
from tests.acceptance.cas.support import mandate


def full_packet(security, bid=9, ask=10):
    payload = bytearray(163)
    struct.pack_into("<BhBI",payload,0,8,163,2,security)
    struct.pack_into("<f",payload,8,ask)
    struct.pack_into("<i",payload,14,1)
    struct.pack_into("<IIhhff",payload,63,195,195,1,1,bid,ask)
    return bytes(payload)


def test_connected_service_qualifies_route_freezes_reference_buys_and_exits(tmp_path, monkeypatch):
    async def run():
        clock = [datetime(2026,9,15,9,35,tzinfo=timezone.utc)]
        ledger = Ledger(tmp_path / "ledger.sqlite3")
        broker = MatchingBroker(ledger)
        stop = asyncio.Event()
        sockets = {}
        loop = asyncio.get_running_loop()
        async def websocket(socket, name):
            sockets[name] = socket
            await socket.recv()
            await stop.wait()
        async def upstox(socket): await websocket(socket,"upstox")
        async def market(socket): await websocket(socket,"market")
        async def order(socket): await websocket(socket,"order")
        async with serve(upstox,"127.0.0.1",0) as us, serve(market,"127.0.0.1",0) as ms, serve(order,"127.0.0.1",0) as os:
            endpoints = {name:f"ws://127.0.0.1:{server.sockets[0].getsockname()[1]}" for name,server in (("upstox",us),("market",ms),("order",os))}
            class Handler(BaseHTTPRequestHandler):
                def log_message(self,*args): pass
                def reply(self,value,content_type="application/json"):
                    raw = value.encode() if isinstance(value,str) else json.dumps(json_safe(value)).encode()
                    self.send_response(200); self.send_header("Content-Type",content_type); self.send_header("Content-Length",str(len(raw))); self.end_headers(); self.wfile.write(raw)
                def do_GET(self):
                    if self.path == "/authorize": return self.reply({"data":{"authorized_redirect_uri":endpoints["upstox"]}})
                    if self.path == "/master": return self.reply("SEGMENT,SECURITY_ID,INSTRUMENT,UNDERLYING_SYMBOL,SM_EXPIRY_DATE,OPTION_TYPE,STRIKE_PRICE,LOT_SIZE,TICK_SIZE,SM_FREEZE_QTY\nNSE_FNO,100,OPTIDX,NIFTY,2026-09-15,CE,25000,65,0.05,1800\nNSE_FNO,200,OPTIDX,NIFTY,2026-09-15,PE,25000,65,0.05,1800\n","text/csv")
                    if self.path == "/freeze": return self.reply("SYMBOL,VOL_FRZ_QTY\nNIFTY,1800\n","text/csv")
                    if self.path == "/v2/orders": return self.reply(broker.order_rows)
                    if self.path == "/v2/trades": return self.reply(broker.trade_rows)
                    if self.path == "/v2/positions": return self.reply(asyncio.run(broker.positions()))
                    if self.path == "/v2/fundlimit": return self.reply({"dhanClientId":"TEST","availabelBalance":str(broker.cash),"withdrawableBalance":str(broker.cash)})
                    if self.path == "/v2/ip/getIP": return self.reply({"primaryIP":"127.0.0.1"})
                    self.send_error(404)
                def do_POST(self):
                    assert self.path == "/v2/orders"
                    request = json.loads(self.rfile.read(int(self.headers["Content-Length"])),parse_float=str)
                    if request["correlationId"].startswith("p"):
                        broker.next_fill = 0
                    result = asyncio.run(broker.submit_order(request))
                    # The WS echo deliberately arrives before the HTTP response.
                    event = {"Data":{"ClientId":"TEST","OrderNo":result["orderId"],"CorrelationId":request["correlationId"],"Status":result["orderStatus"]}}
                    asyncio.run_coroutine_threadsafe(sockets["order"].send(json.dumps(event)),loop).result(timeout=3)
                    self.reply(result)
            http = ThreadingHTTPServer(("127.0.0.1",0),Handler)
            thread = threading.Thread(target=http.serve_forever,daemon=True); thread.start()
            base = f"http://127.0.0.1:{http.server_port}"
            config={"state_dir":str(tmp_path),"account_id":"TEST","live_order_authority":True,"expected_egress_ip":"127.0.0.1","dhan_api_base":base+"/v2","dhan_master_url":base+"/master","nse_freeze_url":base+"/freeze","upstox_authorize_url":base+"/authorize","dhan_market_ws_url":endpoints["market"],"dhan_order_ws_url":endpoints["order"]}
            m=mandate(live=True)
            fields=("account_id","allocated_capital","cumulative_entry_debit_cap","debit_cap_scope","reinvest_realized_profit","probe_max_attempts_per_session","probe_entry_debit_cap_per_session","probe_spending_cap_per_mandate","live_order_authority")
            (tmp_path/"mandate.json").write_text(json.dumps(json_safe({key:getattr(m,key) for key in fields})))
            monkeypatch.setenv("DHAN_ACCESS_TOKEN","fixture-token")
            monkeypatch.setenv("UPSTOX_ANALYTICS_TOKEN","fixture-upstox")
            monkeypatch.delenv("DHAN_BROKER_READ_ONLY",raising=False)
            monkeypatch.setattr(service,"current_verification",lambda *args:True)
            async def zero(*args): return 0
            monkeypatch.setattr(service,"clock_uncertainty",zero)
            monkeypatch.setattr(service,"require_expected_egress",zero)
            task=asyncio.create_task(service.serve_session(config,ledger,stop,now_fn=lambda:clock[0]))
            async def until(predicate):
                deadline=loop.time()+8
                while not predicate():
                    if task.done(): task.result()
                    assert loop.time()<deadline, f"service did not progress; requests={broker.requests}; status={(tmp_path/'status.json').read_text() if (tmp_path/'status.json').exists() else 'none'}"
                    await asyncio.sleep(.03)
            async def index(value,iep=False):
                frame=FeedResponse(); frame.type=1; frame.currentTs=int(clock[0].timestamp()*1000)
                ltpc=frame.feeds["NSE_INDEX|Nifty 50"].fullFeed.indexFF.ltpc
                ltpc.ltp=value
                if iep: ltpc.iep.value=value
                await sockets["upstox"].send(frame.SerializeToString())
                await asyncio.sleep(.03)
            async def status(name):
                frame=FeedResponse(); frame.type=2; frame.currentTs=int(clock[0].timestamp()*1000)
                event=frame.marketInfo.casMarketStatus["NSE_EQ"]; event.status=name; event.updatedTime=frame.currentTs
                await sockets["upstox"].send(frame.SerializeToString())
                await asyncio.sleep(.05)
            try:
                await until(lambda:len(sockets)==3)
                await sockets["market"].send(full_packet(100)+full_packet(200))
                await until(lambda:len(broker.requests)==1)
                assert broker.requests[0]["correlationId"].startswith("p") and broker.requests[0]["price"]=="0.05"
                await until(lambda:(tmp_path/"status.json").exists() and json.loads((tmp_path/"status.json").read_text())["broker_route_verified"])
                for second in range(54,59):
                    clock[0]=datetime(2026,9,15,9,44,second,tzinfo=timezone.utc)
                    await index(25000)
                clock[0]=datetime(2026,9,15,9,45,tzinfo=timezone.utc); await status("CTS_CLOSE")
                await until(lambda:ledger.db.execute("SELECT COUNT(*) FROM references_frozen").fetchone()[0]==1)
                clock[0]=datetime(2026,9,15,9,50,tzinfo=timezone.utc); await status("CAS_LM_START")
                clock[0]+=timedelta(seconds=1); await index(25100,True)
                clock[0]+=timedelta(seconds=1); await index(25100,True)
                await until(lambda:len(broker.requests)==2)
                assert broker.requests[1]["transactionType"]=="BUY"
                await sockets["market"].send(full_packet(100,bid=50))
                clock[0]+=timedelta(seconds=1); await index(24900,True)
                await until(lambda:len(broker.requests)==3)
                assert broker.requests[2]["transactionType"]=="SELL"
                assert Decimal(broker.requests[2]["price"])==Decimal("49.90")
                await until(lambda:ledger.db.execute("SELECT COUNT(*) FROM lifecycles WHERE state='CLOSED'").fetchone()[0]==1)
                assert not any(broker.quantities.values())
            finally:
                stop.set()
                await asyncio.wait_for(task,5)
                http.shutdown(); http.server_close(); thread.join(timeout=2)
                ledger.close()
    asyncio.run(run())
