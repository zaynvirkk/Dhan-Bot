from __future__ import annotations

from typing import Awaitable, Callable, Iterable
from collections import deque
from contextvars import ContextVar
from datetime import datetime, timezone
import asyncio
import json
import random
import time
import httpx

from .domain import ContractError

_ingress = ContextVar('websocket_ingress_ns', default=None)
_ingress_monotonic = ContextVar('websocket_ingress_monotonic_ns', default=None)


def message_received_ns(fallback):
    """Actual receipt time, before waiting for the decoder; injectable in tests."""
    return _ingress.get() or fallback


def message_received_monotonic_ns(fallback):
    value = _ingress_monotonic.get()
    return value if value is not None else fallback


class WebSocketRunner:
    """Bounded ordered decoding, observed health and stable-connection backoff."""

    def __init__(self, url: str | Callable[[], Awaitable[str]], headers: dict[str, str], on_message: Callable[[bytes], Awaitable[None]], *, subscribe: Iterable[dict] = (), connect_messages: Iterable[dict] = (), binary: bool = False, on_connect: Callable[[], None] | None = None, on_disconnect: Callable[[], None] | None = None):
        if not url:
            raise ContractError("websocket endpoint must be configured")
        self.url, self.headers, self.on_message = url, headers, on_message
        self.binary, self.subscribe = binary, list(subscribe)
        self.connect_messages = list(connect_messages)
        self.on_connect, self.on_disconnect = on_connect, on_disconnect
        self.stop = asyncio.Event()
        self.socket, self.last_error = None, ""
        self.clock, self.jitter = time.monotonic, random.uniform
        self.wall_clock = time.time_ns
        self.attempts = self.processed = self.high_water = 0
        self.last_received_at = self.last_processed_at = None
        self.queue_delay_ms = self.processing_ms = None
        self.pending_times = deque()
        self.disconnect_notified = False

    def disconnected(self):
        self.socket = None
        if not self.disconnect_notified:
            self.disconnect_notified = True
            if self.on_disconnect:
                self.on_disconnect()

    def snapshot(self):
        return {'connected': self.socket is not None,
                'reconnects': max(0, self.attempts-1),
                'last_received_at': self.last_received_at,
                'last_processed_at': self.last_processed_at,
                'pending_messages': len(self.pending_times), 'queue_high_water': self.high_water,
                'oldest_pending_ms': round(max(0, self.clock()-self.pending_times[0])*1000, 3) if self.pending_times else 0,
                'queue_delay_ms': self.queue_delay_ms, 'processing_ms': self.processing_ms,
                'processed_messages': self.processed, 'last_error': self.last_error}

    async def consume(self, socket):
        # The library buffer and this queue are both bounded. Backpressure never
        # coalesces strike confirmations or order events into a latest-only value.
        queue = asyncio.Queue(maxsize=64)
        async def receive():
            try:
                async for message in socket:
                    if self.stop.is_set():
                        break
                    stamp, wall = self.clock(), self.wall_clock()
                    self.last_received_at = datetime.fromtimestamp(wall/1e9, timezone.utc).isoformat()
                    self.pending_times.append(stamp)
                    self.high_water = max(self.high_water, len(self.pending_times))
                    await queue.put((message, stamp, wall))
            finally:
                # Do not wait for queued decoding to revoke connection authority.
                self.disconnected()
            await queue.put(None)

        async def process():
            while True:
                item = await queue.get()
                if item is None:
                    return
                message, stamp, wall = item
                started = self.clock()
                self.queue_delay_ms = round(max(0, started-stamp)*1000, 3)
                token = _ingress.set(wall)
                monotonic_token = _ingress_monotonic.set(int(stamp*1e9))
                try:
                    await self.on_message(message.encode() if isinstance(message, str) else message)
                    self.processed += 1
                    self.last_processed_at = datetime.fromtimestamp(self.wall_clock()/1e9, timezone.utc).isoformat()
                    self.processing_ms = round(max(0, self.clock()-started)*1000, 3)
                finally:
                    _ingress.reset(token)
                    _ingress_monotonic.reset(monotonic_token)
                    self.pending_times.popleft()
        jobs = [asyncio.create_task(receive()), asyncio.create_task(process())]
        try:
            await asyncio.gather(*jobs)
        finally:
            for job in jobs:
                job.cancel()
            await asyncio.gather(*jobs, return_exceptions=True)
            self.pending_times.clear()

    async def wait_retry(self, delay):
        try:
            await asyncio.wait_for(self.stop.wait(), timeout=delay)
        except asyncio.TimeoutError:
            pass

    async def run(self) -> None:
        from websockets.asyncio.client import connect
        from websockets.exceptions import ConnectionClosed, InvalidHandshake
        delay = 1.0
        while not self.stop.is_set():
            connected_at, initial_processed = None, self.processed
            self.disconnect_notified = False
            self.attempts += 1
            try:
                endpoint = await self.url() if callable(self.url) else self.url
                if not endpoint:
                    raise ContractError("websocket endpoint factory returned an empty URL")
                async with connect(endpoint, additional_headers=self.headers, ping_interval=10, ping_timeout=5, close_timeout=2, open_timeout=10, max_size=8 * 1024 * 1024, max_queue=16) as socket:
                    self.socket, connected_at = socket, self.clock()
                    self.last_error = ""
                    self.last_received_at = self.last_processed_at = None
                    if self.on_connect:
                        self.on_connect()
                    for message in [*self.connect_messages, *self.subscribe]:
                        encoded = json.dumps(message, separators=(",", ":"))
                        await socket.send(encoded.encode() if self.binary else encoded)
                    await self.consume(socket)
            except asyncio.CancelledError:
                raise
            except (OSError, EOFError, ConnectionClosed, InvalidHandshake, ContractError, httpx.HTTPError) as exc:
                self.last_error = type(exc).__name__
                if self.stop.is_set():
                    return
            finally:
                self.disconnected()
            if connected_at is not None and self.clock()-connected_at >= 30 and self.processed > initial_processed:
                delay = 1.0
            if not self.stop.is_set():
                await self.wait_retry(self.jitter(delay*.75, delay))
                delay = min(delay * 2, 30.0)

    def close(self) -> None:
        self.stop.set()
        if self.socket:
            asyncio.create_task(self.socket.close())
