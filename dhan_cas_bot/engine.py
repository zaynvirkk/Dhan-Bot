from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Iterable
import uuid

from .domain import CasPhase, CasStatus, ContractError, IndexObservation, OptionBook, Intent
from .orders import Broker, OrderManager
from .risk import Allocation, FeeSchedule, reserve_cash, worst_case_entry_cash
from .runtime import AutoLive
from .strategy import Reference, find_opportunity, select_reference


@dataclass
class SessionEngine:
    runtime: AutoLive
    books: dict[str, OptionBook]
    reference: Reference | None = None
    status: CasStatus | None = None
    observations: list[tuple[Decimal, str]] = None
    reference_observations: list[IndexObservation] = None
    consumed_episodes: set[str] = None

    def __post_init__(self) -> None:
        self.observations = [] if self.observations is None else self.observations
        self.reference_observations = [] if self.reference_observations is None else self.reference_observations
        self.consumed_episodes = set() if self.consumed_episodes is None else self.consumed_episodes

    def on_status(self, status: CasStatus, *, clock_uncertainty_ms: int = 0) -> None:
        self.status = status
        if status.phase is CasPhase.CTS_CLOSE and self.reference is None:
            self.reference = select_reference(self.reference_observations, status, clock_uncertainty_ms)
            self.runtime.ledger.freeze_reference(status.trading_date.isoformat(), self.reference)
        self.runtime.status.official_cas_signal_seen = status.phase is not CasPhase.UNKNOWN

    def on_ltp(self, observation: IndexObservation) -> None:
        if self.reference is None:
            self.reference_observations.append(observation)

    async def on_iep(self, observation: IndexObservation) -> bool:
        if self.reference is None or self.status is None:
            return False
        if observation.epoch != self.status.epoch or not observation.wrapper_present:
            return False
        identity = observation.raw_identity or f"{observation.epoch}:{observation.provider_ts_ms}:{observation.receiver_seq}"
        if identity in {x[1] for x in self.observations}:
            return False
        self.observations.append((observation.value, identity))
        self.observations = self.observations[-24:]
        if self.status.phase not in {CasPhase.CAS_LM_START, CasPhase.CAS_M_STOP} or not self.runtime.permit_entry():
            return False
        funds = await self.runtime.broker.funds()
        self.runtime.status.current_account_funded = funds.spendable_cash > 0
        allocation = Allocation.start(funds.strategy_equity, funds.spendable_cash)
        opportunity = find_opportunity(self.reference, self.observations, self.books.values(), allocation, FeeSchedule())
        if opportunity is None:
            return False
        episode = f"{opportunity.instrument.security_id}:{identity}"
        if episode in self.consumed_episodes:
            return False
        self.consumed_episodes.add(episode)
        intent = Intent("entry-" + uuid.uuid4().hex, "BUY", opportunity.instrument, opportunity.quantity, opportunity.limit_price, "entry-" + uuid.uuid4().hex, datetime.now(timezone.utc), "lifecycle-" + uuid.uuid4().hex)
        await self.runtime.orders.submit(intent, reserved_cash=reserve_cash(worst_case_entry_cash(opportunity.quantity, opportunity.limit_price, 1, FeeSchedule())))
        self.runtime.status.state = "ENTRY_PENDING"
        return True

    def on_book(self, book: OptionBook) -> None:
        self.books[book.instrument.security_id] = book
