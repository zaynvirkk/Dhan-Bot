from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable
import json

from .domain import ContractError


@dataclass
class FeedEpoch:
    name: str
    number: int = 0
    connected: bool = False
    seen: set[str] = field(default_factory=set)

    def reconnect(self) -> None:
        self.number += 1
        self.connected = True
        self.seen.clear()

    def disconnect(self) -> None:
        self.connected = False
        self.seen.clear()

    @property
    def id(self) -> str:
        return f"{self.name}:{self.number}"

    def accept(self, identity: str) -> bool:
        if not self.connected or not identity or identity in self.seen:
            return False
        self.seen.add(identity)
        return True


def chunked(values: Iterable[str], size: int = 100) -> list[list[str]]:
    if size <= 0:
        raise ContractError("subscription batch size must be positive")
    values = list(dict.fromkeys(values))
    return [values[i:i + size] for i in range(0, len(values), size)]


def upstox_subscription(keys: Iterable[str]) -> list[dict[str, Any]]:
    return [{"guid": "sablestone-cas", "method": "sub", "data": {"mode": "full", "instrumentKeys": batch}} for batch in chunked(keys, 100)]


def dhan_subscription(security_ids: Iterable[str]) -> list[dict[str, Any]]:
    return [{"RequestCode": 21, "InstrumentCount": len(batch), "InstrumentList": [{"ExchangeSegment": "NSE_FNO", "SecurityId": sid} for sid in batch]} for batch in chunked(security_ids, 100)]


class SocketProtocol:
    """Transport-independent protocol state used by both real and replay feeds."""

    def __init__(self, name: str):
        self.epoch = FeedEpoch(name)

    def on_connect(self) -> str:
        self.epoch.reconnect()
        return self.epoch.id

    def on_disconnect(self) -> None:
        self.epoch.disconnect()

    def accept(self, identity: str) -> bool:
        return self.epoch.accept(identity)


class UpstoxFeedClient:
    def __init__(self, token: str):
        if not token:
            raise ContractError("Upstox analytics token is required")
        self.token = token
        self.protocol = SocketProtocol("upstox")

    async def connect(self) -> str:
        return self.protocol.on_connect()

    def subscription_messages(self, keys: Iterable[str]) -> list[dict[str, Any]]:
        return upstox_subscription(keys)


class DhanMarketClient:
    def __init__(self, access_token: str):
        if not access_token:
            raise ContractError("Dhan access token is required")
        self.access_token = access_token
        self.protocol = SocketProtocol("dhan-market")

    async def connect(self) -> str:
        return self.protocol.on_connect()

    def subscription_messages(self, security_ids: Iterable[str]) -> list[dict[str, Any]]:
        return dhan_subscription(security_ids)


class DhanOrderUpdateClient:
    def __init__(self, access_token: str):
        if not access_token:
            raise ContractError("Dhan access token is required")
        self.access_token = access_token
        self.protocol = SocketProtocol("dhan-orders")

    async def connect(self) -> str:
        return self.protocol.on_connect()

    def accept_order_event(self, account_id: str, expected_account: str, identity: str) -> bool:
        if account_id != expected_account:
            raise ContractError("foreign-account order event")
        return self.protocol.accept(identity)
