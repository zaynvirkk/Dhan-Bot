from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
import csv
import hashlib
import httpx

from .domain import ContractError, Instrument, RuleSnapshot
from .instruments import load_dhan_master, parse_date, is_nifty_option


DHAN_MASTER_URL = "https://images.dhan.co/api-data/api-scrip-master-detailed.csv"
NSE_FREEZE_URL = "https://nsearchives.nseindia.com/content/fo/qtyfreeze.csv"


@dataclass(frozen=True)
class SourceRecord:
    url: str
    digest: str
    retrieved_at: datetime
    effective_from: date
    payload: bytes


class RuleSource:
    def __init__(self, *, timeout: float = 5.0):
        self.timeout = timeout

    async def fetch(self, url: str) -> SourceRecord:
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            response = await client.get(url, headers={"User-Agent": "sablestone-dhan-cas/0.1"})
            response.raise_for_status()
            payload = response.content
        return SourceRecord(url, hashlib.sha256(payload).hexdigest(), datetime.now(timezone.utc), datetime.now(timezone.utc).date(), payload)

    @staticmethod
    def parse_freeze(payload: bytes, *, underlying: str = "NIFTY") -> dict[str, int]:
        text = payload.decode("utf-8-sig")
        reader = csv.DictReader(text.splitlines())
        fields = {str(x).strip().upper() for x in (reader.fieldnames or [])}
        symbol_field = next((x for x in ("SYMBOL", "INDEX SYMBOL", "UNDERLYING") if x in fields), None)
        quantity_field = next((x for x in ("QUANTITY", "FREEZE_QTY", "QUANTITY FREEZE LIMIT", "FREEZE QUANTITY") if x in fields), None)
        if not symbol_field or not quantity_field:
            raise ContractError("NSE freeze source has no recognized fields")
        output = {}
        for row in reader:
            normalized = {str(k).strip().upper(): v for k, v in row.items()}
            if str(normalized.get(symbol_field, "")).strip().upper() == underlying.upper():
                output[underlying.upper()] = int(normalized[quantity_field])
        if not output:
            raise ContractError("NSE freeze source has no NIFTY row")
        return output

    @staticmethod
    def build_snapshot(record: SourceRecord, *, lot_size: int, tick_size: Decimal, freeze_qty: int) -> RuleSnapshot:
        return RuleSnapshot(record.url, record.digest, record.retrieved_at, record.effective_from, None, lot_size, tick_size, freeze_qty)

    @staticmethod
    def current_expiry(payload: bytes, *, today: date) -> date:
        text = payload.decode("utf-8-sig")
        reader = csv.DictReader(text.splitlines())
        expiries = []
        for row in reader:
            if is_nifty_option(row):
                try:
                    value = parse_date(str(row["SM_EXPIRY_DATE"]))
                except ContractError:
                    continue
                if value >= today:
                    expiries.append(value)
        if not expiries:
            raise ContractError("Dhan master has no current/future NIFTY expiry")
        return min(expiries)
