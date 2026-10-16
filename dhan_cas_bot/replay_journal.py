"""Private compressed receipt journal. No pruning, deduplication or trade writes."""
import gzip
import json
import os
import shutil
from pathlib import Path
from datetime import date
from uuid import uuid4
from zoneinfo import ZoneInfo


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
