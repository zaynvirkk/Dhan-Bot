"""Authentication, data isolation and stale/failed observations (no real broker)."""
import asyncio
import base64
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sqlite3
from types import SimpleNamespace

import httpx
import pytest

from dhan_cas_bot.dashboard import collect as collector
from dhan_cas_bot.dashboard.app import ASSETS, Dashboard, view_snapshot
from dhan_cas_bot.dashboard.data import account_view, connections_view, freshness, ledger_view, money, runtime_view
from dhan_cas_bot.ledger import SCHEMA

NOW = datetime(2026, 9, 29, 5, 0, tzinfo=timezone.utc)
SECRET = 'synthetic-dashboard-password-not-a-broker-credential'


def write(path, value):
    path.write_text(json.dumps(value))
    return path


@pytest.fixture
def dashboard(tmp_path):
    auth = write(tmp_path/'auth.json', {'username':'operator', 'password_sha256':hashlib.sha256(SECRET.encode()).hexdigest()})
    return Dashboard(tmp_path/'snapshot.json', auth)


def request(app, path='/', method='GET', credentials=None, raw=None):
    headers = {}
    def start(status, values): headers.update(status=status, headers=dict(values))
    env = {'PATH_INFO':path, 'REQUEST_METHOD':method}
    if credentials is not None:
        env['HTTP_AUTHORIZATION'] = 'Basic '+base64.b64encode(credentials.encode()).decode()
    if raw is not None: env['HTTP_AUTHORIZATION'] = raw
    body = b''.join(app(env, start))
    return headers['status'], headers['headers'], body


@pytest.mark.parametrize('path', ['/', '/api/status', '/app.js', '/app.css', '/favicon.svg', '/../../secrets.env'])
def test_every_route_requires_authentication(dashboard, path):
    status, headers, body = request(dashboard, path)
    assert status.startswith('401')
    assert 'WWW-Authenticate' in headers and headers['Cache-Control']=='no-store'
    assert b'9411' not in body


@pytest.mark.parametrize('raw', ['Basic !!!!', 'Bearer secret', 'Basic '+base64.b64encode('öperator:wrong'.encode()).decode(), 'Basic '+base64.b64encode(b'operator:wrong').decode(), 'Basic '+('a'*600)])
def test_malformed_and_incorrect_auth_rejected(dashboard, raw):
    assert request(dashboard, raw=raw)[0].startswith('401')


def test_no_mutating_endpoints_and_no_traversal(dashboard):
    for method in ['POST','PUT','PATCH','DELETE','OPTIONS']:
        status, headers, _ = request(dashboard, '/api/activate', method, 'operator:'+SECRET)
        assert status.startswith('405') and headers['Allow']=='GET, HEAD'
    assert request(dashboard, '/../../etc/passwd', credentials='operator:'+SECRET)[0].startswith('404')
    assert not dashboard.snapshot.exists()


def test_auth_missing_fails_closed(tmp_path):
    with pytest.raises(ValueError): Dashboard(tmp_path/'s', tmp_path/'missing')
    bad = write(tmp_path/'auth', {'username':'operator', 'password':'plaintext'})
    with pytest.raises(ValueError): Dashboard(tmp_path/'s', bad)


def test_missing_snapshot_is_unknown_and_assets_are_authenticated(dashboard):
    status, _, body = request(dashboard, '/api/status', credentials='operator:'+SECRET)
    assert status.startswith('503') and json.loads(body)['available'] is False
    for path in ASSETS:
        status, headers, body = request(dashboard, path, credentials='operator:'+SECRET)
        assert status.startswith('200') and body
        assert "script-src 'self'" in headers['Content-Security-Policy']
        assert headers['X-Frame-Options']=='DENY'
        status, h, b = request(dashboard, path, 'HEAD', 'operator:'+SECRET)
        assert not b and int(h['Content-Length'])==len(body)


@pytest.mark.parametrize('stamp', [None, 'bad', NOW.replace(tzinfo=None).isoformat(), (NOW+timedelta(minutes=10)).isoformat(), (NOW-timedelta(minutes=10)).isoformat()])
def test_missing_naive_future_and_old_timestamps_are_not_fresh(stamp):
    assert freshness(stamp, NOW, 60)['fresh'] is False


def test_current_and_failed_snapshot_recomputed_on_every_read(tmp_path):
    path = write(tmp_path/'s', {'schema':1,'collector_observed_at':NOW.isoformat(),'account_read_ok':True,
        'runtime':runtime_view({'observed_at':NOW.isoformat(),'writes':True,'auto_live_armed':True},NOW),
        'account':{'observed_at':NOW.isoformat(),'available_cash':'9411.18'},
        'connections':{'observed_at':NOW.isoformat(),'checks':[]}})
    fresh = view_snapshot(path, NOW)
    assert fresh['runtime']['authority']=='ENABLED' and fresh['account']['fresh']
    stale = view_snapshot(path, NOW+timedelta(minutes=2))
    assert stale['runtime']['authority']=='UNKNOWN' and not stale['account']['fresh']
    assert not stale['connections']['fresh']  # collector death overrides check TTL
    fresh['account_read_ok']=False
    write(path,fresh)
    failed=view_snapshot(path,NOW)
    assert not failed['account']['fresh'] and failed['account']['available_cash']=='9411.18'


def test_heartbeat_freshness_covers_collector_cycle_but_expires(tmp_path):
    runtime=runtime_view({'observed_at':NOW.isoformat(),'writes':False,'auto_live_armed':False},NOW)
    path=write(tmp_path/'s',{'schema':1,'collector_observed_at':NOW.isoformat(),'runtime':runtime})
    # 20s broker timeout plus 15s scheduling gap must not manufacture an outage.
    normal=view_snapshot(path,NOW+timedelta(seconds=36))
    assert normal['runtime']['fresh'] and normal['runtime']['authority']=='DISABLED'
    expired=view_snapshot(path,NOW+timedelta(seconds=46))
    assert not expired['runtime']['fresh'] and expired['runtime']['authority']=='UNKNOWN'


def test_running_does_not_imply_authority_and_raw_errors_never_exported():
    assert runtime_view({'observed_at':NOW.isoformat(),'writes':True},NOW)['authority']=='UNKNOWN'
    assert runtime_view({'observed_at':NOW.isoformat(),'writes':True,'auto_live_armed':'false'},NOW)['authority']=='UNKNOWN'
    raw={'observed_at':NOW.isoformat(),'writes':False,'auto_live_armed':False,
         'state':'ARMED_WAITING_SIGNAL','reason':'RECOVERY_REQUIRED:access-token TOP-SECRET', 'account_id':'PRIVATE-ID'}
    out=runtime_view(raw,NOW)
    assert out['authority']=='DISABLED'
    assert 'TOP-SECRET' not in json.dumps(out) and 'PRIVATE-ID' not in json.dumps(out)
    raw['state']=[]
    assert runtime_view(raw,NOW)['state']=='UNKNOWN'
    checks=connections_view({'checks':{'dhan_auth':{'status':[], 'error_type':{}, 'data_plan':{}, 'token':'TOP-SECRET'}}},NOW)
    assert checks['checks'][0]['status']=='UNKNOWN' and 'TOP-SECRET' not in json.dumps(checks)


def test_decimal_cash_and_unknown_pnl_distinct_from_zero():
    f=SimpleNamespace(spendable_cash=Decimal('9411.18'))
    empty=account_view(f,[],[],NOW)
    assert empty['available_cash']=='9411.18' and empty['open_position_count']==0
    assert empty['realised_pnl'] is None and empty['unrealised_pnl'] is None
    positions=[{'netQty':65,'tradingSymbol':'NIFTY CE','realizedProfit':'0.10','unrealizedProfit':'0.20','token':'TOP-SECRET'},
               {'netQty':0,'realizedProfit':'0.20','unrealizedProfit':'0.10'}]
    out=account_view(f,positions,[],NOW)
    assert out['realised_pnl']=='0.30' and out['unrealised_pnl']=='0.30'
    assert out['open_position_count']==1 and 'TOP-SECRET' not in json.dumps(out)
    positions[1].pop('realizedProfit')
    assert account_view(f,positions,[],NOW)['realised_pnl'] is None
    with pytest.raises(ValueError): account_view(f,[{'netQty':'NaN'}],[],NOW)
    for value in ['NaN','Infinity','-Infinity',True,None]: assert money(value) is None
    with pytest.raises(ValueError): account_view(SimpleNamespace(spendable_cash=Decimal('NaN')),[],[],NOW)


def test_ledger_readonly_redacted_and_missing_not_empty(tmp_path):
    path=tmp_path/'ledger.sqlite3'
    assert ledger_view(path)['available'] is False and not path.exists()
    db=sqlite3.connect(path)
    db.executescript(SCHEMA)
    db.execute('INSERT INTO intents VALUES (?,?,?,?,?,?,?,?,?,?,?)',
       ('i','c','l','BUY','123',65,'10.10','SENT','700','TOP-SECRET',NOW.isoformat()))
    db.execute('INSERT INTO orders VALUES (?,?,?,?,?)',('o','i','PRIVATE-ID','TRADED','TOP-SECRET'))
    db.execute('INSERT INTO fills VALUES (?,?,?,?,?,?,?,?,?)',('t','o','i','123',65,'10.10','20',NOW.isoformat(),'TOP-SECRET'))
    db.execute('INSERT INTO incidents VALUES (?,?,?,?)',('x','TOKEN-PRIVATE','TOP-SECRET',NOW.isoformat()))
    db.commit(); db.close()
    before=hashlib.sha256(path.read_bytes()).hexdigest()
    out=ledger_view(path)
    assert out['available'] and out['counts']=={'intents':1,'fills':1,'incidents':1}
    assert out['fills'][0]['price']=='10.10' and out['orders'][0]['state']=='TRADED'
    assert not any(s in json.dumps(out) for s in ['TOP-SECRET','PRIVATE-ID','TOKEN-PRIVATE'])
    assert hashlib.sha256(path.read_bytes()).hexdigest()==before
    bad=tmp_path/'bad.sqlite'; bad.write_bytes(b'not a sqlite database')
    assert ledger_view(bad)['available'] is False


def test_collector_uses_only_get_and_existing_token(monkeypatch,tmp_path):
    calls=[]
    write(tmp_path/'dhan_token.json',{'account':'TEST','token':'BROKER-SECRET'})
    real=collector.DhanBroker
    def broker(*args,**kwargs):
        assert kwargs['allow_writes'] is False
        b=real(*args,**kwargs)
        def transport(request):
            calls.append((request.method,request.url.path))
            assert request.headers['access-token']=='BROKER-SECRET'
            payload={'/v2/profile':{'dhanClientId':'TEST'}, '/v2/fundlimit':{'availabelBalance':'9411.18'}, '/v2/positions':[], '/v2/orders':[]}[request.url.path]
            return httpx.Response(200,json=payload)
        b.client=httpx.AsyncClient(transport=httpx.MockTransport(transport))
        return b
    monkeypatch.setattr(collector,'DhanBroker',broker)
    token_before=(tmp_path/'dhan_token.json').read_bytes()
    out=asyncio.run(collector.collect({'state_dir':str(tmp_path),'account_id':'TEST'},tmp_path/'snapshot.json'))
    assert calls==[('GET','/v2/profile'),('GET','/v2/fundlimit'),('GET','/v2/positions'),('GET','/v2/orders')]
    assert out['account_read_ok'] and out['writes_to_broker'] is False
    assert out['account']['available_cash']=='9411.18'
    assert 'BROKER-SECRET' not in json.dumps(out)
    assert (tmp_path/'dhan_token.json').read_bytes()==token_before
    assert (tmp_path/'snapshot.json').stat().st_mode & 0o777 == 0o640
    assert not list(tmp_path.glob('.snapshot-*'))


def test_failed_account_read_retains_historical_observation(monkeypatch,tmp_path):
    output=write(tmp_path/'snapshot.json',{'account':{'observed_at':NOW.isoformat(),'available_cash':'9000.00'}})
    async def fail(_): raise RuntimeError('SECRET ERROR PAYLOAD')
    monkeypatch.setattr(collector,'read_account',fail)
    out=asyncio.run(collector.collect({'state_dir':str(tmp_path)},output))
    assert not out['account_read_ok'] and out['account']['available_cash']=='9000.00'
    assert out['account']['observed_at']==NOW.isoformat()
    assert 'SECRET ERROR' not in output.read_text()
    assert not view_snapshot(output)['account']['fresh']


def test_wrong_account_does_not_make_a_provider_request(monkeypatch,tmp_path):
    write(tmp_path/'dhan_token.json',{'account':'OTHER','token':'secret'})
    def forbidden(*a,**k): raise AssertionError('Provider must not be constructed')
    monkeypatch.setattr(collector,'DhanBroker',forbidden)
    with pytest.raises(ValueError): asyncio.run(collector.read_account({'state_dir':str(tmp_path),'account_id':'TEST'}))


def test_web_service_is_separated_from_trader_keys():
    root=Path(__file__).resolve().parents[1]
    service=(root/'ops/dhan-dashboard.service').read_text()
    assert 'User=dhan-dashboard' in service and '--bind 127.0.0.1:8088' in service
    assert 'InaccessiblePaths=/etc/sablestone-dhan /var/lib/sablestone-dhan' in service
    assert 'EnvironmentFile=' not in service and 'IPAddressDeny=any' in service
    collect=(root/'ops/dhan-dashboard-collect.service').read_text()
    assert 'DHAN_BROKER_READ_ONLY=1' in collect
    assert 'ReadWritePaths=/var/lib/sablestone-dhan-dashboard\n' in collect
    assert 'secrets.env' in collect and 'EnvironmentFile=' not in collect
    installer=(root/'ops/install_dashboard.sh').read_text()
    assert 'activate-live.py' not in installer and 'restart dhan-cas' not in installer
    html=(root/'dhan_cas_bot/dashboard/static/index.html').read_text()
    assert 'activate-live.py --capital available --check-only' in html
