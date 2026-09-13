from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
import os

from .domain import ContractError, FundsSnapshot


class DhanBroker:
    """Small raw HTTP adapter; never writes unless the service authorizes it."""

    def __init__(self, account_id: str, access_token: str, base_url: str = "https://api.dhan.co/v2", *, allow_writes: bool = False):
        self.account_id = account_id
        self.access_token = access_token
        self.base_url = base_url.rstrip("/")
        self.allow_writes = allow_writes and os.environ.get("DHAN_BROKER_READ_ONLY", "").lower() not in {"1", "true"}

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        import httpx
        headers = {"access-token": self.access_token, "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.request(method, self.base_url + path, headers=headers, **kwargs)
            response.raise_for_status()
            return response.json()

    async def submit_order(self, request: dict[str, Any]) -> dict[str, Any]:
        if not self.allow_writes:
            raise ContractError("Dhan writes are disabled")
        if request.get("dhanClientId") != self.account_id:
            raise ContractError("order account mismatch")
        return await self._request("POST", "/orders", json=request)

    async def order(self, order_id: str) -> dict[str, Any] | None:
        return await self._request("GET", f"/orders/{order_id}")

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

    async def funds(self) -> FundsSnapshot:
        value = await self._request("GET", "/fundlimit")
        return FundsSnapshot(datetime.now(timezone.utc), Decimal(str(value.get("availabelBalance", value.get("availableBalance", "0")))), Decimal(str(value.get("availabelBalance", value.get("availableBalance", "0")))), Decimal(str(value.get("withdrawableBalance", "0"))), Decimal(str(value.get("collateralAmount", "0"))), self.account_id)
