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


def test_exit_uses_the_margin_position_even_if_closed_intraday_row_comes_first(db_path, fake_broker):
    inst=Instrument('23650','NIFTY',Segment.NSE_FNO,date(2026,9,15),OptionType.PE,Decimal('23650'),65,Decimal('.05'),1800)
    book=OptionBook(inst,(Level(Decimal('95'),130),),(Level(Decimal('95.05'),130),),'dhan',1_700_000_000_000_000_000)
    fake_broker._positions=[{'securityId':'23650','netQty':0,'exchangeSegment':'NSE_FNO','productType':'INTRADAY'},
                            {'securityId':'23650','netQty':65,'exchangeSegment':'NSE_FNO','productType':'MARGIN'}]
    calls=[]
    original=fake_broker.positions
    async def positions():
        calls.append(True)
        return await original()
    fake_broker.positions=positions
    ledger=Ledger(db_path)
    try:
        response=asyncio.run(ExitManager(ledger,fake_broker).reduce(inst,65,book,'l1'))
        assert response['orderId']=='O1'
        assert len(calls)==1  # The OMS performs the serialized final position check.
        assert fake_broker.requests[0]['productType']=='MARGIN'
    finally:ledger.close()
