"""Dated official NSE archive adapter. Missing publication never implies finality."""
from datetime import date, datetime, time, timezone
from decimal import Decimal
from email.utils import parsedate_to_datetime
import csv
import hashlib
import io
from zoneinfo import ZoneInfo

import httpx

from .domain import ContractError
from .settlement import FinalValue

IST = ZoneInfo("Asia/Kolkata")


class NseFinalSource:
    @staticmethod
    def parse(payload: bytes, trading_date: date, *, published_at: datetime, received_at: datetime) -> FinalValue:
        if published_at.tzinfo is None or received_at.tzinfo is None or published_at > received_at:
            raise ContractError("final publication timestamps unavailable or inconsistent")
        if published_at.astimezone(IST).date() != trading_date or published_at.astimezone(IST).time() < time(15,30):
            raise ContractError("publication precedes this session's possible final close")
        rows = csv.DictReader(io.StringIO(payload.decode("utf-8-sig")))
        found = []
        for raw in rows:
            row = {key.strip().lower():value.strip() for key,value in raw.items() if key and value is not None}
            if row.get("index name", "").upper() != "NIFTY 50":
                continue
            text_date = row.get("index date", "")
            parsed = None
            for fmt in ("%d-%m-%Y", "%d-%b-%Y", "%Y-%m-%d"):
                try: parsed = datetime.strptime(text_date,fmt).date(); break
                except ValueError: pass
            if parsed != trading_date:
                raise ContractError("official close belongs to another trading date")
            found.append(Decimal(row["closing index value"].replace(",","")))
        if len(found) != 1 or not found[0].is_finite() or found[0] <= 0:
            raise ContractError("official NIFTY close is missing or ambiguous")
        return FinalValue(trading_date.isoformat(),found[0],"NSE","closing_index_value",published_at.isoformat(),received_at.isoformat(),hashlib.sha256(payload).hexdigest(),"NSE_CAS_2026","FINAL")

    async def fetch(self, trading_date: date) -> FinalValue | None:
        url = f"https://nsearchives.nseindia.com/content/indices/ind_close_all_{trading_date:%d%m%Y}.csv"
        async with httpx.AsyncClient(timeout=3,follow_redirects=False) as client:
            response = await client.get(url)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            published = response.headers.get("last-modified")
            if not published:
                raise ContractError("NSE final archive has no publication timestamp")
            return self.parse(response.content,trading_date,published_at=parsedate_to_datetime(published),received_at=datetime.now(timezone.utc))
