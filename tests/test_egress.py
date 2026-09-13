import asyncio
import pytest
from dhan_cas_bot.egress import require_expected_egress
from dhan_cas_bot.domain import ContractError


def test_missing_expected_egress_fails_closed():
    with pytest.raises(ContractError): asyncio.run(require_expected_egress(""))
