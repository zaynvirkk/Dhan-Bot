from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import uuid

from .domain import ContractError, Instrument, Intent
from .exits import sell_limit
from .ledger import Ledger
from .orders import Broker, OrderManager


class ExitManager:
    """Reduction path with priority over all entry decisions."""

    def __init__(self, ledger: Ledger, broker: Broker):
        self.ledger = ledger
        self.broker = broker
        self.orders = OrderManager(ledger, broker)

    async def reduce(self, instrument: Instrument, quantity: int, book, lifecycle_id: str, *, emergency: bool = False) -> dict:
        if quantity <= 0 or quantity % instrument.lot_size:
            raise ContractError("exit quantity must be whole lots")
        position_rows = await self.broker.positions()
        row = next((x for x in position_rows if str(x.get("securityId")) == instrument.security_id), None)
        broker_qty = int((row or {}).get("netQty", (row or {}).get("netQuantity", 0)))
        if broker_qty < quantity:
            raise ContractError("requested exit exceeds broker-verified long quantity")
        limit = sell_limit(book, emergency=emergency)
        quantity = min(quantity, instrument.freeze_qty // instrument.lot_size * instrument.lot_size)
        intent = Intent("exit-" + uuid.uuid4().hex, "SELL", instrument, quantity, limit, "x" + uuid.uuid4().hex[:28], datetime.now(timezone.utc), lifecycle_id)
        # A sell has no premium debit, but a tiny positive reservation keeps the
        # durable intent invariant and covers a charge/reconciliation incident.
        return await self.orders.submit(intent, reserved_cash=Decimal("0.01"))
