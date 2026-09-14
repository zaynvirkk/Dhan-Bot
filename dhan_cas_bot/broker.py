from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
import os
import asyncio
import json
import time

from .domain import ContractError, FundsSnapshot


class DhanBroker:
    """Small raw HTTP adapter; never writes unless the service authorizes it."""

    def __init__(self, account_id: str, access_token: str, base_url: str = "https://api.dhan.co/v2", *, allow_writes: bool = False):
        self.account_id = account_id
        self.access_token = access_token
        self.base_url = base_url.rstrip("/")
        self.allow_writes = allow_writes and os.environ.get("DHAN_BROKER_READ_ONLY", "").lower() not in {"1", "true"}
        self.client = None
        self.read_lock = asyncio.Lock()
        self.last_read = 0.0

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        import httpx
        headers = {"access-token": self.access_token, "Content-Type": "application/json"}
        if self.client is None:
            self.client = httpx.AsyncClient(timeout=httpx.Timeout(5.0, connect=3.0), follow_redirects=False)
        if method == "GET":
            async with self.read_lock:
                await asyncio.sleep(max(0, .11 - (time.monotonic() - self.last_read)))
                self.last_read = time.monotonic()
        if "json" in kwargs:
            value = kwargs.pop("json")
            # Dhan expects a JSON number for price; emit the exact decimal
            # directly instead of converting money through binary float.
            kwargs["content"] = "{" + ",".join(json.dumps(key)+":"+(format(Decimal(item), "f") if key == "price" else json.dumps(item)) for key,item in value.items()) + "}"
        response = await self.client.request(method, self.base_url + path, headers=headers, **kwargs)
        response.raise_for_status()
        return json.loads(response.text, parse_float=Decimal)

    async def close(self):
        if self.client:
            await self.client.aclose()
            self.client = None

    async def submit_order(self, request: dict[str, Any]) -> dict[str, Any]:
        if not self.allow_writes:
            raise ContractError("Dhan writes are disabled")
        if request.get("dhanClientId") != self.account_id:
            raise ContractError("order account mismatch")
        return await self._request("POST", "/orders", json=request)

    async def order(self, order_id: str) -> dict[str, Any] | None:
        return await self._request("GET", f"/orders/{order_id}")

    async def order_by_correlation(self, correlation: str):
        import httpx
        try:
            result = await self._request("GET", f"/orders/external/{correlation}")
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return None
            raise
        if not isinstance(result, dict) or not result.get("orderId"):
            raise ContractError("correlation lookup returned no order identity")
        return result

    async def historical_trades(self, from_date, to_date):
        key = (str(from_date), str(to_date))
        cached = getattr(self, "_historical_cache", {})
        if key in cached and time.monotonic() - cached[key][0] < 300:
            return cached[key][1]
        result = []
        for page in range(100):
            rows = await self._request("GET", f"/trades/{from_date}/{to_date}/{page}")
            if not isinstance(rows, list):
                raise ContractError("historical trades response is not a list")
            if not rows:
                cached[key] = (time.monotonic(), result)
                self._historical_cache = cached
                return result
            result.extend(rows)
        raise ContractError("historical trade pagination did not terminate")

    async def orders(self) -> list[dict[str, Any]]:
        value = await self._request("GET", "/orders")
        if not isinstance(value, list):
            raise ContractError("Dhan orders response is not a list")
        return value

    async def trades(self) -> list[dict[str, Any]]:
        value = await self._request("GET", "/trades")
        if not isinstance(value, list):
            raise ContractError("Dhan trades response is not a list")
        return value

    async def positions(self) -> list[dict[str, Any]]:
        value = await self._request("GET", "/positions")
        if not isinstance(value, list):
            raise ContractError("Dhan positions response is not a list")
        return value

    async def ledger_report(self, from_date, to_date):
        value = await self._request("GET", "/ledger", params={"from-date":str(from_date),"to-date":str(to_date)})
        if isinstance(value,dict) and "vouchernumber" in value:
            value=[value]
        if not isinstance(value,list):
            raise ContractError("broker ledger is not an account transaction list")
        return value

    async def funds(self) -> FundsSnapshot:
        value = await self._request("GET", "/fundlimit")
        if not isinstance(value, dict) or not ({"availabelBalance", "availableBalance"} & value.keys()):
            raise ContractError("funds response has no available balance")
        cash = Decimal(str(value.get("availabelBalance", value.get("availableBalance"))))
        if "dhanClientId" in value and str(value["dhanClientId"]) != self.account_id:
            raise ContractError("funds account mismatch")
        return FundsSnapshot(datetime.now(timezone.utc), cash, cash, Decimal(str(value.get("withdrawableBalance", "0"))), Decimal(str(value.get("collateralAmount", "0"))), self.account_id)
