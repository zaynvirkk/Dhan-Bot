from datetime import date
from decimal import Decimal
import asyncio

from dhan_cas_bot.domain import CasPhase, CasStatus, IndexObservation
from dhan_cas_bot.engine import SessionEngine
from dhan_cas_bot.ledger import Ledger
from dhan_cas_bot.runtime import AutoLive
from .acceptance.cas.support import book, mandate


def observation(i, value):
    provider = 995000 + i * 500
    return IndexObservation(Decimal(value), provider, (provider - 50) * 1_000_000, "upstox:1", i, raw_identity=f"r{i}")


def test_engine_dispatches_eligible_dhan_order_after_gates(db_path, fake_broker):
    ledger = Ledger(db_path)
    m = mandate(live=True)
    runtime = AutoLive(ledger, fake_broker, m, software_verified=True)
    runtime.status.current_account_funded = True
    runtime.status.broker_route_verified = True
    runtime.status.official_cas_signal_seen = True
    engine = SessionEngine(runtime, {})
    engine.on_ltp(observation(0, "25000")); engine.on_ltp(observation(1, "25001")); engine.on_ltp(observation(2, "25002")); engine.on_ltp(observation(3, "25003")); engine.on_ltp(observation(4, "25004"))
    engine.on_status(CasStatus(CasPhase.CTS_CLOSE, 1_000_000, date(2026, 9, 15), "upstox:1"))
    engine.on_status(CasStatus(CasPhase.CAS_LM_START, 1_001_000, date(2026, 9, 15), "upstox:1"))
    engine.on_book(book())
    assert asyncio.run(engine.on_iep(observation(5, "24900"))) is False
    assert asyncio.run(engine.on_iep(observation(6, "24800"))) is True
    assert fake_broker.requests[0]["exchangeSegment"] == "NSE_FNO"
    assert fake_broker.requests[0]["productType"] == "MARGIN"
