"""Adversarial event sequences; all order transports are local fixtures."""
import asyncio
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal as D

import pytest

from dhan_cas_bot.domain import CasPhase, CasStatus, ContractError, Intent
from dhan_cas_bot.engine import SessionEngine
from dhan_cas_bot.risk import FeeSchedule, worst_case_entry_cash
from tests.test_production_lifecycles import setup, book, obs, NOW, DAY


def test_market_only_reconnect_requires_two_new_contract_observations(tmp_path):
    async def run():
        engine, broker, _, _ = setup(tmp_path)
        engine.on_book(book("CE", 1))
        await engine.on_iep(obs("25100", 1), dispatch=False)
        await engine.on_iep(obs("25100", 2), dispatch=False)
        engine.market_reconnect("d2")
        engine.on_book(replace(book("CE", 2), epoch="d2"))
        assert not await engine.cycle()
        assert not await engine.on_iep(obs("25100", 3))
        assert await engine.on_iep(obs("25100", 4))
        assert len(broker.requests) == 1
    asyncio.run(run())


def test_book_loses_then_regains_lag_without_new_index_events(tmp_path):
    async def run():
        engine, broker, _, _ = setup(tmp_path)
        engine.on_book(book("CE", 1))
        await engine.on_iep(obs("25100", 1), dispatch=False)
        await engine.on_iep(obs("25100", 2), dispatch=False)
        engine.on_book(book("CE", 2, ask="101", bid="100"))
        engine.on_book(book("CE", 3))
        assert not await engine.cycle()
        assert not await engine.on_iep(obs("25100", 3))
        assert await engine.on_iep(obs("25100", 4))
        assert len(broker.requests) == 1
    asyncio.run(run())


def test_collection_stop_during_cash_read_prevents_entry(tmp_path):
    async def run():
        engine, broker, _, _ = setup(tmp_path)
        engine.on_book(book("CE", 1))
        await engine.on_iep(obs("25100", 1), dispatch=False)
        await engine.on_iep(obs("25100", 2), dispatch=False)
        original = broker.funds
        async def delayed_funds():
            engine.on_status(CasStatus(CasPhase.CAS_STOP, int(NOW.timestamp()*1000), DAY, "u1"))
            return await original()
        broker.funds = delayed_funds
        assert not await engine.cycle()
        assert not broker.requests
    asyncio.run(run())


@pytest.mark.parametrize("kind", ["reference", "final"])
def test_corrupt_saved_signal_does_not_strand_a_broker_long(tmp_path, kind):
    async def run():
        engine, broker, ledger, clock = setup(tmp_path)
        engine.on_book(book("CE", 1))
        await engine.on_iep(obs("25100", 1))
        await engine.on_iep(obs("25100", 2))
        if kind == "reference":
            ledger.db.execute("UPDATE references_frozen SET payload='{' WHERE session_id=?", (str(DAY),))
        else:
            ledger.db.execute("INSERT INTO metadata VALUES(?,?)", ("final:"+str(DAY), '{'))
        recovered = SessionEngine(engine.runtime, {}, now_fn=lambda:clock[0])
        await recovered.runtime.recover()
        assert await recovered.cycle()
        assert [r["transactionType"] for r in broker.requests] == ["BUY", "SELL"]
        assert not recovered.runtime.permit_entry()
        assert ledger.db.execute("SELECT COUNT(*) FROM incidents WHERE kind='SAVED_SIGNAL_INVALID'").fetchone()[0] == 1
    asyncio.run(run())


def test_expiry_close_does_not_send_orders_for_still_reported_expired_position(tmp_path):
    async def run():
        engine, broker, ledger, clock = setup(tmp_path)
        engine.on_book(book("CE", 1))
        await engine.on_iep(obs("25100", 1))
        await engine.on_iep(obs("25100", 2))
        clock[0] = NOW.replace(hour=10, minute=10)
        for _ in range(3):
            assert not await engine.cycle()
        assert len(broker.requests) == 1
        assert ledger.lifecycle_totals(engine.active["lifecycle_id"])["quantity"] == 195
        assert engine.runtime.status.state == "SETTLEMENT_PENDING"
    asyncio.run(run())


def test_cash_endpoint_failure_blocks_buys_but_not_exit_management(tmp_path):
    async def run():
        engine, broker, _, _ = setup(tmp_path)
        engine.on_book(book("CE", 1))
        await engine.on_iep(obs("25100", 1))
        await engine.on_iep(obs("25100", 2))
        async def broken_funds():
            raise TimeoutError("funds endpoint unavailable")
        broker.funds = broken_funds
        await engine.runtime.refresh_account()
        assert not engine.runtime.status.current_account_funded
        assert await engine.on_iep(obs("24900", 3))
        assert [r["transactionType"] for r in broker.requests] == ["BUY", "SELL"]
    asyncio.run(run())


def test_rate_reserve_uses_lot_rounded_freeze_children(tmp_path):
    async def run():
        engine, broker, ledger, _ = setup(tmp_path)
        # 3,575 units need three <=1,755-unit exits, although ceil(q/1800)=2.
        inst = book("CE", 1).instrument
        first = Intent("first", "BUY", inst, 1755, D("1"), "first", NOW, "L")
        second = replace(first, intent_id="second", client_order_id="second", quantity=1755)
        for intent in (first, second):
            ledger.create_intent(intent, D("2000"))
        import time
        ledger.db.executemany("INSERT INTO rate_events VALUES(?,?,?)", [(str(i), time.time(), "BUY") for i in range(6)])
        last = replace(first, intent_id="last", client_order_id="last", quantity=65)
        with pytest.raises(ContractError, match="RATE_CAPACITY:1"):
            await engine.runtime.orders.submit(last, reserved_cash=D("100"))
        assert not broker.requests
    asyncio.run(run())


def test_cash_reservation_covers_published_rates_and_tax_rounding():
    # NSE/FA/73061: Rs 3,552.99/crore options premium + .01/crore IPFT.
    # Per-child charge rounding is covered even when tax rounds up a rupee.
    assert FeeSchedule().exchange_rate == D("3552.99") / D("10000000")
    assert worst_case_entry_cash(845, D("11")) == D("9323.53")
    # Independent rounded invoice: premium 17,550, brokerage 20, exchange
    # 6.24, SEBI .02, IPFT 0, GST 4.73, stamp 1 => 17,582 - .01.
    assert worst_case_entry_cash(65, D("270")) >= D("17581.99")


def test_candidate_outside_price_band_does_not_hide_valid_contract(tmp_path):
    async def run():
        engine, broker, _, _ = setup(tmp_path)
        cheap = book("CE", 1)
        invalid = replace(cheap, instrument=replace(cheap.instrument, lower_limit=D("12")))
        valid = replace(book("CE", 2, ask="11"), instrument=replace(cheap.instrument, security_id="101"))
        engine.on_book(invalid); engine.on_book(valid)
        assert not await engine.on_iep(obs("25100", 1))
        assert await engine.on_iep(obs("25100", 2))
        assert len(broker.requests) == 1 and broker.requests[0]["securityId"] == "101"
    asyncio.run(run())


def test_zero_intrinsic_expiry_does_not_invent_fee_free_cash_close(tmp_path):
    async def run():
        from tests.test_release_boundaries import stop_cas, final
        engine, broker, ledger, clock = setup(tmp_path)
        engine.on_book(book("CE", 1))
        await engine.on_iep(obs("25100", 1)); await engine.on_iep(obs("25100", 2))
        stop_cas(engine, clock)
        engine.on_final(final("24900"))
        clock[0] = NOW + timedelta(days=1)
        broker.quantities = {}
        rows = []
        async def report(*args): return rows
        broker.ledger_report = report
        assert not await engine.cycle()
        assert engine.active is not None
        assert not ledger.db.execute("SELECT * FROM cash_postings").fetchall()
        rows.append({"dhanClientId":"TEST", "narration":f"NIFTY EXPIRY SETTLEMENT 100 {DAY}", "exchange":"NSE-FO", "vouchernumber":"expiry-fee", "credit":"0", "debit":"23.60"})
        broker.cash -= D("23.60")
        assert not await engine.cycle()
        assert engine.active is None
        assert ledger.db.execute("SELECT net_credit FROM settlements").fetchone()[0] == "-23.60"
    asyncio.run(run())


def test_fill_identity_is_scoped_to_broker_order(tmp_path):
    async def run():
        engine, broker, ledger, _ = setup(tmp_path)
        engine.on_book(book("CE", 1))
        await engine.on_iep(obs("25100", 1)); await engine.on_iep(obs("25100", 2))
        await engine.on_iep(obs("24900", 3))
        # Exchange trade numbers alone are not a cross-order/day identity.
        broker.trade_rows[1]["exchangeTradeId"] = broker.trade_rows[0]["exchangeTradeId"]
        await engine.runtime.orders.reconcile()
        assert ledger.lifecycle_totals(engine.active["lifecycle_id"])["quantity"] == 0
        await engine.runtime.orders.reconcile()
        assert ledger.db.execute("SELECT COUNT(*) FROM fills").fetchone()[0] == 2
    asyncio.run(run())
