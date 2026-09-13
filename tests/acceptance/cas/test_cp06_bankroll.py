from decimal import Decimal
from dhan_cas_bot.risk import lifecycle_ceiling

def test_cp06_positive(): assert lifecycle_ceiling(Decimal("80000"))==Decimal("20000.00")
def test_cp06_negative(): assert lifecycle_ceiling(Decimal("0"))==0
def test_cp06_recovery(): assert lifecycle_ceiling(Decimal("9411.18"))==Decimal("9411.18")
