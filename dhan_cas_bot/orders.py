from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Protocol
import uuid
import json
from zoneinfo import ZoneInfo

from .domain import ContractError, Fill, FundsSnapshot, Intent
from .ledger import Ledger
from .risk import reserve_cash, worst_case_entry_cash

TERMINAL = {"TRADED", "CANCELLED", "REJECTED", "EXPIRED"}


class Broker(Protocol):
    account_id: str
    async def submit_order(self, request: dict[str, Any]) -> dict[str, Any]: ...
    async def order(self, order_id: str) -> dict[str, Any] | None: ...
    async def orders(self) -> list[dict[str, Any]]: ...
    async def trades(self) -> list[dict[str, Any]]: ...
    async def positions(self) -> list[dict[str, Any]]: ...
    async def funds(self) -> FundsSnapshot: ...


def order_request(intent: Intent, account_id: str) -> dict[str, Any]:
    if len(intent.client_order_id) > 30:
        raise ContractError("Dhan correlationId exceeds 30 characters")
    intent.instrument.tick(intent.limit_price)
    if intent.quantity > intent.instrument.freeze_qty:
        raise ContractError("child order exceeds current quantity freeze")
    for bound, invalid in ((intent.instrument.lower_limit, lambda x: intent.limit_price < x), (intent.instrument.upper_limit, lambda x: intent.limit_price > x)):
        if bound is not None and invalid(bound):
            raise ContractError("order price outside instrument band")
    return {"dhanClientId": account_id, "correlationId": intent.client_order_id,
            "transactionType": intent.side, "exchangeSegment": "NSE_FNO",
            "productType": "MARGIN", "orderType": "LIMIT", "validity": "IOC",
            "securityId": intent.instrument.security_id, "quantity": intent.quantity,
            "price": str(intent.limit_price), "afterMarketOrder": False}


class OrderManager:
    def __init__(self, ledger: Ledger, broker: Broker):
        self.ledger, self.broker = ledger, broker
        if not hasattr(ledger, "order_lock"):
            ledger.order_lock = asyncio.Lock()
        self.lock = ledger.order_lock

    def _rate_attempt(self, intent: Intent, attempt_id: str) -> None:
        timestamp = datetime.now(timezone.utc).timestamp()
        # Count all ambiguous writes. Reserve exit slots from potential fills,
        # including buys whose HTTP response has not arrived.
        potential = sum(max(0, x["quantity"]) for x in self.ledger.pending_intents() if x["side"] == "BUY")
        for row in self.ledger.db.execute("SELECT lifecycle_id FROM lifecycles WHERE state!='CLOSED'"):
            potential += self.ledger.lifecycle_totals(row[0])["quantity"]
        reserve = max(1, (potential + intent.instrument.freeze_qty - 1) // intent.instrument.freeze_qty) if intent.side == "BUY" else 0
        with self.ledger.transaction() as db:
            for seconds, limit in ((1, 9), (60, 250), (3600, 1000), (86400, 7000)):
                used = db.execute("SELECT COUNT(*) FROM rate_events WHERE occurred_at>?", (timestamp-seconds,)).fetchone()[0]
                if used + 1 + reserve > limit:
                    raise ContractError(f"RATE_CAPACITY:{seconds}")
            db.execute("INSERT INTO rate_events VALUES(?,?,?)", (attempt_id, timestamp, intent.side))

    async def submit(self, intent: Intent, *, reserved_cash: Decimal, pre_dispatch=None) -> dict[str, Any]:
        request = order_request(intent, self.broker.account_id)
        if intent.side == "BUY" and reserved_cash < reserve_cash(worst_case_entry_cash(intent.quantity, intent.limit_price)):
            raise ContractError("entry reservation understates worst-case debit")
        async with self.lock:
            if pre_dispatch is not None and not pre_dispatch():
                raise ContractError("entry inputs changed before dispatch")
            if intent.side == "SELL":
                pending = sum(row["quantity"] for row in self.ledger.pending_intents() if row["side"] == "SELL" and row["security_id"] == intent.instrument.security_id)
                positions = await self.broker.positions()
                held = sum(int(row.get("netQty", row.get("netQuantity", 0))) for row in positions if str(row.get("securityId")) == intent.instrument.security_id and row.get("exchangeSegment", "NSE_FNO") == "NSE_FNO" and row.get("productType", "MARGIN") == "MARGIN")
                if intent.quantity + pending > held:
                    raise ContractError("sale exceeds unreserved broker long quantity")
            self.ledger.create_intent(intent, reserved_cash)
            attempt_id = uuid.uuid4().hex
            try:
                self._rate_attempt(intent, attempt_id)
            except ContractError:
                self.ledger.set_intent_state(intent.intent_id, "ABORTED")
                raise
            self.ledger.record_attempt(attempt_id, intent.intent_id, "STARTED", {})
            try:
                response = await self.broker.submit_order(request)
            except BaseException as exc:
                self.ledger.record_attempt(attempt_id, intent.intent_id, "UNKNOWN", {"error": type(exc).__name__})
                raise
            if not isinstance(response, dict) or not response.get("orderId"):
                self.ledger.record_attempt(attempt_id, intent.intent_id, "UNKNOWN", {"error": "ambiguous_response"})
                raise ContractError("broker response is ambiguous; reconciliation required")
            self.ledger.record_attempt(attempt_id, intent.intent_id, "ACCEPTED", response)
            self.ledger.record_order(str(response["orderId"]), intent.intent_id, self.broker.account_id, str(response.get("orderStatus", "TRANSIT")), response)
            return response

    async def reconcile(self) -> dict[str, Any]:
        async with self.lock:
            orders = await self.broker.orders()
            trades = await self.broker.trades()
            positions = await self.broker.positions()
            if any(not isinstance(rows, list) for rows in (orders, trades, positions)):
                raise ContractError("broker reconciliation response is not a list")
            intent_rows = list(self.ledger.db.execute("SELECT * FROM intents ORDER BY created_at"))
            today = datetime.now(ZoneInfo("Asia/Kolkata")).date()
            previous_dates = [datetime.fromisoformat(row["created_at"]).astimezone(ZoneInfo("Asia/Kolkata")).date() for row in intent_rows]
            historical = getattr(self.broker, "historical_trades", None)
            if historical and previous_dates and min(previous_dates) < today:
                # Read yesterday's facts after a restart; today's empty trade
                # book must never erase fills or establish settlement cash.
                trades = trades + await historical(min(previous_dates), today)
            by_corr = {str(x.get("correlationId")): x for x in orders if x.get("correlationId")}
            by_id = {str(x.get("orderId")): x for x in orders}
            for row in intent_rows:
                saved = self.ledger.db.execute("SELECT * FROM orders WHERE intent_id=?", (row["intent_id"],)).fetchone()
                broker_order = by_corr.get(row["client_order_id"]) or (by_id.get(saved["order_id"]) if saved else None)
                if broker_order is None and saved and saved["state"] in TERMINAL:
                    broker_order = json.loads(saved["payload"])
                lookup = getattr(self.broker, "order_by_correlation", None)
                if broker_order is None and lookup and row["state"] not in {"FILLED","CANCELLED","REJECTED","EXPIRED","ABORTED","PENDING_SEND"}:
                    broker_order = await lookup(row["client_order_id"])
                if broker_order is None:
                    attempts = self.ledger.db.execute("SELECT COUNT(*) FROM attempts WHERE intent_id=?", (row["intent_id"],)).fetchone()[0]
                    if row["state"] == "PENDING_SEND" and not attempts:
                        self.ledger.set_intent_state(row["intent_id"], "ABORTED")
                    # A missing broker order is UNKNOWN, never safe to resubmit.
                    continue
                order_id = str(broker_order.get("orderId", ""))
                if not order_id:
                    raise ContractError("broker order has no identity")
                for key, expected in (("dhanClientId", self.broker.account_id), ("securityId", row["security_id"]), ("transactionType", row["side"]), ("exchangeSegment", "NSE_FNO"), ("productType", "MARGIN")):
                    if key in broker_order and str(broker_order[key]) != expected:
                        raise ContractError("foreign or contradictory broker order")
                state = str(broker_order.get("orderStatus", "UNKNOWN"))
                self.ledger.record_order(order_id, row["intent_id"], self.broker.account_id, state, broker_order)
                for trade in trades:
                    if str(trade.get("orderId")) != order_id:
                        continue
                    for key, expected in (("dhanClientId", self.broker.account_id), ("securityId", row["security_id"]), ("transactionType", row["side"]), ("exchangeSegment", "NSE_FNO"), ("productType", "MARGIN")):
                        if key in trade and str(trade[key]) != expected:
                            raise ContractError("foreign or contradictory broker fill")
                    trade_id = str(trade.get("exchangeTradeId") or trade.get("tradeId") or "")
                    fees = Decimal(str(trade.get("fees", "0")))
                    components = ("sebiTax","stt","brokerageCharges","serviceTax","exchangeTransactionCharges","stampDuty")
                    fees = max(fees, sum((Decimal(str(trade.get(key, "0"))) for key in components), Decimal("0")))
                    fill = Fill(trade_id, order_id, row["security_id"], int(trade["tradedQuantity"]), Decimal(str(trade["tradedPrice"])), fees, datetime.now(timezone.utc))
                    self.ledger.record_fill_once(fill, row["intent_id"], trade)
                filled = self.ledger.db.execute("SELECT COALESCE(SUM(quantity),0) FROM fills WHERE intent_id=?", (row["intent_id"],)).fetchone()[0]
                state = self.ledger.db.execute("SELECT state FROM orders WHERE order_id=?", (order_id,)).fetchone()[0]
                expected = int(broker_order.get("filledQty", broker_order.get("filledQuantity", row["quantity"] if state == "TRADED" else filled)))
                if expected > row["quantity"] or filled > row["quantity"]:
                    raise ContractError("broker fill exceeds submitted quantity")
                if state in TERMINAL and filled >= expected:
                    self.ledger.set_intent_state(row["intent_id"], "FILLED" if filled == row["quantity"] else state)
            return {"orders": orders, "trades": trades, "positions": positions, "unresolved": bool(self.ledger.pending_intents())}
