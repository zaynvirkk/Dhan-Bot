from __future__ import annotations

from typing import Awaitable, Callable, Iterable
import asyncio
import json
import httpx

from .domain import ContractError


class WebSocketRunner:
    """Reconnect loop for a configured endpoint; parsing remains in adapters."""

    def __init__(self, url: str | Callable[[], Awaitable[str]], headers: dict[str, str], on_message: Callable[[bytes], Awaitable[None]], *, subscribe: Iterable[dict] = (), connect_messages: Iterable[dict] = (), binary: bool = False, on_connect: Callable[[], None] | None = None, on_disconnect: Callable[[], None] | None = None):
        if not url:
            raise ContractError("websocket endpoint must be configured")
        self.url = url
        self.headers = headers
        self.on_message = on_message
        self.binary = binary
        self.subscribe = list(subscribe)
        self.connect_messages = list(connect_messages)
        self.on_connect = on_connect
        self.on_disconnect = on_disconnect
        self.stop = asyncio.Event()
        self.socket = None
        self.last_error = ""

    async def run(self) -> None:
        from websockets.asyncio.client import connect
        from websockets.exceptions import ConnectionClosed
        delay = 1.0
        while not self.stop.is_set():
            try:
                endpoint = await self.url() if callable(self.url) else self.url
                if not endpoint:
                    raise ContractError("websocket endpoint factory returned an empty URL")
                async with connect(endpoint, additional_headers=self.headers, ping_interval=10, ping_timeout=5, close_timeout=2, open_timeout=10, max_size=8 * 1024 * 1024) as socket:
                    self.socket = socket
                    delay = 1.0
                    if self.on_connect:
                        self.on_connect()
                    for message in self.connect_messages:
                        encoded = json.dumps(message, separators=(",", ":"))
                        await socket.send(encoded.encode() if self.binary else encoded)
                    for message in self.subscribe:
                        encoded = json.dumps(message, separators=(",", ":"))
                        await socket.send(encoded.encode() if self.binary else encoded)
                    async for message in socket:
                        if self.stop.is_set():
                            break
                        if isinstance(message, str):
                            message = message.encode()
                        await self.on_message(message)
            except asyncio.CancelledError:
                raise
            except (OSError, ConnectionClosed, ContractError, httpx.HTTPError) as exc:
                self.last_error = type(exc).__name__
                if self.stop.is_set():
                    return
            finally:
                self.socket = None
                if self.on_disconnect:
                    self.on_disconnect()
            if not self.stop.is_set():
                try:
                    await asyncio.wait_for(self.stop.wait(), timeout=delay)
                except asyncio.TimeoutError:
                    pass
                delay = min(delay * 2, 30.0)

    def close(self) -> None:
        self.stop.set()
        if self.socket:
            asyncio.create_task(self.socket.close())
