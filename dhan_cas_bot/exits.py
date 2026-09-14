from __future__ import annotations

from decimal import Decimal

from .domain import ContractError, OptionBook


def sell_limit(book: OptionBook, *, emergency: bool = False) -> Decimal:
    bid = book.top_bid
    if bid is None and not emergency:
        raise ContractError("no current bid for normal sale")
    ticks = 10 if emergency else 2
    value = bid.price - book.instrument.tick_size * ticks if bid else book.instrument.tick_size
    value = max(book.instrument.tick_size, value)
    if book.instrument.lower_limit is not None:
        value = max(value, book.instrument.lower_limit)
    if book.instrument.upper_limit is not None:
        value = min(value, book.instrument.upper_limit)
    from decimal import ROUND_CEILING
    value = (value / book.instrument.tick_size).to_integral_value(rounding=ROUND_CEILING) * book.instrument.tick_size
    book.instrument.tick(value)
    return value


def executable_sale_units(book: OptionBook, quantity: int) -> list[tuple[int, Decimal]]:
    """Map a held quantity onto finite bid depth, never best-bid-times-all."""
    if quantity <= 0:
        return []
    remaining = quantity
    slices: list[tuple[int, Decimal]] = []
    for level in book.bids:
        if remaining <= 0:
            break
        units = min(remaining, level.quantity)
        if units:
            slices.append((units, level.price))
            remaining -= units
    return slices
