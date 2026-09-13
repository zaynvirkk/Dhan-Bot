from datetime import date, datetime, timezone
from decimal import Decimal
import asyncio

from dhan_cas_bot.domain import Instrument, Intent, OptionType, Segment
from dhan_cas_bot.ledger import Ledger
from dhan_cas_bot.orders import OrderManager


def intent():
    inst = Instrument("23650", "NIFTY", Segment.NSE_FNO, date(2026, 9, 15), OptionType.PE, Decimal("23650"), 65, Decimal("0.05"), 1800)
    return Intent("i1", "BUY", inst, 65, Decimal("10"), "c1", datetime.now(timezone.utc), "l1")


def test_intent_commits_before_request_and_fill_is_idempotent(db_path, fake_broker):
    ledger = Ledger(db_path)
    manager = OrderManager(ledger, fake_broker)
    response = asyncio.run(manager.submit(intent(), reserved_cash=Decimal("700")))
    assert response["orderId"] == "O1"
    assert ledger.pending_intents()[0]["state"] == "SENT"
    asyncio.run(manager.reconcile())
    assert len(ledger.fills_for("l1")) == 0
    ledger.close()


def test_ambiguous_send_is_unknown(db_path):
    from .conftest import FakeBroker
    class Broken(FakeBroker):
        async def submit_order(self, request): raise TimeoutError()
    ledger = Ledger(db_path); manager = OrderManager(ledger, Broken())
    try:
        asyncio.run(manager.submit(intent(), reserved_cash=Decimal("700")))
    except TimeoutError: pass
    assert ledger.pending_intents()[0]["state"] == "SEND_UNKNOWN"
