from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime, timezone
import uuid

from .domain import ContractError, Instrument, Intent, OptionBook
from .ledger import Ledger
from .orders import Broker, OrderManager
from .risk import FeeSchedule, worst_case_entry_cash, reserve_cash


@dataclass(frozen=True)
class RouteProof:
    epoch: str
    order_id: str
    account_id: str
    accepted_at: datetime
    zero_fill: bool


class RouteQualifier:
    def __init__(self, ledger: Ledger, broker: Broker, *, session_id: str, max_attempts: int, debit_cap: Decimal, mandate_spend_cap: Decimal):
        if max_attempts <= 0 or debit_cap <= 0 or mandate_spend_cap <= 0:
            raise ContractError("qualification budgets must be finite and positive")
        self.ledger = ledger
        self.broker = broker
        self.session_id = session_id
        self.max_attempts = max_attempts
        self.debit_cap = debit_cap
        self.mandate_spend_cap = mandate_spend_cap

    async def qualify(self, book: OptionBook, *, epoch: str) -> RouteProof:
        attempts = int(self.ledger.counter(f"probe.attempts:{self.session_id}"))
        spent = self.ledger.counter("probe.spent")
        if attempts >= self.max_attempts:
            raise ContractError("qualification attempt budget exhausted")
        bid = book.top_bid
        if bid is None or bid.quantity < book.instrument.lot_size:
            raise ContractError("no one-lot bid for qualification")
        limit = bid.price - book.instrument.tick_size
        if limit <= 0:
            raise ContractError("no positive non-marketable probe price")
        cost = reserve_cash(worst_case_entry_cash(book.instrument.lot_size, limit, 1, FeeSchedule()))
        if cost > self.debit_cap or spent + cost > self.mandate_spend_cap:
            raise ContractError("qualification debit budget exhausted")
        intent = Intent("probe-" + uuid.uuid4().hex, "BUY", book.instrument, book.instrument.lot_size, limit, "probe-" + uuid.uuid4().hex, datetime.now(timezone.utc), "route-probe")
        manager = OrderManager(self.ledger, self.broker)
        self.ledger.set_counter(f"probe.attempts:{self.session_id}", attempts + 1)
        response = await manager.submit(intent, reserved_cash=cost)
        self.ledger.set_counter("probe.spent", spent + cost)
        order_id = str(response["orderId"])
        if response.get("accountId", self.broker.account_id) != self.broker.account_id:
            raise ContractError("qualification response account mismatch")
        return RouteProof(epoch, order_id, self.broker.account_id, datetime.now(timezone.utc), response.get("orderStatus") in {"CANCELLED", "REJECTED"})
