from decimal import Decimal
from dhan_cas_bot.exits import executable_sale_units
from .support import book

def test_cp10_positive(): assert executable_sale_units(book(),130)==[(65,Decimal("9"))]
def test_cp10_negative(): assert executable_sale_units(book(),0)==[]
def test_cp10_recovery(): assert sum(q for q,_ in executable_sale_units(book(),195))==65
