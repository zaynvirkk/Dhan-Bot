import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
import subprocess
from pathlib import Path

from dhan_cas_bot.dashboard import app as app_module
from dhan_cas_bot.dashboard import collect as collector
from dhan_cas_bot.dashboard.data import shared_account, telemetry_view
from dhan_cas_bot.service import write_account_observation
from .conftest import FakeBroker
from .test_dashboard import dashboard, request, SECRET, write


def open_stream(dashboard, *, cookie=None):
    headers = {}
    env = {'REQUEST_METHOD': 'GET', 'PATH_INFO': '/api/events',
           'HTTP_COOKIE': cookie or dashboard.session_cookie()}
    result = dashboard(env, lambda status, values: headers.update(status=status, headers=dict(values)))
    return result, headers


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
