from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable

from .domain import CasPhase, CasStatus, ContractError, IndexObservation, OptionBook, OptionType
from .risk import Allocation, FeeSchedule, conditional_sale_cash, reserve_cash, worst_case_entry_cash, ladder_capacity


REFERENCE_MAX_AGE_MS = 30_000
MAX_CLOCK_UNCERTAINTY_MS = 100
MAX_HISTORY = 24


@dataclass(frozen=True)
class Reference:
    value: Decimal
    boundary_ms: int
    event_ids: tuple[str, ...]
    epoch: str


def select_reference(observations: Iterable[IndexObservation], status: CasStatus, clock_uncertainty_ms: int) -> Reference:
    if status.phase is not CasPhase.CTS_CLOSE:
        raise ContractError("reference boundary must be CTS_CLOSE")
    if clock_uncertainty_ms > MAX_CLOCK_UNCERTAINTY_MS:
        raise ContractError("host clock uncertainty is too high")
    eligible = [
        x for x in observations
        if x.epoch == status.epoch
        and x.provider_ts_ms >= status.updated_time_ms - REFERENCE_MAX_AGE_MS
        and x.provider_ts_ms < status.updated_time_ms
        and x.received_ns // 1_000_000 >= status.updated_time_ms - REFERENCE_MAX_AGE_MS
        and x.received_ns // 1_000_000 + clock_uncertainty_ms < status.updated_time_ms
        and x.receiver_seq >= 0
        and x.frame_kind == "live_feed"
        and x.wrapper_present
    ]
    by_identity: dict[str, IndexObservation] = {}
    for item in eligible:
        identity = item.raw_identity or f"{item.epoch}:{item.provider_ts_ms}:{item.receiver_seq}:{item.value}"
        by_identity[identity] = item
    eligible = sorted(by_identity.values(), key=lambda x: (x.provider_ts_ms, x.receiver_seq))[-5:]
    if len(eligible) != 5:
        raise ContractError("REFERENCE_UNAVAILABLE: five distinct observations required")
    values = sorted(x.value for x in eligible)
    median = values[2]
    return Reference(median, status.updated_time_ms, tuple(x.raw_identity or f"{x.provider_ts_ms}:{x.receiver_seq}" for x in eligible), status.epoch)


def intrinsic(option_type: OptionType, strike: Decimal, index: Decimal) -> Decimal:
    if option_type is OptionType.CE:
        return max(index - strike, Decimal("0"))
    return max(strike - index, Decimal("0"))


@dataclass(frozen=True)
class Opportunity:
    instrument: object
    side: str
    quantity: int
    limit_price: Decimal
    conditional_edge: Decimal
    score: tuple[Decimal, Decimal, int]
    reason: str


def _same_direction(option_type: OptionType, current: Decimal, reference: Decimal) -> bool:
    return (current > reference and option_type is OptionType.CE) or (current < reference and option_type is OptionType.PE)


def find_opportunity(reference: Reference, observations: list[tuple[Decimal, str]], books: Iterable[OptionBook], allocation: Allocation, fees: FeeSchedule | None = None) -> Opportunity | None:
    """Find the deterministic best single-contract CAS lag.

    `observations` is a sequence of (official IEP, observation identity).
    Future data is deliberately not accepted by this function.
    """
    fees = fees or FeeSchedule()
    if len(observations) < 2:
        return None
    current = observations[-1][0]
    previous = observations[-2][0]
    if current == reference.value or len({identity for _, identity in observations}) < 2:
        return None
    direction = OptionType.CE if current > reference.value else OptionType.PE
    contiguous = []
    for value, identity in reversed(observations):
        if not _same_direction(direction, value, reference.value):
            break
        contiguous.append(value)
    if len(contiguous) < 2:
        return None
    eligible: list[Opportunity] = []
    for book in books:
        inst = book.instrument
        if inst.option_type is not direction:
            continue
        ask = book.top_ask
        bid = book.top_bid
        if ask is None or bid is None:
            continue
        if ask.quantity < inst.lot_size or bid.quantity < inst.lot_size:
            continue
        target = min(intrinsic(direction, inst.strike, value) for value in contiguous)
        if ask.price + inst.tick_size > target:
            continue
        limits = sorted({level.price for level in book.asks if level.price < target and level.quantity > 0})
        for limit in limits:
            available = (ladder_capacity(book, limit) // inst.lot_size) * inst.lot_size
            available = min(available, int(min(allocation.remaining,allocation.spendable_cash) / limit) // inst.lot_size * inst.lot_size)
            child_size = inst.freeze_qty // inst.lot_size * inst.lot_size
            low, high = 0, available // inst.lot_size
            while low < high:
                middle = (low+high+1)//2
                units = middle*inst.lot_size
                if allocation.permits(reserve_cash(worst_case_entry_cash(units,limit,(units+child_size-1)//child_size,fees))):
                    low = middle
                else:
                    high = middle-1
            maximum = low*inst.lot_size
            quantities = {inst.lot_size,maximum}
            for boundary in range(child_size,maximum+child_size,child_size):
                quantities.update((boundary,boundary-inst.lot_size))
            for quantity in sorted(q for q in quantities if 0 < q <= maximum):
                children = (quantity + child_size - 1) // child_size
                entry = reserve_cash(worst_case_entry_cash(quantity, limit, children, fees))
                if not allocation.permits(entry):
                    continue
                sale = conditional_sale_cash(quantity, target, children, fees)
                edge = sale - entry
                if edge <= 0:
                    continue
                score = (edge / entry, edge, quantity)
                eligible.append(Opportunity(inst, "BUY", quantity, limit, edge, score, "CAS_LAG_V1"))
    if not eligible:
        return None
    return max(eligible, key=lambda x: (x.score, -int(x.instrument.security_id), -x.limit_price))


def find_final_opportunity(final, books, allocation):
    """Confirmed final input needs no manufactured sequence of IEP observations."""
    final.validate()
    fees = FeeSchedule()
    choices = []
    for book in books:
        inst = book.instrument
        target = intrinsic(inst.option_type,inst.strike,final.value)
        if inst.expiry.isoformat() != final.trading_date or not book.top_ask:
            continue
        child = inst.freeze_qty//inst.lot_size*inst.lot_size
        for limit in sorted({x.price for x in book.asks if x.price+inst.tick_size <= target}):
            units = min(ladder_capacity(book,limit),int(min(allocation.remaining,allocation.spendable_cash)/limit)//inst.lot_size*inst.lot_size)
            low,high=0,units//inst.lot_size
            while low<high:
                middle=(low+high+1)//2; quantity=middle*inst.lot_size
                if allocation.permits(reserve_cash(worst_case_entry_cash(quantity,limit,(quantity+child-1)//child,fees))): low=middle
                else: high=middle-1
            quantity=low*inst.lot_size
            if not quantity: continue
            children=(quantity+child-1)//child
            entry=reserve_cash(worst_case_entry_cash(quantity,limit,children,fees))
            edge=conditional_sale_cash(quantity,target,children,fees)-entry
            if edge>0:
                choices.append(Opportunity(inst,"BUY",quantity,limit,edge,(edge/entry,edge,quantity),"FINAL_RESIDUAL"))
    return max(choices,key=lambda x:(x.score,-int(x.instrument.security_id),-x.limit_price)) if choices else None
