"""Small durable daily health receipts, separate from the short UI history ring."""
import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .data import STATES, STRATEGY_NAMES, choice, feed_health_view, timestamp, freshness


def append_session_audit(output, report, now, *, max_bytes=16*1024*1024):
    """Read-side only; fail visibly without erasing evidence or stopping updates."""
    root=Path(output).parent
    day=now.astimezone(ZoneInfo('Asia/Kolkata')).date().isoformat()
    path=root/('session-audit-'+day+'.jsonl')
    rt=report.get('runtime') if isinstance(report.get('runtime'),dict) else {}
    funded=rt.get('funded_strategies') if isinstance(rt.get('funded_strategies'),list) else []
    release=report.get('release') if isinstance(report.get('release'),dict) else {}
    feeds=feed_health_view(rt.get('feed_health'))
    sample={'at':now.isoformat(),'source_current':rt.get('fresh') is True and freshness(rt.get('observed_at'),now,45)['fresh'],
            'state':choice(rt.get('state'),STATES,'UNKNOWN'),
            'authority':choice(rt.get('authority'),{'ENABLED','DISABLED'},'UNKNOWN'),
            'funded_strategies':[n for n in funded if isinstance(n,str) and n in STRATEGY_NAMES],
            'feeds':{name:{k:r.get(k) for k in ('connected','reconnects','last_error','transport_events')}
                     for name,r in feeds.items()}}
    for key in ('broker_route_verified','account_snapshot_fresh'):
        sample[key]=rt.get(key) if type(rt.get(key)) is bool else None
    for key in ('funded_source','dashboard_source'):
        value=release.get(key)
        sample[key]=value if isinstance(value,str) and len(value)==40 and all(c in '0123456789abcdef' for c in value) else None
    try:
        root.mkdir(parents=True,exist_ok=True)
        if path.is_symlink():return 'UNAVAILABLE'
        if path.exists():
            with path.open('rb') as stream:
                stream.seek(max(0,path.stat().st_size-65536))
                tail=stream.read().splitlines()
            previous=json.loads(tail[-1])
            before=datetime.fromisoformat(previous['at'])
            if before>=now:return 'AVAILABLE' if before==now else 'UNAVAILABLE'
            comparable=lambda r:{k:v for k,v in r.items() if k!='at'}
            if comparable(previous)==comparable(sample) and (now-before).total_seconds()<60:return 'AVAILABLE'
        data=(json.dumps(sample,sort_keys=True,separators=(',',':'))+'\n').encode()
        if len(data)>65536 or (path.stat().st_size if path.exists() else 0)+len(data)>max_bytes:return 'CAP_REACHED'
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_APPEND|os.O_NOFOLLOW,0o640)
        with os.fdopen(fd,'ab') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
        # Only this module's own date-shaped files; never private state files.
        for old in root.glob('session-audit-????-??-??.jsonl'):
            try:
                date=datetime.strptime(old.name[14:-6],'%Y-%m-%d').date()
                if not old.is_symlink() and (now.astimezone(ZoneInfo('Asia/Kolkata')).date()-date).days>=7:old.unlink()
            except ValueError:continue
        return 'AVAILABLE'
    except (OSError,ValueError,TypeError,KeyError,IndexError):return 'UNAVAILABLE'
