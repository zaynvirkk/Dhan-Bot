from dhan_cas_bot.risk import lifecycle_ceiling
from decimal import Decimal

def test_cp11_positive(): assert lifecycle_ceiling(Decimal("9411.18"))>0
def test_cp11_negative(): assert lifecycle_ceiling(Decimal("0"))==0
def test_cp11_recovery(): assert lifecycle_ceiling(Decimal("50000"))==Decimal("12500.00")
