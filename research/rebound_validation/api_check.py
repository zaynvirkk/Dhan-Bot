"""Fresh narrow read-only broker checks; no trading routes or account writes."""
import hashlib
import json
import time
from datetime import datetime, timezone

import httpx

from dhan_cas_bot.profile import require_derivatives_profile
from research.gauntlet.data import token, save
from research.multifeature.providers import environment
from .data import OUT
from .dhan_history import access

ALLOWED = {'GET': {'/v2/profile', '/v2/fundlimit', '/v2/positions', '/v2/orders', '/v2/trades', '/v2/ip/getIP'},
           'POST': {'/v2/optionchain/expirylist', '/v2/optionchain', '/v2/marketfeed/quote'}}


def main():
    out = {'checked_at': datetime.now(timezone.utc).isoformat(), 'orders_submitted': 0,
           'market_hours_execution_evidence': False, 'requests': []}
    env = environment()
    try:
        key = access()
        headers = {'access-token': key, 'client-id': env['DHAN_CLIENT_ID']}

        def request(method, path, payload=None):
            if path not in ALLOWED.get(method, set()):
                raise ValueError('READ_ONLY_ALLOWLIST')
            start = time.monotonic()
            r = httpx.request(method, 'https://api.dhan.co'+path, headers=headers, json=payload, timeout=20)
            try:
                x = r.json()
            except ValueError:
                x = {}
            receipt = {'path': path, 'http_status': r.status_code, 'elapsed_ms': round((time.monotonic()-start)*1000),
                       'sha256': hashlib.sha256(r.content).hexdigest()}
            if r.status_code != 200:
                receipt['error_code'] = x.get('errorCode') if isinstance(x, dict) else None
            out['requests'].append(receipt)
            if r.status_code != 200:
                raise ValueError('BROKER_READ_FAILED')
            time.sleep(1.1)
            return x

        profile = request('GET', '/v2/profile')
        require_derivatives_profile(profile, env['DHAN_CLIENT_ID'])
        out['profile'] = {'identity_matches': True, 'active_segments': profile.get('activeSegment'), 'data_plan': profile.get('dataPlan')}
        funds = request('GET', '/v2/fundlimit')
        out['available_balance'] = funds.get('availabelBalance', funds.get('availableBalance'))
        for field in ('positions', 'orders', 'trades'):
            value = request('GET', '/v2/'+field)
            if not isinstance(value, list):
                raise ValueError('ACCOUNT_COLLECTION_SHAPE')
            out[field+'_count'] = len(value)
        ip = request('GET', '/v2/ip/getIP')
        out['vm_ip_in_whitelist'] = '34.100.255.111' in json.dumps(ip)
        expiry = request('POST', '/v2/optionchain/expirylist', {'UnderlyingScrip': 13, 'UnderlyingSeg': 'IDX_I'})
        out['available_expiries'] = expiry.get('data', [])
        eligible = [d for d in out['available_expiries'] if d > '2026-09-29']
        if eligible:
            exp = min(eligible)
            chain = request('POST', '/v2/optionchain', {'UnderlyingScrip': 13, 'UnderlyingSeg': 'IDX_I', 'Expiry': exp})
            data = chain.get('data', {})
            out['chain'] = {'expiry': exp, 'spot': data.get('last_price'), 'strikes': len(data.get('oc', {})),
                            'closed_market_snapshot': True, 'fillable': 'UNKNOWN'}
        out['dhan_status'] = 'READS_SUCCEEDED'
    except Exception as e:
        out['dhan_status'] = 'UNKNOWN'
        out['error_type'] = type(e).__name__
    try:
        r = httpx.get('https://api.upstox.com/v2/market/status/NSE', headers={'Authorization': 'Bearer '+token()}, timeout=20)
        x = r.json()
        out['upstox'] = {'http_status': r.status_code, 'response_status': x.get('status'), 'market_status': x.get('data', {}).get('status'),
                         'sha256': hashlib.sha256(r.content).hexdigest()}
    except Exception as e:
        out['upstox'] = {'error_type': type(e).__name__}
    save(OUT/'api_check.json', out)
    print(json.dumps(out))


if __name__ == '__main__':
    main()
