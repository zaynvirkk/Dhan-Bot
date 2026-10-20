"""Private compressed receipt journal. No pruning, deduplication or trade writes."""
import gzip
import asyncio
import json
import os
import shutil
from pathlib import Path
from datetime import date, time
from uuid import uuid4
from zoneinfo import ZoneInfo


def capture_market(now, *, has_directional, has_position):
    """CAS-only flat capture matches the existing reference/recovery window.

    Minute/seconds engines still retain their bootstrap and pre-open history.
    This only scopes raw recording; it never gates account/position management.
    """
    if now.tzinfo is None:
        raise ValueError('capture clock must be timezone aware')
    return (has_directional or has_position
            or time(15,5) <= now.astimezone(ZoneInfo('Asia/Kolkata')).time() <= time(15,45))


async def queued_capture_batch(queue, *, maximum_rows=256, maximum_wait=.020):
    """Coalesce sparse arrivals without changing their original receipt clocks."""
    if maximum_rows <= 0 or not 0 < maximum_wait <= 1:
        raise ValueError('invalid bounded capture batch')
    rows = [await queue.get()]
    loop = asyncio.get_running_loop()
    deadline = loop.time()+maximum_wait
    while len(rows) < maximum_rows:
        try:
            rows.append(queue.get_nowait())
        except asyncio.QueueEmpty:
            remaining = deadline-loop.time()
            if remaining <= 0:
                break
            try:
                rows.append(await asyncio.wait_for(queue.get(),remaining))
            except asyncio.TimeoutError:
                break
    return rows


def read_capture(path):
    with gzip.open(path, 'rt') as stream:
        for line in stream:
            yield json.loads(line)


class ReplayJournal:
    def __init__(self, root, *, daily_cap=512*1024*1024, minimum_free=1024*1024*1024):
        self.root = Path(root)
        self.daily_cap, self.minimum_free = daily_cap, minimum_free
        self.sequence = 0
        self.capture_id = uuid4().hex
        self.health = {'state': 'WAITING', 'receipts': 0, 'compressed_bytes': 0}

    def write(self, rows, now):
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        day = now.astimezone(ZoneInfo('Asia/Kolkata')).date().isoformat()
        path = self.root / ('replay-'+day+'.jsonl.gz')
        if path.is_symlink():
            raise OSError('unsafe replay path')
        before = path.stat().st_size if path.exists() else 0
        encoded = []
        for row in rows:
            self.sequence += 1
            encoded.append(json.dumps({**row, 'capture_id':self.capture_id, 'sequence': self.sequence}, separators=(',', ':'))+'\n')
        payload = gzip.compress(''.join(encoded).encode(), compresslevel=3, mtime=0)
        if before+len(payload)>self.daily_cap:
            self.health.update(state='CAP_REACHED', date=day, compressed_bytes=before)
            raise OSError('replay daily cap reached')
        if shutil.disk_usage(self.root).free-len(payload)<self.minimum_free:
            self.health.update(state='DISK_RESERVE', date=day, compressed_bytes=before)
            raise OSError('replay disk reserve')
        fd = os.open(path, os.O_WRONLY|os.O_CREAT|os.O_APPEND|os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'ab') as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        self.health.update(state='RECORDING', date=day,
            receipts=self.health['receipts']+len(rows), compressed_bytes=before+len(payload),
            observed_at=now.isoformat())

    def retain_recent(self, now, days=14):
        """Only this new journal's dated raw files; outcome memory is never pruned."""
        today=now.astimezone(ZoneInfo('Asia/Kolkata')).date()
        for path in self.root.glob('replay-????-??-??.jsonl.gz'):
            if path.is_symlink():continue
            try:old=date.fromisoformat(path.name[7:17])
            except ValueError:continue
            if (today-old).days>=days:path.unlink()
