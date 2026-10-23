import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
import gzip
import subprocess
from pathlib import Path

from dhan_cas_bot.dashboard import app as app_module
from dhan_cas_bot.dashboard import collect as collector
from dhan_cas_bot.dashboard.data import shared_account, telemetry_view
from dhan_cas_bot.service import write_account_observation
from .conftest import FakeBroker
from .test_dashboard import dashboard, request, SECRET, write


def test_shared_token_repair_revision_is_required_without_changing_authority(tmp_path, monkeypatch):
    for revision, fresh, needs_update in ((7, True, True), (8, True, True), (9, True, True), (10, True, True), (11, True, False), (None, True, True), (8, False, False)):
        runtime={'fresh':fresh,'runtime_revision':revision,'authority':'ENABLED','auto_live_armed':True}
        monkeypatch.setattr(collector,'local_snapshot',lambda *_:{'runtime':runtime})
        report=collector.projection({'state_dir':str(tmp_path)}, {})
        assert report['release']['required_runtime_revision']==11
        assert report['release']['upgrade_required'] is needs_update
        assert report['runtime']==runtime


def open_stream(dashboard, *, cookie=None):
    headers = {}
    env = {'REQUEST_METHOD': 'GET', 'PATH_INFO': '/api/events',
           'HTTP_COOKIE': cookie or dashboard.session_cookie()}
    result = dashboard(env, lambda status, values: headers.update(status=status, headers=dict(values)))
    return result, headers


def test_compact_live_updates_do_not_queue_history_or_bypass_auth(dashboard, monkeypatch):
    now=datetime.now(timezone.utc)
    sample={'schema':1,'collector_observed_at':now.isoformat(),
        'runtime':{'observed_at':now.isoformat(),'authority':'ENABLED'},
        'history':{'status':'AVAILABLE','days':[],'events':[{'at':now.isoformat()}]}}
    write(dashboard.snapshot,sample)
    monkeypatch.setattr(app_module.time,'sleep',lambda seconds:None)
    def request_compact(path,cookie=None):
        headers={}
        result=dashboard({'REQUEST_METHOD':'GET','PATH_INFO':path,'QUERY_STRING':'history=omit',
            'HTTP_COOKIE':cookie or ''},lambda status,values:headers.update(status=status))
        return result,headers
    assert request_compact('/api/status')[1]['status'].startswith('401')
    result,headers=request_compact('/api/status',dashboard.session_cookie())
    raw=json.loads(b''.join(result))
    assert headers['status']=='200 OK' and raw['runtime']['authority']=='ENABLED'
    assert 'history' not in raw and raw['history_unchanged'] is True
    stream,headers=request_compact('/api/events',dashboard.session_cookie())
    try:
        assert b'"history":' not in next(stream)
        sample['history']['events'].append({'at':(now+timedelta(seconds=1)).isoformat()})
        write(dashboard.snapshot,sample)
        assert next(stream).startswith(b'event: pulse'), 'History updates must not flood the live feed'
    finally:
        stream.close()
    assert 'history' in json.loads(request(dashboard,'/api/status',credentials='operator:'+SECRET)[2])


def test_full_journal_compression_preserves_history_and_negotiation(dashboard):
    now=datetime.now(timezone.utc)
    history={'status':'AVAILABLE','days':[],'events':[{'at':now.isoformat(),'state':'ARMED_WAITING_SIGNAL'}]*240}
    write(dashboard.snapshot,{'schema':1,'collector_observed_at':now.isoformat(),'history':history})
    status,headers,body=request(dashboard,'/api/status',cookie=dashboard.session_cookie(),overrides={'HTTP_ACCEPT_ENCODING':'br, gzip'})
    assert status=='200 OK' and headers['Content-Encoding']=='gzip'
    assert headers['Vary']=='Accept-Encoding'
    assert json.loads(gzip.decompress(body))['history']==history
    assert len(body)<len(json.dumps(history))//10
    _,headers,body=request(dashboard,'/api/status',cookie=dashboard.session_cookie(),overrides={'HTTP_ACCEPT_ENCODING':'gzip;q=0'})
    assert 'Content-Encoding' not in headers and json.loads(body)['history']==history


def test_sse_authenticated_bounded_and_releases_on_early_disconnect(dashboard):
    assert request(dashboard, '/api/events')[0].startswith('401')
    streams = []
    try:
        for _ in range(6):
            stream, headers = open_stream(dashboard)
            streams.append(stream)
            assert headers['status'] == '200 OK'
            assert headers['headers']['Content-Type'] == 'text/event-stream'
            assert 'Content-Length' not in headers['headers']
        assert open_stream(dashboard)[1]['status'].startswith('503')
        streams.pop().close()  # generator never consumed
        stream, headers = open_stream(dashboard)
        streams.append(stream)
        assert headers['status'] == '200 OK'
        assert b'"available": false' in next(stream)
        # A HEAD response must not claim a thread/stream slot.
        assert request(dashboard, '/api/events', method='HEAD', credentials='operator:'+SECRET)[0].startswith('200')
    finally:
        for stream in streams: stream.close()


def test_sse_expires_cookie_midstream_and_recomputes_staleness(dashboard, monkeypatch):
    now = datetime.now(timezone.utc)
    write(dashboard.snapshot, {'schema':1, 'collector_observed_at':now.isoformat(),
          'runtime':{'observed_at':now.isoformat(),'authority':'ENABLED'}})
    stream, _ = open_stream(dashboard)
    monkeypatch.setattr(app_module.time, 'sleep', lambda seconds: None)
    try:
        assert b'"authority": "ENABLED"' in next(stream)
        monkeypatch.setattr(app_module, 'utcnow', lambda: now+timedelta(seconds=61))
        assert b'"authority": "UNKNOWN"' in next(stream)
        monkeypatch.setattr(app_module.time, 'time', lambda: now.timestamp()+app_module.SESSION_SECONDS+1)
        assert next(stream) == b'event: auth-required\ndata: {}\n\n'
        assert stream.closed
    finally:
        stream.close()


def test_shared_snapshot_prevents_routine_broker_calls_and_strips_unknown_fields(tmp_path, monkeypatch):
    now = datetime.now(timezone.utc)
    funds = asyncio.run(FakeBroker().funds())
    write_account_observation(tmp_path, funds, {'positions':[], 'orders':[]}, now)
    path = tmp_path/'account-observation.json'
    raw = json.loads(path.read_text())
    raw['token'] = 'private-token'
    raw['account']['credentials'] = 'private-token'
    raw['account']['orders'] = [{'quantity':65, 'state':'PENDING', 'token':'private-token'}]
    write(path, raw)
    async def forbidden(*args): raise AssertionError('Routine broker read')
    monkeypatch.setattr(collector, 'read_account', forbidden)
    output = asyncio.run(collector.collect({'state_dir':str(tmp_path)}, tmp_path/'snapshot.json'))
    assert output['account_source'] == 'trader' and output['account_read_ok']
    assert output['account']['observed_at'] == now.isoformat()
    assert 'private-token' not in json.dumps(output)
    assert path.stat().st_mode & 0o777 == 0o600
    assert shared_account(raw, now+timedelta(seconds=61)) is None
    assert shared_account(raw, now-timedelta(seconds=10)) is None


def test_failed_shared_cash_is_not_an_empty_or_fresh_account(tmp_path, monkeypatch):
    now = datetime.now(timezone.utc)
    output = tmp_path/'snapshot.json'
    write(output, {'account': {'observed_at':(now-timedelta(seconds=10)).isoformat(), 'available_cash':'123.45'}})
    write_account_observation(tmp_path, None, {'positions':[], 'orders':[]}, now)
    async def forbidden(*args): raise AssertionError('Do not hide trader cash failure with another read')
    monkeypatch.setattr(collector, 'read_account', forbidden)
    result = asyncio.run(collector.collect({'state_dir':str(tmp_path)}, output))
    assert not result['account_read_ok']
    assert result['account']['available_cash'] == '123.45'


def test_expired_successful_independent_read_is_stale_not_a_failed_broker_call(tmp_path):
    now=datetime.now(timezone.utc)
    result=collector.projection({'state_dir':str(tmp_path)},{'account':{'available_cash':'123.45'}},
        checked={'ok':True,'account':{'available_cash':'123.45'},'observed_at':(now-timedelta(seconds=100)).isoformat()})
    assert not result['account_read_ok']
    assert result['account_error']=='ACCOUNT_OBSERVATION_STALE'


def test_failed_check_keeps_the_actual_failure_distinct_from_stale_success(tmp_path):
    result=collector.projection({'state_dir':str(tmp_path)},{},
        checked={'ok':False,'account':None,'observed_at':datetime.now(timezone.utc).isoformat()})
    assert result['account_error']=='BROKER_READ_FAILED'


def test_lost_shared_source_requests_fallback_before_five_minute_check_expiry():
    now=datetime.now(timezone.utc);checked={'ok':True,'observed_at':(now-timedelta(seconds=20)).isoformat()}
    assert collector.independent_check_due(None,checked,now)
    assert not collector.independent_check_due({'account_read_ok':True},checked,now)
    assert not collector.independent_check_due({'account_read_ok':False},checked,now)


def test_watch_publishes_local_status_while_independent_check_is_stalled(tmp_path, monkeypatch):
    async def run():
        entered, release = asyncio.Event(), asyncio.Event()
        async def delayed(*args):
            entered.set()
            await release.wait()
        monkeypatch.setattr(collector, 'read_account', delayed)
        now = datetime.now(timezone.utc)
        write_account_observation(tmp_path, await FakeBroker().funds(), {'positions':[], 'orders':[]}, now)
        write(tmp_path/'status.json', {'observed_at':now.isoformat(), 'state':'NO_TRADE_DAY'})
        path = tmp_path/'snapshot.json'
        task = asyncio.create_task(collector.watch({'state_dir':str(tmp_path)}, path))
        try:
            await entered.wait()
            initial = json.loads(path.read_text())
            write(tmp_path/'status.json', {'observed_at':now.isoformat(), 'state':'RECOVERING'})
            async def changed():
                while json.loads(path.read_text())['runtime']['state'] != 'RECOVERING':
                    await asyncio.sleep(.01)
            await asyncio.wait_for(changed(), 1.5)
            assert json.loads(path.read_text())['account_read_ok']
            assert not release.is_set()  # API still waiting; publication continued.
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
    asyncio.run(run())


def test_telemetry_projection_only_allows_known_numbers():
    value = telemetry_view({'latency': {'http_ack_ms': {'p95':'NaN', 'samples': 1, 'secret':'xyz'}, 'token': 'xyz'},
                            'decision_counts': {'EMPTY_BOOK': 3, 'token':'xyz'}})
    assert value['latency']['http_ack_ms']['p95'] is None
    assert value['decision_counts'] == {'EMPTY_BOOK':3}
    assert 'xyz' not in json.dumps(value)


def test_browser_stream_push_fallback_visibility_and_auth():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(['node', str(root/'tests/dashboard_stream_test.cjs')], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_sse_sends_small_pulse_until_source_evidence_or_freshness_changes(dashboard, monkeypatch):
    now = datetime.now(timezone.utc)
    write(dashboard.snapshot, {'schema':1,'collector_observed_at':now.isoformat(),
          'runtime':{'observed_at':now.isoformat(),'authority':'ENABLED','feed_health':{'market':{'connected':True}}}})
    monkeypatch.setattr(app_module.time,'sleep',lambda seconds:None)
    monkeypatch.setattr(app_module,'utcnow',lambda:now)
    stream,_=open_stream(dashboard)
    try:
        assert next(stream).startswith(b'retry:')
        monkeypatch.setattr(app_module,'utcnow',lambda:now+timedelta(seconds=1))
        assert next(stream).startswith(b'event: pulse')
        advanced=(now+timedelta(seconds=1)).isoformat()
        write(dashboard.snapshot, {'schema':1,'collector_observed_at':advanced,
              'runtime':{'observed_at':advanced,'authority':'ENABLED','feed_health':{'market':{'connected':True}}}})
        pulse=next(stream)
        assert pulse.startswith(b'event: pulse') and advanced.encode() in pulse
        monkeypatch.setattr(app_module,'utcnow',lambda:now+timedelta(seconds=48))
        expired=next(stream)
        assert b'"authority": "UNKNOWN"' in expired
        assert not expired.startswith(b'event: pulse')
    finally: stream.close()


def test_sse_quote_updates_do_not_resend_unchanged_history(dashboard, monkeypatch):
    now=datetime.now(timezone.utc)
    sample={'schema':1,'collector_observed_at':now.isoformat(),
            'runtime':{'observed_at':now.isoformat(),'books_observed':1},
            'history':{'status':'AVAILABLE','days':[],'events':[{'at':now.isoformat()}]}}
    monkeypatch.setattr(app_module.time,'sleep',lambda seconds:None)
    write(dashboard.snapshot,sample)
    stream,_=open_stream(dashboard)
    try:
        assert b'"history":' in next(stream)
        sample['runtime']['books_observed']=2
        write(dashboard.snapshot,sample)
        update=next(stream)
        assert b'"history":' not in update and b'"history_unchanged": true' in update
        sample['history']={'status':'UNAVAILABLE','days':[],'events':[]}
        write(dashboard.snapshot,sample)
        assert b'"status": "UNAVAILABLE"' in next(stream)
    finally: stream.close()
