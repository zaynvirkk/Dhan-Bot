from datetime import date, datetime, timezone
from decimal import Decimal
import asyncio
import json
import pytest

from dhan_cas_bot.domain import Instrument, Level, OptionBook, OptionType, Segment, ContractError
from dhan_cas_bot.feeds import chunked, dhan_subscription, upstox_subscription, SocketProtocol
from dhan_cas_bot.ledger import Ledger
from dhan_cas_bot.route import RouteQualifier
from dhan_cas_bot.settlement_adapter import FinalValueAdapter


def book():
    inst = Instrument("23650", "NIFTY", Segment.NSE_FNO, date(2026, 9, 15), OptionType.PE, Decimal("23650"), 65, Decimal("0.05"), 1800)
    return OptionBook(inst, (Level(Decimal("9"), 65),), (Level(Decimal("10"), 195),), "dhan:1", 1_700_000_000_000_000_000)


def test_subscriptions_are_batched_and_epochs_clear_old_frames():
    assert [len(x["data"]["instrumentKeys"]) for x in upstox_subscription([str(i) for i in range(201)])] == [100, 100, 1]
    assert [x["InstrumentCount"] for x in dhan_subscription([str(i) for i in range(101)])] == [100, 1]
    epoch = SocketProtocol("x"); first = epoch.on_connect(); assert epoch.accept("a"); epoch.on_disconnect(); second = epoch.on_connect(); assert first != second and epoch.accept("a")


def test_route_probe_bootstraps_without_signal(db_path, fake_broker):
    ledger = Ledger(db_path)
    proof = asyncio.run(RouteQualifier(ledger, fake_broker, session_id="s", max_attempts=1, debit_cap=Decimal("1000"), mandate_spend_cap=Decimal("2000")).qualify(book(), epoch="dhan:1"))
    assert proof.account_id == "TEST"
    assert ledger.counter("probe.attempts:s") == 1


def test_final_adapter_rejects_provisional():
    payload = {"trading_date":"2026-09-15","value":"25000","source":"NSE","source_field":"official_settlement_value","published_at":"2026-09-15T10:00:00Z","received_at":"2026-09-15T10:00:01Z","revision":"1","settlement_regime":"CASH","finality_kind":"FINAL"}
    assert FinalValueAdapter().parse(payload).value == Decimal("25000")
    payload["source_field"] = "provisional_iep"
    with pytest.raises(ContractError): FinalValueAdapter().parse(payload)
