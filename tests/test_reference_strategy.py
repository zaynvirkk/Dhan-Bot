from datetime import date
from decimal import Decimal
import pytest

from dhan_cas_bot.domain import CasPhase, CasStatus, IndexObservation, Instrument, Level, OptionBook, OptionType, Segment, ContractError
from dhan_cas_bot.strategy import select_reference, Reference, find_opportunity
from dhan_cas_bot.risk import Allocation


def obs(i, value="25000", ts=1_000_000, epoch="e"):
    provider = ts - 5000 + i * 500
    return IndexObservation(Decimal(value), provider, (provider - 50) * 1_000_000, epoch, i, raw_identity=f"f{i}")


def test_reference_strict_boundary_and_median():
    status = CasStatus(CasPhase.CTS_CLOSE, 1_000_000, date(2026, 9, 15), "e")
    reference = select_reference([obs(i, str(24990 + i)) for i in range(5)], status, 100)
    assert reference.value == Decimal("24992")
    bad = obs(5, "25000", ts=1_002_500)
    with pytest.raises(ContractError): select_reference([obs(i, str(24990 + i)) for i in range(4)] + [bad], status, 100)
    with pytest.raises(ContractError): select_reference([obs(i, str(24990 + i)) for i in range(5)], status, 101)


def test_strategy_requires_bid_and_ask_lot_and_does_not_need_future():
    status = CasStatus(CasPhase.CTS_CLOSE, 1_000_000, date(2026, 9, 15), "e")
    ref = select_reference([obs(i, str(24990 + i)) for i in range(5)], status, 0)
    inst = Instrument("25100", "NIFTY", Segment.NSE_FNO, date(2026, 9, 15), OptionType.PE, Decimal("25100"), 65, Decimal("0.05"), 1800)
    book = OptionBook(inst, (Level(Decimal("9"), 65),), (Level(Decimal("10"), 195),), "dhan", 1_700_000_000_000_000_000)
    allocation = Allocation.start(Decimal("9411.18"), Decimal("9411.18"))
    assert find_opportunity(ref, [(Decimal("24980"), "a"), (Decimal("24900"), "b")], [book], allocation) is not None
    thin = OptionBook(inst, (Level(Decimal("9"), 1),), book.asks, "dhan", book.received_ns)
    assert find_opportunity(ref, [(Decimal("24980"), "a"), (Decimal("24900"), "b")], [thin], allocation) is None


def test_opposite_direction_observations_do_not_establish_persistence():
    ref = Reference(Decimal("25000"), 1, (), "e")
    inst = Instrument("1", "NIFTY", Segment.NSE_FNO, date(2026,9,15), OptionType.PE, Decimal("25100"),65,Decimal("0.05"),1800)
    book = OptionBook(inst,(Level(Decimal("9"),65),),(Level(Decimal("10"),195),),"d",1)
    assert find_opportunity(ref,[(Decimal("25001"),"a"),(Decimal("24900"),"b")],[book],Allocation.start(Decimal("9000"),Decimal("9000"))) is None
