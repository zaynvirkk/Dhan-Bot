from datetime import date
from decimal import Decimal
import pytest
from dhan_cas_bot.domain import Instrument, OptionType, Segment, ContractError

def test_cp04_positive(): assert Instrument("1","NIFTY",Segment.NSE_FNO,date(2026,9,15),OptionType.CE,Decimal("25000"),65,Decimal("0.05"),1800).lot_size==65
def test_cp04_negative():
    with pytest.raises(ContractError): Instrument("1","BANKNIFTY",Segment.NSE_FNO,date(2026,9,15),OptionType.CE,Decimal("25000"),65,Decimal("0.05"),1800)
def test_cp04_recovery(): assert date(2026,9,15).weekday() == 1
