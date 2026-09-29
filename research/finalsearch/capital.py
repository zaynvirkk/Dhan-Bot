"""Fresh read-only quotes and indicative margins; never submits an order."""
import asyncio, csv, hashlib, json, time
from datetime import datetime, timezone
import httpx
from dhan_cas_bot.auth import resolve_dhan_access_token
from research.gauntlet.data import save
from research.multifeature.providers import environment
from .experiment import STORE, OUT, D

ALLOWED = {'/v2/fundlimit', '/v2/positions', '/v2/marketfeed/quote', '/v2/margincalculator', '/v2/margincalculator/multi'}

def main():
    env = environment()
    token = asyncio.run(resolve_dhan_access_token(env['DHAN_CLIENT_ID'], pin=env['DHAN_PIN'], totp_secret=env['DHAN_TOTP_SECRET']))
    headers = {'access-token': token, 'client-id': env['DHAN_CLIENT_ID']}
    receipts = []
    def request(path, body=None):
        if path not in ALLOWED: raise ValueError('Not a read-only endpoint')
        start = time.monotonic()
        r = httpx.request('POST' if body is not None else 'GET', 'https://api.dhan.co' + path,
                          headers=headers, json=body, timeout=30)
        try: data = r.json()
        except ValueError: data = {'error': 'NON_JSON'}
        # No account IDs or tokens in the persisted receipt.
        def redact(value):
            if isinstance(value, dict): return {k: redact(v) for k, v in value.items() if 'clientid' not in k.lower()}
            if isinstance(value, list): return list(map(redact, value))
            return value
        data = redact(data)
        if path == '/v2/positions': data = {'count': len(data)} if isinstance(data, list) else {'error': 'POSITION_READ_FAILED'}
        safe = {k: v for k, v in (body or {}).items() if k != 'dhanClientId'}
        receipts.append({'at': datetime.now(timezone.utc).isoformat(), 'path': path, 'request': safe,
                         'status': r.status_code, 'response': data, 'sha256': hashlib.sha256(r.content).hexdigest(),
                         'elapsed_ms': round((time.monotonic() - start) * 1000)})
        save(STORE / 'capital_requests.json', receipts)
        time.sleep(1.1)
        if r.status_code != 200: raise ValueError('HTTP_' + str(r.status_code))
        return data
    funds = request('/v2/fundlimit'); positions = request('/v2/positions')
    rows = list(csv.DictReader((STORE / 'current_master.csv').open()))
    today = datetime.now(timezone.utc).date().isoformat()
    chosen = []
    for sym in ('NIFTY', 'BANKNIFTY', 'GOLDPETAL', 'GOLDTEN', 'CRUDEOILM', 'NATGASMINI', 'SILVERMIC'):
        eligible = [r for r in rows if r['UNDERLYING_SYMBOL'] == sym and r['INSTRUMENT'].startswith('FUT') and r['SM_EXPIRY_DATE'] > today]
        # Avoid near tender/devolvement: current feasibility, not historical selection.
        if sym not in ('NIFTY', 'BANKNIFTY'): eligible = [r for r in eligible if r['SM_EXPIRY_DATE'] >= '2026-10-15']
        if eligible: chosen.append(min(eligible, key=lambda r: r['SM_EXPIRY_DATE']))
    quote_body = {}
    def segment(r): return 'MCX_COMM' if r['EXCH_ID'] == 'MCX' else 'NSE_FNO'
    for r in chosen: quote_body.setdefault(segment(r), []).append(int(r['SECURITY_ID']))
    quote_body['IDX_I'] = [13]
    quotes = request('/v2/marketfeed/quote', quote_body)['data']
    spot = D(str(quotes['IDX_I']['13']['last_price']))
    options = [r for r in rows if r['UNDERLYING_SYMBOL'] == 'NIFTY' and r['INSTRUMENT'] == 'OPTIDX' and r['SM_EXPIRY_DATE'] > today]
    expiries = sorted({r['SM_EXPIRY_DATE'] for r in options}); expiry = expiries[0]
    near = [r for r in options if r['SM_EXPIRY_DATE'] == expiry]
    strikes = sorted({D(r['STRIKE_PRICE']) for r in near}); atm = min(strikes, key=lambda k: abs(k - spot))
    required = [(expiry, atm + delta, side) for delta, side in [(0, 'CE'), (50, 'CE'), (100, 'CE'), (0, 'PE'), (-50, 'PE'), (-100, 'PE')]]
    required.append((expiries[1], atm, 'CE'))
    opts = {}
    for exp, strike, side in required:
        r = next(x for x in options if x['SM_EXPIRY_DATE'] == exp and D(x['STRIKE_PRICE']) == strike and x['OPTION_TYPE'] == side)
        opts[exp, strike, side] = r
    opt_quotes = request('/v2/marketfeed/quote', {'NSE_FNO': [int(r['SECURITY_ID']) for r in opts.values()]})['data']['NSE_FNO']
    quotes['NSE_FNO'].update(opt_quotes)
    def leg(r, side):
        quote = quotes[segment(r)][r['SECURITY_ID']]; price = D(str(quote['last_price']))
        if price <= 0: raise ValueError('ZERO_PRICE')
        return {'exchangeSegment': segment(r), 'transactionType': side, 'quantity': int(D(r['LOT_SIZE'])),
                'productType': 'MARGIN', 'securityId': r['SECURITY_ID'], 'price': float(price)}
    result = []
    def check(name, rs, sides):
        legs = [leg(r, s) for r, s in zip(rs, sides)]
        if len(legs) == 1:
            margin = request('/v2/margincalculator', {**legs[0], 'dhanClientId': env['DHAN_CLIENT_ID']})
        else:
            margin = request('/v2/margincalculator/multi', {'dhanClientId': env['DHAN_CLIENT_ID'], 'includePosition': False,
                                                         'includeOrder': False, 'scripList': legs})
        row = {'name': name, 'contracts': [r['DISPLAY_NAME'] for r in rs], 'legs': legs, 'margin': margin}
        result.append(row); save(OUT / 'capital.json', {'checked_at': datetime.now(timezone.utc).isoformat(), 'funds': funds,
             'positions': positions, 'spot': str(spot), 'market_closed': True, 'checks': result})
        print(name, margin, flush=True)
    for r in chosen: check(r['UNDERLYING_SYMBOL'] + '_FUTURE', [r], ['BUY'])
    c = lambda delta, side='CE', exp=expiry: opts[exp, atm + delta, side]
    check('NAKED_SHORT_CALL', [c(0)], ['SELL'])
    check('CALL_DEBIT_50', [c(0), c(50)], ['BUY', 'SELL'])
    check('CALL_CREDIT_50', [c(0), c(50)], ['SELL', 'BUY'])
    check('PUT_CREDIT_50', [c(0, 'PE'), c(-50, 'PE')], ['SELL', 'BUY'])
    check('IRON_FLY_50', [c(50), c(-50, 'PE'), c(0), c(0, 'PE')], ['BUY', 'BUY', 'SELL', 'SELL'])
    check('LONG_BUTTERFLY_50', [c(0), c(100), c(50), c(50)], ['BUY', 'BUY', 'SELL', 'SELL'])
    check('CALL_CALENDAR', [c(0, exp=expiries[1]), c(0)], ['BUY', 'SELL'])
    check('LONG_STRADDLE', [c(0), c(0, 'PE')], ['BUY', 'BUY'])

if __name__ == '__main__':
    try: main()
    except Exception as exc:
        # Exception messages from auth/HTTP libraries can contain secret URLs.
        print('CAPITAL_CHECK_STOPPED', type(exc).__name__, flush=True)
        raise SystemExit(1)
