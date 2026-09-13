from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
from typing import Iterable

from .domain import ContractError, FundsSnapshot, Instrument, OptionBook, dec


PAISE = Decimal("0.01")


def ceil_paise(value: Decimal) -> Decimal:
    return value.quantize(PAISE, rounding=ROUND_CEILING)


def floor_paise(value: Decimal) -> Decimal:
    return value.quantize(PAISE, rounding=ROUND_FLOOR)


def lifecycle_ceiling(bankroll: Decimal) -> Decimal:
    """The operator's fixed capital rule; non-positive equity cannot buy."""
    bankroll = dec(bankroll, "bankroll", allow_negative=True)
    if bankroll <= 0:
        return Decimal("0")
    if bankroll < Decimal("40000"):
        return bankroll.min(Decimal("10000"))
    return floor_paise(bankroll * Decimal("0.25"))


@dataclass(frozen=True)
class FeeSchedule:
    brokerage_per_child: Decimal = Decimal("20")
    exchange_rate: Decimal = Decimal("3552") / Decimal("10000000")
    sebi_rate: Decimal = Decimal("10") / Decimal("10000000")
    ipft_rate: Decimal = Decimal("0.01") / Decimal("10000000")
    buy_stamp_rate: Decimal = Decimal("0.00003")
    sell_stt_rate: Decimal = Decimal("0.0015")
    gst_rate: Decimal = Decimal("0.18")

    def _common(self, turnover: Decimal, children: int) -> Decimal:
        brokerage = self.brokerage_per_child * children
        exchange = turnover * self.exchange_rate
        sebi = turnover * self.sebi_rate
        ipft = turnover * self.ipft_rate
        return brokerage + exchange + sebi + ipft + (brokerage + exchange + sebi + ipft) * self.gst_rate

    def buy(self, turnover: Decimal, children: int) -> Decimal:
        return self._common(turnover, children) + turnover * self.buy_stamp_rate

    def sell(self, turnover: Decimal, children: int) -> Decimal:
        return self._common(turnover, children) + turnover * self.sell_stt_rate


def worst_case_entry_cash(quantity: int, limit: Decimal, children: int = 1, fees: FeeSchedule | None = None) -> Decimal:
    limit = dec(limit, "limit")
    if quantity <= 0 or children <= 0 or limit <= 0:
        raise ContractError("entry cash inputs must be positive")
    fees = fees or FeeSchedule()
    turnover = Decimal(quantity) * limit
    return turnover + fees.buy(turnover, children)


def conditional_sale_cash(quantity: int, target: Decimal, children: int = 1, fees: FeeSchedule | None = None) -> Decimal:
    fees = fees or FeeSchedule()
    turnover = Decimal(quantity) * target
    return turnover - fees.sell(turnover, children)


def reserve_cash(value: Decimal) -> Decimal:
    return ceil_paise(value)


@dataclass(frozen=True)
class Allocation:
    bankroll: Decimal
    ceiling: Decimal
    remaining: Decimal
    spendable_cash: Decimal
    selected_cap_remaining: Decimal | None

    @classmethod
    def start(cls, bankroll: Decimal, spendable_cash: Decimal, consumed: Decimal = Decimal("0"), reserved: Decimal = Decimal("0"), debit_cap_remaining: Decimal | None = None) -> "Allocation":
        ceiling = lifecycle_ceiling(bankroll)
        remaining = ceiling - consumed - reserved
        return cls(bankroll, ceiling, max(Decimal("0"), remaining), max(Decimal("0"), spendable_cash), debit_cap_remaining)

    def permits(self, cash: Decimal) -> bool:
        if cash <= 0:
            return False
        if cash > self.remaining or cash > self.spendable_cash:
            return False
        return self.selected_cap_remaining is None or cash <= self.selected_cap_remaining


def ladder_capacity(book: OptionBook, limit: Decimal) -> int:
    """Return whole-lot quantity available at or below a LIMIT price."""
    book.instrument.tick(limit)
    total = sum(level.quantity for level in book.asks if level.price <= limit)
    return (total // book.instrument.lot_size) * book.instrument.lot_size


def candidate_quantities(book: OptionBook, limit: Decimal, allocation: Allocation, children: int = 1, fees: FeeSchedule | None = None) -> Iterable[int]:
    fees = fees or FeeSchedule()
    available = min(ladder_capacity(book, limit), book.instrument.freeze_qty)
    for quantity in range(book.instrument.lot_size, available + 1, book.instrument.lot_size):
        if allocation.permits(reserve_cash(worst_case_entry_cash(quantity, limit, children, fees))):
            yield quantity


def reconcile_funds(snapshot: FundsSnapshot, mandate_capital: Decimal) -> Decimal:
    if snapshot.broker_account == "":
        raise ContractError("broker account is missing")
    cap = dec(mandate_capital, "mandate capital")
    return min(snapshot.strategy_equity, cap) if cap else snapshot.strategy_equity
