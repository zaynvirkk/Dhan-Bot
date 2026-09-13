import pytest
from dhan_cas_bot.upstox_signal import extract_iep
from dhan_cas_bot.domain import ContractError

def test_cp01_positive(): assert extract_iep({"feeds":{"NSE_INDEX|Nifty 50":{"fullFeed":{"indexFF":{"ltpc":{"iep":{"value":25000}}}}}}}) > 0
def test_cp01_negative():
    with pytest.raises(ContractError): extract_iep({"feeds":{}})
def test_cp01_recovery(): assert extract_iep({"feeds":{"NSE_INDEX|Nifty 50":{"fullFeed":{"indexFF":{"ltpc":{"iep":{"value":25000}}}}}}}) == 25000
