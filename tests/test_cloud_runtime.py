import asyncio
from datetime import date
from io import StringIO
import json

import pytest
from websockets.asyncio.server import serve

from dhan_cas_bot.broker import DhanBroker
from dhan_cas_bot.domain import ContractError
from dhan_cas_bot.instruments import load_dhan_master
from dhan_cas_bot.rules import RuleSource
from dhan_cas_bot.transport import WebSocketRunner
from dhan_cas_bot.release import run_verification
from dhan_cas_bot.commissioning import normalize_whitelist
from dhan_cas_bot.service import parse_clock_uncertainty


def test_native_master_segment_and_decimal_quantity():
    payload = ("EXCH_ID,SEGMENT,SECURITY_ID,INSTRUMENT,UNDERLYING_SYMBOL,SM_EXPIRY_DATE,OPTION_TYPE,STRIKE_PRICE,LOT_SIZE,TICK_SIZE,SM_FREEZE_QTY\n"
               "NSE,D,123,OPTIDX,NIFTY,2026-09-15,PE,23650,65.0,5.0000,1800\n"
               "BSE,D,456,OPTIDX,NIFTY,2026-09-14,PE,23650,65.0,5.0000,1800\n")
    expiry = RuleSource.current_expiry(payload.encode(), today=date(2026, 9, 13))
    assert expiry == date(2026, 9, 15)
    result = load_dhan_master(StringIO(payload), expiry=expiry)
    assert len(result) == 1 and result[0].lot_size == 65
    assert str(result[0].tick_size) == "0.0500"


def test_gcp_chrony_tracking_with_optional_source_address():
    observed="A9FEA9FE,169.254.169.254,3,1789361487.124628006,-0.000005826,0.000006912,0.000004503,-95.593,0.000,0.003,0.000350781,0.000284748,1039.5,Normal"
    assert parse_clock_uncertainty(observed)==1
    legacy=observed.replace(",169.254.169.254", "")
    assert parse_clock_uncertainty(legacy)==1
    assert parse_clock_uncertainty(observed.replace("Normal","Not synchronised"))>100
    assert parse_clock_uncertainty(observed.replace("-0.000005826","0.200"))>100
    assert parse_clock_uncertainty(observed.replace("0.000350781","NaN"))>100
    assert parse_clock_uncertainty("invalid")>100


def test_native_nse_freeze_columns():
    assert RuleSource.parse_freeze(b"S.No.,SYMBOL    ,VOL_FRZ_QTY    \n1,NIFTY     ,1800\n") == {"NIFTY": 1800}


def test_whitelist_message_array_is_unknown_not_verified():
    value = normalize_whitelist([{"message": "No registered address", "status": "failure"}])
    assert value == {"primary_ip": None, "secondary_ip": None, "whitelist_resolved": False}
    assert normalize_whitelist({"primaryIP": "192.0.2.1"})["primary_ip"] == "192.0.2.1"


def test_real_socket_reconnect_resubscribes_binary_and_clears_epoch():
    async def exercise():
        received, epochs = [], []
        async def server(socket):
            received.append(await socket.recv())
            await socket.send(b"frame")
            await socket.close()
        async with serve(server, "127.0.0.1", 0) as listener:
            port = listener.sockets[0].getsockname()[1]
            runner = None
            async def message(payload):
                assert payload == b"frame"
                if len(received) == 2:
                    runner.close()
            runner = WebSocketRunner(f"ws://127.0.0.1:{port}", {}, message, subscribe=[{"method": "sub"}], binary=True, on_connect=lambda: epochs.append("connect"), on_disconnect=lambda: epochs.append("disconnect"))
            await asyncio.wait_for(runner.run(), 5)
        assert received == [b'{"method":"sub"}', b'{"method":"sub"}']
        assert epochs == ["connect", "disconnect", "connect", "disconnect"]
    asyncio.run(exercise())


def test_vm_readonly_boundary_blocks_even_authorized_broker(monkeypatch):
    monkeypatch.setenv("DHAN_BROKER_READ_ONLY", "1")
    broker = DhanBroker("TEST", "test-token", allow_writes=True)
    calls=[]
    async def transport(*args, **kwargs):
        calls.append(args)
        return {"orderId":"fixture"}
    monkeypatch.setattr(broker,"_request",transport)
    with pytest.raises(ContractError, match="writes are disabled"):
        asyncio.run(broker.submit_order({"dhanClientId": "TEST"}))
    assert not calls


def test_malformed_orders_cannot_reconcile_as_empty(monkeypatch):
    broker = DhanBroker("TEST", "test-token")
    async def wrong(*args):
        return {"errorCode": "DH-901"}
    monkeypatch.setattr(broker, "_request", wrong)
    with pytest.raises(ContractError, match="not a list"):
        asyncio.run(broker.orders())


def test_verification_executes_failing_source_and_removes_marker(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/test_failure.py").write_text("def test_failure():\n    assert False\n")
    state = tmp_path / "state"
    state.mkdir()
    marker = state / "software_verified.json"
    marker.write_text(json.dumps({"case_count": 60}))
    with pytest.raises(ContractError, match="verification failed"):
        run_verification(tmp_path, state)
    assert not marker.exists()
