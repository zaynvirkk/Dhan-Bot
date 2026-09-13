from datetime import date
from decimal import Decimal

from dhan_cas_bot.domain import Instrument, Level, OptionBook, OptionType, Segment, Mandate


def instrument():
    return Instrument("25100", "NIFTY", Segment.NSE_FNO, date(2026, 9, 15), OptionType.PE, Decimal("25100"), 65, Decimal("0.05"), 1800)


def book():
    i = instrument()
    return OptionBook(i, (Level(Decimal("9"), 65),), (Level(Decimal("10"), 195),), "dhan:1", 1_700_000_000_000_000_000)


def mandate(live=False):
    return Mandate("TEST", allocated_capital=Decimal("9411.18"), cumulative_entry_debit_cap=None, debit_cap_scope="none", probe_max_attempts_per_session=1, probe_entry_debit_cap_per_session=Decimal("100"), probe_spending_cap_per_mandate=Decimal("500"), live_order_authority=live)
