from datetime import date
from decimal import Decimal
from dhan_cas_bot.domain import CasPhase,CasStatus,IndexObservation
from dhan_cas_bot.strategy import select_reference

def _o(i):
    p=995000+i*500; return IndexObservation(Decimal(25000+i),p,(p-50)*1000000,"e",i,raw_identity=str(i))
def test_cp05_positive(): assert select_reference([_o(i) for i in range(5)],CasStatus(CasPhase.CTS_CLOSE,1000000,date(2026,9,15),"e"),0).value==Decimal(25002)
def test_cp05_negative():
    import pytest
    with pytest.raises(Exception): select_reference([_o(i) for i in range(4)],CasStatus(CasPhase.CTS_CLOSE,1000000,date(2026,9,15),"e"),0)
def test_cp05_recovery(): assert len(select_reference([_o(i) for i in range(5)],CasStatus(CasPhase.CTS_CLOSE,1000000,date(2026,9,15),"e"),0).event_ids)==5
