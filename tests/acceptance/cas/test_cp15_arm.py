from decimal import Decimal
from dhan_cas_bot.domain import Mandate

def test_cp15_positive(): assert Mandate("TEST",allocated_capital=Decimal("1"),probe_entry_debit_cap_per_session=Decimal("1"),probe_spending_cap_per_mandate=Decimal("1")).strategy_id=="CAS_LAG_V1"
def test_cp15_negative():
    import pytest
    with pytest.raises(Exception): Mandate("",probe_entry_debit_cap_per_session=Decimal("1"),probe_spending_cap_per_mandate=Decimal("1")).validate()
def test_cp15_recovery(): assert Mandate("TEST",probe_entry_debit_cap_per_session=Decimal("1"),probe_spending_cap_per_mandate=Decimal("1")).live_order_authority is False
