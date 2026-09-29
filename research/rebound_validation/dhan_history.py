"""Reconstruct a fixed option only from explicitly matching rolling strikes.

Expiry code is mapped using the prior published exchange contract calendar.
Returned strike and timestamp must match; uncovered history remains missing.
"""
import asyncio
import hashlib
import json
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP
from functools import lru_cache
from zoneinfo import ZoneInfo

import httpx

from dhan_cas_bot.auth import resolve_dhan_access_token
from research.gauntlet.core import Bar, D
from research.gauntlet.data import CACHE, save
from research.multifeature.providers import environment
from .data import STORE, calendar, exchange

ACCESS = None
RATE_LOCK = threading.Lock()
NEXT_REQUEST = 0.0


def access():
    global ACCESS
    if ACCESS is None:
        env = environment()
        for attempt in range(2):
            try:
                ACCESS = asyncio.run(resolve_dhan_access_token(env['DHAN_CLIENT_ID'], pin=env['DHAN_PIN'],
                                                                totp_secret=env['DHAN_TOTP_SECRET']))
                break
            except Exception:
                if attempt:
                    raise RuntimeError('AUTHENTICATION_FAILED_IDENTITY_GUARD') from None
                time.sleep(1)
    return ACCESS


def rolling(day, code, offset, side, network):
    global NEXT_REQUEST
    body = {'exchangeSegment': 'NSE_FNO', 'interval': '1', 'securityId': '13', 'instrument': 'OPTIDX',
            'expiryFlag': 'WEEK', 'expiryCode': code, 'strike': 'ATM' if not offset else f'ATM{offset:+d}',
            'drvOptionType': 'CALL' if side == 'CE' else 'PUT',
            'requiredData': ['open', 'high', 'low', 'close', 'volume', 'oi', 'strike', 'spot'],
            'fromDate': day, 'toDate': (date.fromisoformat(day)+timedelta(days=1)).isoformat()}
    name = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()+'.json'
    p = STORE / 'dhan_raw' / name
    old = CACHE / 'broader/dhan_selected' / name
    for cached in (p, old):
        if cached.exists():
            x = json.loads(cached.read_text())
            if x.get('status') == 200 and isinstance(x.get('body', {}).get('data'), dict):
                return x, cached
    if not network:
        raise ValueError('MISSING_DHAN_ROLLING_SOURCE')
    env = environment()
    token = access()
    for attempt in range(3):
        try:
            with RATE_LOCK:
                wait = max(0., NEXT_REQUEST-time.monotonic())
                NEXT_REQUEST = max(NEXT_REQUEST, time.monotonic())+.4
            if wait:
                time.sleep(wait)
            r = httpx.post('https://api.dhan.co/v2/charts/rollingoption',
                           headers={'access-token': token, 'client-id': env['DHAN_CLIENT_ID']},
                           json=body, timeout=30)
            x = {'request': body, 'status': r.status_code, 'body': r.json(),
                 'retrieved_at': datetime.now(timezone.utc).isoformat(), 'sha256': hashlib.sha256(r.content).hexdigest()}
            save(p, x)
            time.sleep(.28)
            if r.status_code not in (429, 500, 502, 503, 504):
                return x, p
        except (httpx.HTTPError, ValueError):
            if attempt == 2:
                raise ValueError('DHAN_HISTORY_TRANSPORT_FAILURE') from None
        time.sleep(2**attempt)
    return x, p


def matching_rows(raw, strike):
    fields = ('timestamp', 'strike', 'open', 'high', 'low', 'close', 'volume', 'oi')
    n = len(raw.get('timestamp', []))
    if any(len(raw.get(f, [])) != n for f in fields):
        raise ValueError('DHAN_PARALLEL_ARRAY_LENGTH')
    out = []
    for i, t in enumerate(raw['timestamp']):
        if D(str(raw['strike'][i])) != strike:
            continue
        at = datetime.fromtimestamp(t, ZoneInfo('Asia/Kolkata')).isoformat()
        out.append([at] + [raw[f][i] for f in ('open', 'high', 'low', 'close', 'volume', 'oi')])
    return out


@lru_cache(maxsize=1)
def spot():
    return json.loads((STORE / 'spot.json').read_text())


def fixed_contract(c, day, network=True):
    p = STORE / 'dhan_fixed' / (hashlib.sha256((c.key+' '+day).encode()).hexdigest()+'.json')
    if p.exists():
        x = json.loads(p.read_text())
        if x['key'] != c.key or x['day'] != day or x['expiry'] != c.expiry:
            raise ValueError('DHAN_FIXED_IDENTITY_MISMATCH')
        if x.get('format_version') == 2:
            return [Bar.parse(r) for r in x['bars']], p
        save(p.with_suffix('.unfiltered.json'), x)
    days = calendar()
    prior = days[days.index(day)-1]
    expiries = sorted({r.get('FininstrmActlXpryDt') or r['XpryDt'] for r in exchange(prior)
                       if r['TckrSymb'] == 'NIFTY' and r['FinInstrmTp'] == 'IDO'
                       and (r.get('FininstrmActlXpryDt') or r['XpryDt']) >= day})
    if c.expiry not in expiries:
        raise ValueError('UNKNOWN_DHAN_EXPIRY_MAPPING')
    code = expiries.index(c.expiry)+1
    # Near-expiry index supports +/-10; other expiries only +/-3.
    bound = 10 if code == 1 else 3
    implied = []
    for r in spot():
        if r[0][:10] == day:
            atm = (D(str(r[4]))/50).quantize(D(1), rounding=ROUND_HALF_UP)*50
            implied.append(int((c.strike-atm)/50))
    if not implied:
        raise ValueError('MISSING_SPOT_FOR_DHAN_RECONSTRUCTION')
    # One-strike padding handles differing source ATM rounding; actual strike
    # identity decides membership. Future spot is used for DOWNLOAD only.
    offsets = range(max(-bound, min(implied)-1), min(bound, max(implied)+1)+1)
    by = {}
    receipts = {}
    errors = []
    outside = set()
    if network:
        access()  # Single authentication before concurrent read-only data calls.
    def fetch(k):
        return k, rolling(day, code, k, c.side, network)
    with ThreadPoolExecutor(max_workers=3) as pool:
        fetched = list(pool.map(fetch, offsets))
    for k, (x, path) in fetched:
        receipts[str(path.relative_to(CACHE))] = hashlib.sha256(path.read_bytes()).hexdigest()
        if x['status'] != 200:
            errors.append({'offset': k, 'http_status': x['status']})
            continue
        raw = x.get('body', {}).get('data', {}).get(c.side.lower()) or {}
        for row in matching_rows(raw, c.strike) if raw else []:
            Bar.parse(row)
            if row[0][:10] != day:
                outside.add(row[0])
                continue
            if row[0] in by and by[row[0]] != row:
                raise ValueError('CONFLICTING_DHAN_FIXED_OBSERVATION')
            by[row[0]] = row
    x = {'format_version': 2, 'key': c.key, 'day': day, 'expiry': c.expiry, 'expiry_code': code, 'strike': str(c.strike),
         'bars': sorted(by.values()), 'raw_hashes': receipts, 'request_failures': errors,
         'offset_bounds': [-bound, bound], 'outside_requested_day': sorted(outside), 'missing_minutes_are_unknown': True}
    save(p, x)
    print('Dhan fixed', day, c.expiry, c.strike, c.side, 'rows', len(by), flush=True)
    return [Bar.parse(r) for r in x['bars']], p
