from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Protocol
import uuid

from .domain import ContractError, Fill, FundsSnapshot, Intent
from .ledger import Ledger
from .risk import reserve_cash, worst_case_entry_cash


class Broker(Protocol):
    account_id: str

    async def submit_order(self, request: dict[str, Any]) -> dict[str, Any]: ...
    async def order(self, order_id: str) -> dict[str, Any] | None: ...
    async def orders(self) -> list[dict[str, Any]]: ...
    async def trades(self) -> list[dict[str, Any]]: ...
    async def positions(self) -> list[dict[str, Any]]: ...
    async def funds(self) -> FundsSnapshot: ...


def order_request(intent: Intent, account_id: str) -> dict[str, Any]:
    return {
        "dhanClientId": account_id,
        "correlationId": intent.client_order_id,
        "transactionType": intent.side,
        "exchangeSegment": "NSE_FNO",
        "productType": "MARGIN",
        "orderType": "LIMIT",
        "validity": "IOC",
        "securityId": intent.instrument.security_id,
        "quantity": intent.quantity,
        "price": str(intent.limit_price),
    }


class OrderManager:
    def __init__(self, ledger: Ledger, broker: Broker):
        self.ledger = ledger
        self.broker = broker

    async def submit(self, intent: Intent, *, reserved_cash: Decimal) -> dict[str, Any]:
        self.ledger.create_intent(intent, reserved_cash)
        attempt_id = uuid.uuid4().hex
        request = order_request(intent, self.broker.account_id)
        try:
            response = await self.broker.submit_order(request)
        except Exception as exc:
            self.ledger.record_attempt(attempt_id, intent.intent_id, "UNKNOWN", {"error": type(exc).__name__})
            raise
        if not isinstance(response, dict) or not response.get("orderId"):
            self.ledger.record_attempt(attempt_id, intent.intent_id, "UNKNOWN", response)
            raise ContractError("broker response is ambiguous; reconciliation required")
        self.ledger.record_attempt(attempt_id, intent.intent_id, "ACCEPTED", response)
        self.ledger.record_order(str(response["orderId"]), intent.intent_id, self.broker.account_id, str(response.get("orderStatus", "TRANSIT")), response)
        return response

    async def reconcile(self) -> dict[str, Any]:
        orders = await self.broker.orders()
        trades = await self.broker.trades()
        positions = await self.broker.positions()
        by_corr = {str(x.get("correlationId")): x for x in orders if x.get("correlationId")}
        for row in self.ledger.pending_intents():
            broker_order = by_corr.get(row["client_order_id"])
            if broker_order is None:
                continue
            order_id = str(broker_order.get("orderId", ""))
            if order_id:
                self.ledger.record_order(order_id, row["intent_id"], self.broker.account_id, str(broker_order.get("orderStatus", "UNKNOWN")), broker_order)
            for trade in trades:
                if str(trade.get("orderId")) != order_id:
                    continue
                fill = Fill(str(trade["tradeId"]), order_id, row["security_id"], int(trade["tradedQuantity"]), Decimal(str(trade["tradedPrice"])), Decimal(str(trade.get("fees", "0"))), datetime.now(timezone.utc))
                self.ledger.record_fill_once(fill, row["intent_id"], trade)
        return {"orders": orders, "trades": trades, "positions": positions}
