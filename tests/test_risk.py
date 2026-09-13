from decimal import Decimal

from dhan_cas_bot.risk import lifecycle_ceiling, worst_case_entry_cash, FeeSchedule


def test_bankroll_boundaries_and_fixture_cash():
    assert lifecycle_ceiling(Decimal("-1")) == Decimal("0")
    assert lifecycle_ceiling(Decimal("0")) == Decimal("0")
    assert lifecycle_ceiling(Decimal("9411.18")) == Decimal("9411.18")
    assert lifecycle_ceiling(Decimal("10000")) == Decimal("10000")
    assert lifecycle_ceiling(Decimal("25000")) == Decimal("10000")
    assert lifecycle_ceiling(Decimal("39999.99")) == Decimal("10000")
    assert lifecycle_ceiling(Decimal("40000")) == Decimal("10000.00")
    assert lifecycle_ceiling(Decimal("80000")) == Decimal("20000.00")
    assert lifecycle_ceiling(Decimal("100000")) == Decimal("25000.00")
    assert worst_case_entry_cash(845, Decimal("11")) == Decimal("9322.78569818810")


def test_cash_rejects_float_and_negative():
    import pytest
    from dhan_cas_bot.domain import ContractError
    with pytest.raises(ContractError): worst_case_entry_cash(1, 11.0)
    with pytest.raises(ContractError): lifecycle_ceiling(Decimal("NaN"))
