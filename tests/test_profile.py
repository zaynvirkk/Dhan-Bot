import pytest

from dhan_cas_bot.domain import ContractError
from dhan_cas_bot.profile import require_derivatives_profile


@pytest.mark.parametrize("segments",["E, D, ","Equity, Derivative, Currency, Commodity","NSE_FNO"])
def test_affirmative_derivatives_profile(segments):
    require_derivatives_profile({"dhanClientId":"TEST","dataPlan":"Active","activeSegment":segments},"TEST")


@pytest.mark.parametrize("segments",["E, ","Equity, Currency Derivatives","",None])
def test_equity_or_currency_does_not_authorize_nifty_options(segments):
    with pytest.raises(ContractError):
        require_derivatives_profile({"dhanClientId":"TEST","dataPlan":"Active","activeSegment":segments},"TEST")
