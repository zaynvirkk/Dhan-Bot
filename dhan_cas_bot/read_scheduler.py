"""Process-local, account-wide REST admission; requests in flight are never retried."""
import asyncio
from contextlib import contextmanager
from contextvars import ContextVar
import heapq
import itertools
import time
import weakref

_priority = ContextVar('broker_read_priority', default=0)
_accounts = weakref.WeakKeyDictionary()


@contextmanager
def read_priority(value):
    token = _priority.set(value)
    try:
        yield
    finally:
        _priority.reset(token)


class ReadScheduler:
    """Prioritize execution (0), reconciliation (2), then monitoring (10).

    Spacing applies across clients for an account in this event loop. It doesn't
    coordinate other processes or cancel an already dispatched HTTP request.
    """
    def __init__(self, interval=.11):
        self.interval, self.last = interval, -float('inf')
        self.waiters, self.sequence = [], itertools.count()
        self.worker = None

    async def acquire(self):
        future = asyncio.get_running_loop().create_future()
        heapq.heappush(self.waiters, (_priority.get(), next(self.sequence), future))
        if self.worker is None:
            self.worker = asyncio.create_task(self._drain())
        try:
            await future
        finally:
            if not future.done():
                future.cancel()

    async def _drain(self):
        try:
            while self.waiters:
                await asyncio.sleep(max(0, self.interval-(time.monotonic()-self.last)))
                while self.waiters:
                    _, _, future = heapq.heappop(self.waiters)
                    if not future.done():
                        self.last = time.monotonic()
                        future.set_result(None)
                        break
        finally:
            self.worker = None


def account_reads(account, base_url):
    clients = _accounts.setdefault(asyncio.get_running_loop(), {})
    return clients.setdefault((account, base_url), ReadScheduler())
