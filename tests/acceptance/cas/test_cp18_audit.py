from dhan_cas_bot.domain import dec

def test_cp18_positive(): assert dec("1.00","x")==1
def test_cp18_negative():
    import pytest
    with pytest.raises(Exception): dec(float("nan"),"x")
def test_cp18_recovery(): assert dec("-1","x",allow_negative=True)==-1
