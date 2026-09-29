"""Resumable, read-only source collection. Raw licensed data stays private."""
from __future__ import annotations
import gzip
import fcntl
import hashlib
import json
import os
import shlex
import threading
import time
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
import httpx

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / 'artifacts/private/gauntlet'
LOCK = threading.Lock()
NEXT = 0.0

def token():
    value = os.environ.get('UPSTOX_ANALYTICS_TOKEN')
    if value:
        return value
    for line in (ROOT / '.env').read_text().splitlines():
        fields = shlex.split(line, comments=True)
        if fields and fields[0].startswith('UPSTOX_ANALYTICS_TOKEN='):
            return fields[0].partition('=')[2]
    raise RuntimeError('UPSTOX_ANALYTICS_TOKEN missing')

def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w',dir=path.parent,delete=False) as handle:
        handle.write(json.dumps(data, separators=(',', ':')))
        tmp=Path(handle.name)
    tmp.replace(path)

def upstox(path):
    global NEXT
    # Explicit market-data endpoint allowlist: never route orders/account writes.
    if not path.startswith(('/v2/expired-instruments/', '/v3/historical-candle/', '/v2/option/contract')):
        raise ValueError('non-research endpoint')
    key = hashlib.sha256(path.encode()).hexdigest()
    file = CACHE / 'upstox' / (key + '.json')
    if file.exists():
        stored = json.loads(file.read_text())
        if stored.get('status') == 200 and stored.get('body', {}).get('status') == 'success':
            return stored['body']['data']
    for attempt in range(3):
        with LOCK:
            CACHE.mkdir(parents=True,exist_ok=True)
            with (CACHE/'rate_limit').open('a+') as rate:
                fcntl.flock(rate,fcntl.LOCK_EX)
                rate.seek(0)
                prior=float(rate.read() or '0')
                delay=max(0.,prior-time.time())
                rate.seek(0);rate.truncate();rate.write(str(max(prior,time.time())+1.05));rate.flush()
                fcntl.flock(rate,fcntl.LOCK_UN)
        if delay:
            time.sleep(delay)
        started = time.monotonic()
        try:
            response = httpx.get('https://api.upstox.com' + path, timeout=45,
                                 headers={'Authorization': 'Bearer ' + token(), 'Accept':'application/json'})
            body = response.json()
            receipt = {'path':path, 'retrieved_at':datetime.now(timezone.utc).isoformat(),
                       'elapsed_ms':round((time.monotonic()-started)*1000),
                       'status':response.status_code, 'body':body,
                       'sha256':hashlib.sha256(response.content).hexdigest()}
            save(file, receipt)
            if response.status_code == 200 and body.get('status') == 'success':
                return body['data']
            if response.status_code not in (429, 500, 502, 503, 504):
                raise RuntimeError('Upstox HTTP ' + str(response.status_code) + ' ' + str([e.get('errorCode') for e in body.get('errors', [])]))
        except (httpx.HTTPError, json.JSONDecodeError):
            if attempt == 2:
                raise RuntimeError('Upstox transport/JSON failure') from None
        time.sleep(2 ** (attempt + 1))
    raise RuntimeError('Upstox unavailable after bounded retries')

def candles(key, start, end, expired=False):
    encoded = quote(key, safe='')
    path = (f'/v2/expired-instruments/historical-candle/{encoded}/1minute/{end}/{start}' if expired
            else f'/v3/historical-candle/{encoded}/minutes/1/{end}/{start}')
    return upstox(path)['candles']

def contracts(key, expiry):
    return upstox('/v2/expired-instruments/option/contract?instrument_key=' + quote(key, safe='') + '&expiry_date=' + expiry)

def public(url, name):
    file = CACHE / 'public' / name
    if file.exists():
        return file.read_bytes()
    response = httpx.get(url, timeout=60, follow_redirects=True,
                         headers={'User-Agent':'Mozilla/5.0', 'Accept':'*/*'})
    if response.status_code != 200:
        save(file.with_suffix('.error.json'), {'url':url, 'status':response.status_code})
        raise RuntimeError(f'HTTP {response.status_code}')
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_bytes(response.content)
    save(file.with_suffix(file.suffix+'.receipt.json'), {'url':url, 'status':200,
         'retrieved_at':datetime.now(timezone.utc).isoformat(),
         'sha256':hashlib.sha256(response.content).hexdigest()})
    return response.content
