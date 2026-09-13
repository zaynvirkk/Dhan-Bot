from datetime import datetime,timezone
import pytest
from dhan_cas_bot.governor import RateGovernor

def test_cp13_positive():
    g=RateGovernor(); [g.admit(datetime.now(timezone.utc)) for _ in range(10)]
def test_cp13_negative():
    g=RateGovernor(); now=datetime.now(timezone.utc); [g.admit(now) for _ in range(10)]
    with pytest.raises(Exception): g.admit(now)
def test_cp13_recovery(): assert RateGovernor().limits[0][1]==10
