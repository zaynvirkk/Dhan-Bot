from decimal import Decimal
from dhan_cas_bot.settlement import exercise_intrinsic,compare_sale_and_exercise
from dhan_cas_bot.domain import OptionType

def test_cp12_positive(): assert exercise_intrinsic(OptionType.CE,Decimal("25000"),Decimal("25100"))==Decimal("100")
def test_cp12_negative(): assert exercise_intrinsic(OptionType.PE,Decimal("25000"),Decimal("25100"))==0
def test_cp12_recovery(): assert compare_sale_and_exercise(sale_proceeds=Decimal("10"),exercise_value=Decimal("9"),sale_costs=Decimal("0"),exercise_costs=Decimal("0"))=="SALE"
