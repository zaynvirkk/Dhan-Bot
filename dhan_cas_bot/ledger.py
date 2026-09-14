from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterator
from dataclasses import asdict

from .domain import ContractError, Fill, Intent, Mandate, json_safe


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=FULL;
CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS mandates (account_id TEXT PRIMARY KEY, payload TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sessions (session_id TEXT PRIMARY KEY, trading_date TEXT NOT NULL, state TEXT NOT NULL, payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS references_frozen (session_id TEXT PRIMARY KEY, payload TEXT NOT NULL, committed_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS intents (intent_id TEXT PRIMARY KEY, client_order_id TEXT UNIQUE NOT NULL, lifecycle_id TEXT NOT NULL, side TEXT NOT NULL, security_id TEXT NOT NULL, quantity INTEGER NOT NULL, price TEXT NOT NULL, state TEXT NOT NULL, reserved_cash TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS attempts (attempt_id TEXT PRIMARY KEY, intent_id TEXT NOT NULL, sent_at TEXT NOT NULL, response_state TEXT NOT NULL, response TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS orders (order_id TEXT PRIMARY KEY, intent_id TEXT NOT NULL, broker_account TEXT NOT NULL, state TEXT NOT NULL, payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS fills (trade_id TEXT PRIMARY KEY, order_id TEXT NOT NULL, intent_id TEXT NOT NULL, security_id TEXT NOT NULL, quantity INTEGER NOT NULL, price TEXT NOT NULL, fees TEXT NOT NULL, occurred_at TEXT NOT NULL, payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS counters (name TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS cash_postings (posting_id TEXT PRIMARY KEY, lifecycle_id TEXT NOT NULL, amount TEXT NOT NULL, kind TEXT NOT NULL, payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS incidents (incident_id TEXT PRIMARY KEY, kind TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS lifecycles (lifecycle_id TEXT PRIMARY KEY, session_id TEXT NOT NULL, security_id TEXT NOT NULL, bankroll TEXT NOT NULL, state TEXT NOT NULL, payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS rate_events (event_id TEXT PRIMARY KEY, occurred_at REAL NOT NULL, kind TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS consumed_books (identity TEXT PRIMARY KEY, lifecycle_id TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS depth_debits (identity TEXT NOT NULL, intent_id TEXT PRIMARY KEY, quantity INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS settlements (receipt_id TEXT PRIMARY KEY, lifecycle_id TEXT NOT NULL, quantity INTEGER NOT NULL, net_credit TEXT NOT NULL, payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS observations (identity TEXT PRIMARY KEY, kind TEXT NOT NULL, received_at TEXT NOT NULL, payload TEXT NOT NULL);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Ledger:
    """Single-writer durable ledger. Every money transition is FULL committed."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.db = sqlite3.connect(self.path, isolation_level=None, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        self.db.execute("PRAGMA synchronous=FULL")

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                yield self.db
                self.db.execute("COMMIT")
            except Exception:
                self.db.execute("ROLLBACK")
                raise

    def put_mandate(self, mandate: Mandate) -> None:
        mandate.validate()
        payload = json.dumps(json_safe(mandate.__dict__), sort_keys=True)
        with self.transaction() as db:
            db.execute("INSERT INTO mandates(account_id,payload,updated_at) VALUES(?,?,?) ON CONFLICT(account_id) DO UPDATE SET payload=excluded.payload,updated_at=excluded.updated_at", (mandate.account_id, payload, now()))

    def freeze_reference(self, session_id: str, reference: Any) -> None:
        payload = json.dumps(json_safe(reference.__dict__), sort_keys=True)
        with self.transaction() as db:
            existing = db.execute("SELECT payload FROM references_frozen WHERE session_id=?", (session_id,)).fetchone()
            if existing and existing[0] != payload:
                raise ContractError("same-session reference is immutable")
            db.execute("INSERT OR IGNORE INTO references_frozen(session_id,payload,committed_at) VALUES(?,?,?)", (session_id, payload, now()))

    def create_intent(self, intent: Intent, reserved_cash: Decimal) -> None:
        if reserved_cash < 0 or (intent.side == "BUY" and reserved_cash == 0):
            raise ContractError("buy reservation must be positive")
        payload = json.dumps(json_safe(asdict(intent)), sort_keys=True)
        with self.transaction() as db:
            db.execute("INSERT INTO intents(intent_id,client_order_id,lifecycle_id,side,security_id,quantity,price,state,reserved_cash,payload,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)", (intent.intent_id, intent.client_order_id, intent.lifecycle_id, intent.side, intent.instrument.security_id, intent.quantity, str(intent.limit_price), "PENDING_SEND", str(reserved_cash), payload, intent.created_at.isoformat()))

    def record_attempt(self, attempt_id: str, intent_id: str, state: str, response: Any) -> None:
        with self.transaction() as db:
            db.execute("INSERT INTO attempts(attempt_id,intent_id,sent_at,response_state,response) VALUES(?,?,?,?,?) ON CONFLICT(attempt_id) DO UPDATE SET response_state=excluded.response_state,response=excluded.response", (attempt_id, intent_id, now(), state, json.dumps(json_safe(response), sort_keys=True, default=str)))
            db.execute("UPDATE intents SET state=? WHERE intent_id=?", ("SEND_UNKNOWN" if state in {"STARTED", "UNKNOWN"} else "SENT", intent_id))

    def record_order(self, order_id: str, intent_id: str, account: str, state: str, payload: Any) -> None:
        with self.transaction() as db:
            old = db.execute("SELECT * FROM orders WHERE order_id=?", (order_id,)).fetchone()
            if old and (old["intent_id"] != intent_id or old["broker_account"] != account):
                raise ContractError("order identity conflict")
            if old and old["state"] in {"TRADED", "CANCELLED", "REJECTED", "EXPIRED"} and state not in {"TRADED", "CANCELLED", "REJECTED", "EXPIRED"}:
                return
            db.execute("INSERT OR REPLACE INTO orders(order_id,intent_id,broker_account,state,payload) VALUES(?,?,?,?,?)", (order_id, intent_id, account, state, json.dumps(json_safe(payload), sort_keys=True, default=str)))

    def record_fill_once(self, fill: Fill, intent_id: str, payload: Any) -> bool:
        with self.transaction() as db:
            old = db.execute("SELECT * FROM fills WHERE trade_id=?", (fill.trade_id,)).fetchone()
            if old:
                if (old["order_id"], old["security_id"], old["quantity"], Decimal(old["price"])) != (fill.order_id, fill.security_id, fill.quantity, fill.price):
                    raise ContractError("conflicting duplicate fill")
                if fill.fees > Decimal(old["fees"]):
                    db.execute("UPDATE fills SET fees=? WHERE trade_id=?", (str(fill.fees),fill.trade_id))
                return False
            intent = db.execute("SELECT * FROM intents WHERE intent_id=?", (intent_id,)).fetchone()
            quantity = db.execute("SELECT COALESCE(SUM(quantity),0) FROM fills WHERE intent_id=?", (intent_id,)).fetchone()[0]
            if intent is None or fill.security_id != intent["security_id"] or quantity + fill.quantity > intent["quantity"]:
                raise ContractError("fill exceeds or mismatches intent")
            cursor = db.execute("INSERT OR IGNORE INTO fills(trade_id,order_id,intent_id,security_id,quantity,price,fees,occurred_at,payload) VALUES(?,?,?,?,?,?,?,?,?)", (fill.trade_id, fill.order_id, intent_id, fill.security_id, fill.quantity, str(fill.price), str(fill.fees), fill.occurred_at.isoformat(), json.dumps(json_safe(payload), sort_keys=True, default=str)))
            return cursor.rowcount == 1

    def set_intent_state(self, intent_id: str, state: str) -> None:
        with self.transaction() as db:
            db.execute("UPDATE intents SET state=? WHERE intent_id=?", (state, intent_id))

    def set_counter(self, name: str, value: Decimal | int) -> None:
        with self.transaction() as db:
            db.execute("INSERT INTO counters(name,value) VALUES(?,?) ON CONFLICT(name) DO UPDATE SET value=excluded.value", (name, str(value)))

    def counter(self, name: str) -> Decimal:
        row = self.db.execute("SELECT value FROM counters WHERE name=?", (name,)).fetchone()
        return Decimal(row[0]) if row else Decimal("0")

    def incident(self, incident_id: str, kind: str, payload: Any) -> None:
        with self.transaction() as db:
            db.execute("INSERT OR REPLACE INTO incidents(incident_id,kind,payload,created_at) VALUES(?,?,?,?)", (incident_id, kind, json.dumps(json_safe(payload), sort_keys=True, default=str), now()))

    def pending_intents(self) -> list[sqlite3.Row]:
        return list(self.db.execute("SELECT * FROM intents WHERE state NOT IN ('FILLED','CANCELLED','REJECTED','EXPIRED','ABORTED') ORDER BY created_at"))

    def observe(self, identity: str, kind: str, payload: Any) -> None:
        with self.transaction() as db:
            db.execute("INSERT OR IGNORE INTO observations VALUES(?,?,?,?)", (identity, kind, now(), json.dumps(json_safe(payload), sort_keys=True)))

    def observe_batch(self, items) -> None:
        with self.transaction() as db:
            db.executemany("INSERT OR IGNORE INTO observations VALUES(?,?,?,?)", [(identity,kind,now(),json.dumps(json_safe(payload),sort_keys=True)) for identity,kind,payload in items])

    def metadata(self, key: str, default: Any = None) -> Any:
        row = self.db.execute("SELECT value FROM metadata WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def put_metadata(self, key: str, value: Any) -> None:
        with self.transaction() as db:
            db.execute("INSERT INTO metadata VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, json.dumps(json_safe(value), sort_keys=True)))

    def lifecycle_totals(self, lifecycle_id: str) -> dict:
        from .risk import FeeSchedule, ceil_paise
        fees = FeeSchedule()
        buys = sells = Decimal("0")
        quantity = 0
        reserved = Decimal("0")
        unresolved = False
        for intent in self.db.execute("SELECT * FROM intents WHERE lifecycle_id=?", (lifecycle_id,)):
            fills = list(self.db.execute("SELECT * FROM fills WHERE intent_id=?", (intent["intent_id"],)))
            qty = sum(fill["quantity"] for fill in fills)
            turnover = sum((Decimal(fill["price"]) * fill["quantity"] for fill in fills), Decimal("0"))
            reported_fees = sum((Decimal(fill["fees"]) for fill in fills), Decimal("0"))
            cost = max(reported_fees, ceil_paise((fees.buy if intent["side"] == "BUY" else fees.sell)(turnover, 1))) if qty else Decimal("0")
            terminal = intent["state"] in {"FILLED", "CANCELLED", "REJECTED", "EXPIRED", "ABORTED"}
            unresolved |= not terminal
            if intent["side"] == "BUY":
                buys += turnover + cost
                quantity += qty
                if not terminal:
                    reserved += max(Decimal("0"), Decimal(intent["reserved_cash"]) - turnover - cost)
            else:
                sells += turnover - cost
                quantity -= qty
        if quantity < 0:
            raise ContractError("ledger contains a net short position")
        for row in self.db.execute("SELECT quantity,net_credit FROM settlements WHERE lifecycle_id=?",(lifecycle_id,)):
            quantity -= row[0]
            sells += Decimal(row[1])
        if quantity < 0:
            raise ContractError("settlement exceeds managed quantity")
        return {"entry_debit": buys, "sale_credit": sells, "quantity": quantity, "reserved": reserved, "unresolved": unresolved}

    def fills_for(self, lifecycle_id: str) -> list[sqlite3.Row]:
        return list(self.db.execute("SELECT f.* FROM fills f JOIN intents i ON i.intent_id=f.intent_id WHERE i.lifecycle_id=? ORDER BY f.occurred_at", (lifecycle_id,)))

    def close(self) -> None:
        with self._lock:
            self.db.close()
