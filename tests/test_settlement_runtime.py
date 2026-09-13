from decimal import Decimal
from datetime import date
import asyncio

from dhan_cas_bot.domain import Mandate
from dhan_cas_bot.ledger import Ledger
from dhan_cas_bot.runtime import AutoLive


def mandate():
    return Mandate("TEST", allocated_capital=Decimal("9411.18"), cumulative_entry_debit_cap=None, debit_cap_scope="none", probe_max_attempts_per_session=1, probe_entry_debit_cap_per_session=Decimal("100"), probe_spending_cap_per_mandate=Decimal("500"), live_order_authority=False)


def test_runtime_recovery_is_broker_first_and_live_is_off_by_default(db_path, fake_broker):
    runtime = AutoLive(Ledger(db_path), fake_broker, mandate(), software_verified=True)
    asyncio.run(runtime.recover())
    assert runtime.status.state == "DISARMED"
    assert runtime.permit_entry() is False
    runtime.disarm_new_entries()
    assert runtime.status.state == "ENTRY_HALTED"
