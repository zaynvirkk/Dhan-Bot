from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterator

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
        if reserved_cash <= 0:
            raise ContractError("intent reservation must be positive")
        payload = json.dumps(json_safe(intent.__dict__), sort_keys=True, default=str)
        with self.transaction() as db:
            db.execute("INSERT INTO intents(intent_id,client_order_id,lifecycle_id,side,security_id,quantity,price,state,reserved_cash,payload,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)", (intent.intent_id, intent.client_order_id, intent.lifecycle_id, intent.side, intent.instrument.security_id, intent.quantity, str(intent.limit_price), "PENDING_SEND", str(reserved_cash), payload, intent.created_at.isoformat()))

    def record_attempt(self, attempt_id: str, intent_id: str, state: str, response: Any) -> None:
        with self.transaction() as db:
            db.execute("INSERT INTO attempts(attempt_id,intent_id,sent_at,response_state,response) VALUES(?,?,?,?,?)", (attempt_id, intent_id, now(), state, json.dumps(json_safe(response), sort_keys=True, default=str)))
            db.execute("UPDATE intents SET state=? WHERE intent_id=?", ("SEND_UNKNOWN" if state == "UNKNOWN" else "SENT", intent_id))

    def record_order(self, order_id: str, intent_id: str, account: str, state: str, payload: Any) -> None:
        with self.transaction() as db:
            db.execute("INSERT OR REPLACE INTO orders(order_id,intent_id,broker_account,state,payload) VALUES(?,?,?,?,?)", (order_id, intent_id, account, state, json.dumps(json_safe(payload), sort_keys=True, default=str)))

    def record_fill_once(self, fill: Fill, intent_id: str, payload: Any) -> bool:
        with self.transaction() as db:
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
        return list(self.db.execute("SELECT * FROM intents WHERE state NOT IN ('FILLED','CANCELLED','REJECTED') ORDER BY created_at"))

    def fills_for(self, lifecycle_id: str) -> list[sqlite3.Row]:
        return list(self.db.execute("SELECT f.* FROM fills f JOIN intents i ON i.intent_id=f.intent_id WHERE i.lifecycle_id=? ORDER BY f.occurred_at", (lifecycle_id,)))

    def close(self) -> None:
        with self._lock:
            self.db.close()
