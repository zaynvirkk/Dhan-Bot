import asyncio
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
import json

import pytest

from dhan_cas_bot.cli import main
from dhan_cas_bot.domain import CasPhase, CasStatus, ContractError
from dhan_cas_bot.engine import SessionEngine
from dhan_cas_bot.final_source import NseFinalSource
from dhan_cas_bot.ledger import Ledger
from dhan_cas_bot.route import RouteQualifier
from dhan_cas_bot.settlement import FinalValue
from tests.test_production_lifecycles import setup, book, obs, NOW, DAY
from tests.test_connected_service import full_packet
from dhan_cas_bot.dhan_feed import decode_full_binary, book_from_packet


def final(value="25100"):
    return FinalValue(str(DAY),D(value),"NSE","closing_index_value",NOW.replace(hour=10,minute=5).isoformat(),NOW.replace(hour=10,minute=6).isoformat(),"revision-1","NSE_CAS_2026","FINAL")


def stop_cas(engine, clock):
    clock[0] = NOW.replace(hour=10,minute=7)
    engine.on_status(CasStatus(CasPhase.CAS_STOP,int(NOW.replace(hour=10,minute=0).timestamp()*1000),DAY,"u1"))


def test_official_final_requires_correct_date_publication_and_unique_index():
    payload = b"Index Name,Index Date,Closing Index Value\nNIFTY 50,15-09-2026,25100.25\n"
    published = NOW.replace(hour=10,minute=5)
    result=NseFinalSource.parse(payload,DAY,published_at=published,received_at=published+timedelta(seconds=1))
    result.validate()
    assert result.value == D("25100.25") and result.source == "NSE"
    for bad in (payload.replace(b"15-09",b"14-09"),payload+b"NIFTY 50,15-09-2026,25100.25\n",payload.replace(b"25100.25",b"NaN")):
        with pytest.raises(ContractError): NseFinalSource.parse(bad,DAY,published_at=published,received_at=published)
    with pytest.raises(ContractError): NseFinalSource.parse(payload,DAY,published_at=NOW,received_at=published)


def test_final_residual_entry_uses_official_value_without_manufacturing_iep(tmp_path):
    async def run():
        engine,broker,ledger,clock=setup(tmp_path)
        stop_cas(engine,clock)
        engine.reference = None
        engine.on_final(final())
        engine.on_book(book("CE",1))
        assert await engine.cycle()
        assert len(broker.requests)==1 and broker.requests[0]["transactionType"]=="BUY"
        assert not engine.observations and not engine.streaks
        decision=json.loads(ledger.db.execute("SELECT payload FROM observations WHERE kind='ENTRY_DECISION'").fetchone()[0])
        assert decision["reference"] is None and decision["final"]["source"]=="NSE"
    asyncio.run(run())


def test_final_entry_cutoff_precedes_time_exit_and_revision_disarms_durably(tmp_path):
    async def run():
        engine,broker,ledger,clock=setup(tmp_path)
        stop_cas(engine,clock)
        engine.on_final(final())
        engine.on_book(book("CE",1))
        clock[0]=NOW.replace(hour=10,minute=8,second=30)
        assert not await engine.cycle() and not broker.requests
        engine.on_final(final("25050"))
        assert ledger.metadata("disarmed") is True
        assert engine.exit_reason=="FINAL_VALUE_REVISED"
    asyncio.run(run())


def test_exercise_cash_remains_pending_until_exact_broker_receipt(tmp_path):
    async def run():
        engine,broker,ledger,clock=setup(tmp_path)
        engine.on_book(book("CE",1))
        await engine.on_iep(obs("25100",1)); await engine.on_iep(obs("25100",2))
        stop_cas(engine,clock); engine.on_final(final())
        assert not await engine.cycle()
        assert engine.runtime.status.state=="SETTLEMENT_PENDING" and len(broker.requests)==1
        lid=engine.active["lifecycle_id"]
        quantity=ledger.lifecycle_totals(lid)["quantity"]
        clock[0]=NOW+timedelta(days=1)
        broker.quantities={}
        rows=[]
        async def statement(*args): return rows
        broker.ledger_report=statement
        assert not await engine.cycle()
        assert engine.active and not ledger.db.execute("SELECT * FROM cash_postings").fetchall()
        rows.append({"dhanClientId":"TEST","narration":f"NIFTY EXERCISE 100 {DAY}","exchange":"NSE-FO","vouchernumber":"settle-1","credit":str(quantity*100-D("100")),"debit":"0"})
        assert not await engine.cycle()  # Unexplained excess fees do not match.
        assert engine.active
        rows[0]["credit"]=str(quantity*100-D("40"))
        broker.cash += quantity*100-D("40")
        assert not await engine.cycle()
        assert engine.active is None
        assert ledger.lifecycle_totals(lid)["quantity"]==0
        assert len(ledger.db.execute("SELECT * FROM settlements").fetchall())==1
        await engine.cycle()
        assert len(ledger.db.execute("SELECT * FROM settlements").fetchall())==1
    asyncio.run(run())


def test_restart_after_expiry_restores_final_without_upstox_signal(tmp_path):
    async def run():
        engine,broker,ledger,clock=setup(tmp_path)
        engine.on_book(book("CE",1))
        await engine.on_iep(obs("25100",1)); await engine.on_iep(obs("25100",2))
        stop_cas(engine,clock); engine.on_final(final())
        await engine.cycle()
        clock[0]=NOW+timedelta(days=1)
        broker.quantities={}
        recovered=SessionEngine(engine.runtime,{},now_fn=lambda:clock[0])
        assert recovered.final_value.value==D("25100")
        assert not await recovered.cycle()
        assert recovered.runtime.status.state=="SETTLEMENT_PENDING"
        assert len(broker.requests)==1
    asyncio.run(run())


def test_stale_flat_snapshot_cannot_close_a_just_sent_intent(tmp_path):
    async def run():
        engine,broker,ledger,_=setup(tmp_path)
        engine.on_book(book("CE",1))
        await engine.on_iep(obs("25100",1)); await engine.on_iep(obs("25100",2))
        assert engine.runtime.reconciled["positions"]==[]
        assert not await engine.cycle(reconcile=False)
        assert engine.active and len(broker.requests)==1
        assert not ledger.db.execute("SELECT * FROM cash_postings").fetchall()
    asyncio.run(run())


def test_adds_split_freeze_and_do_not_reuse_consumed_depth(tmp_path):
    async def run():
        engine,broker,ledger,_=setup(tmp_path)
        broker.cash=D("500000")
        engine.runtime.mandate=replace(engine.runtime.mandate,allocated_capital=D("500000"))
        engine.on_book(book("CE",1,quantity=6500))
        await engine.on_iep(obs("25100",1)); await engine.on_iep(obs("25100",2))
        for _ in range(6): await engine.cycle()
        assert sum(r["quantity"] for r in broker.requests)==6500
        assert all(r["quantity"]<=1800 and r["quantity"]%65==0 for r in broker.requests)
        before=len(broker.requests)
        await engine.cycle(); assert len(broker.requests)==before
        totals=ledger.lifecycle_totals(engine.active["lifecycle_id"])
        assert totals["entry_debit"]<=D("125000")
        engine.on_book(book("CE",2,quantity=195))
        assert await engine.cycle()
    asyncio.run(run())


def test_waiting_oms_lock_rechecks_disarm_before_network(tmp_path):
    async def run():
        engine,broker,ledger,_=setup(tmp_path)
        engine.on_book(book("CE",1))
        await engine.on_iep(obs("25100",1)); await engine.on_iep(obs("25100",2),dispatch=False)
        engine.runtime.reconciled=await engine.runtime.orders.reconcile()
        await ledger.order_lock.acquire()
        task=asyncio.create_task(engine.cycle(reconcile=False))
        await asyncio.sleep(.02)
        engine.runtime.disarm_new_entries()
        ledger.order_lock.release()
        with pytest.raises(ContractError,match="changed before dispatch"): await task
        assert not broker.requests and not ledger.pending_intents()
    asyncio.run(run())


def test_cli_disarm_is_durable_without_replacing_service_status(tmp_path,capsys):
    state=tmp_path/"state"; state.mkdir()
    status={"state":"POSITION_OPEN","writes":True}
    (state/"status.json").write_text(json.dumps(status))
    config=tmp_path/"production.toml"
    config.write_text(f'state_dir = "{state}"\nlive_order_authority = true\naccount_id = "TEST"\ndhan_api_base = "https://api.dhan.co/v2"\nexpected_egress_ip = "192.0.2.1"\n')
    assert main(["disarm","--config",str(config),"--new-entries"])==0
    ledger=Ledger(state/"ledger.sqlite3")
    assert ledger.metadata("disarmed") is True
    ledger.close()
    assert json.loads((state/"status.json").read_text())==status
    assert json.loads(capsys.readouterr().out)["exit_management_preserved"]


def test_zero_fill_probe_does_not_exhaust_lifetime_debit_cap(tmp_path):
    async def run():
        engine,broker,ledger,_=setup(tmp_path)
        for day in ("2026-09-15","2026-09-22"):
            probe=RouteQualifier(ledger,broker,session_id=day,max_attempts=1,debit_cap=D("100"),mandate_spend_cap=D("40"))
            broker.next_fill=0
            await probe.qualify(book("CE",1),epoch=day)
            await engine.runtime.orders.reconcile()
        assert len(broker.requests)==2 and ledger.lifecycle_totals("route-probe")["entry_debit"]==0
    asyncio.run(run())


def test_empty_untraded_option_book_replaces_liquidity_without_reconnect(tmp_path):
    import struct
    engine,broker,ledger,_=setup(tmp_path)
    previous=book("CE",1)
    engine.on_book(previous)
    raw=bytearray(full_packet(100))
    struct.pack_into("<f",raw,8,0)
    raw[63:]=bytes(100)
    decoded=decode_full_binary(bytes(raw),previous.instrument)
    engine.on_book(book_from_packet(decoded,previous.instrument,previous.epoch,previous.received_ns+1))
    assert engine.market_connected
    assert engine.books["100"].bids==engine.books["100"].asks==()


def test_final_sale_slice_does_not_require_full_position_liquidity(tmp_path):
    async def run():
        engine,broker,ledger,clock=setup(tmp_path)
        engine.on_book(book("CE",1))
        await engine.on_iep(obs("25100",1)); await engine.on_iep(obs("25100",2))
        stop_cas(engine,clock); engine.on_final(final())
        engine.on_book(book("CE",2,bid="110",ask="120",quantity=65))
        assert await engine.cycle()
        assert broker.requests[-1]["transactionType"]=="SELL" and broker.requests[-1]["quantity"]==65
        engine.on_book(book("CE",3,bid="90",ask="120",quantity=65))
        assert not await engine.cycle()
        assert ledger.lifecycle_totals(engine.active["lifecycle_id"])["quantity"]==130
        assert engine.runtime.status.state=="SETTLEMENT_PENDING"
    asyncio.run(run())


def test_reordered_iep_cannot_reverse_current_direction(tmp_path):
    async def run():
        engine,broker,ledger,_=setup(tmp_path)
        engine.on_book(book("CE",1))
        await engine.on_iep(obs("25100",20),dispatch=False)
        assert not await engine.on_iep(obs("24900",10),dispatch=False)
        assert engine.observations[-1][0]==D("25100")
        assert await engine.on_iep(obs("25100",21))
        assert len(broker.requests)==1
    asyncio.run(run())


def test_post_stop_additions_use_remaining_frozen_allowance(tmp_path):
    async def run():
        engine,broker,ledger,clock=setup(tmp_path)
        stop_cas(engine,clock); engine.on_final(final())
        engine.on_book(book("CE",1,quantity=65))
        assert await engine.cycle()
        first=engine.active
        await engine.cycle()
        assert len(broker.requests)==1
        engine.on_book(book("CE",2,quantity=65))
        assert await engine.cycle()
        assert engine.active["lifecycle_id"]==first["lifecycle_id"]
        assert engine.active["bankroll"]==first["bankroll"]
        assert len(broker.requests)==2
    asyncio.run(run())
