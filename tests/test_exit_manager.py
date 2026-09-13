from datetime import date
from decimal import Decimal
import asyncio
import pytest

from dhan_cas_bot.domain import Instrument, Level, OptionBook, OptionType, Segment, ContractError
from dhan_cas_bot.exit_manager import ExitManager
from dhan_cas_bot.ledger import Ledger


def test_sale_uses_finite_depth_and_never_oversells(db_path, fake_broker):
    inst = Instrument("23650", "NIFTY", Segment.NSE_FNO, date(2026, 9, 15), OptionType.PE, Decimal("23650"), 65, Decimal("0.05"), 1800)
    book = OptionBook(inst, (Level(Decimal("95"), 65), Level(Decimal("94"), 65)), (Level(Decimal("100"), 65),), "dhan", 1_700_000_000_000_000_000)
    fake_broker._positions = [{"securityId": "23650", "netQty": 130}]
    response = asyncio.run(ExitManager(Ledger(db_path), fake_broker).reduce(inst, 65, book, "l1"))
    assert response["orderId"] == "O1" and fake_broker.requests[0]["transactionType"] == "SELL"
    with pytest.raises(ContractError): asyncio.run(ExitManager(Ledger(db_path), fake_broker).reduce(inst, 195, book, "l1"))
