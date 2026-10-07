from datetime import datetime, timezone
import json

from websockets.exceptions import ConnectionClosedError
from websockets.frames import Close

from dhan_cas_bot.commissioning import connection_failure
from dhan_cas_bot.dashboard.data import connections_view


def test_close_diagnostics_never_publish_provider_reason_or_credentials():
    secret = 'wss://provider.example?token=DO_NOT_PUBLISH'
    exc = ConnectionClosedError(Close(1008, secret), Close(1000, secret), True)
    value = connection_failure(exc)
    assert value == {'close_received_code': 1008, 'close_sent_code': 1000,
                     'keepalive_timeout': False}
    assert secret not in json.dumps(value)


def test_local_keepalive_timeout_is_distinct_from_peer_close():
    exc = ConnectionClosedError(None, Close(1011, 'keepalive ping timeout'), None)
    assert connection_failure(exc) == {'close_received_code': None,
                                      'close_sent_code': 1011,
                                      'keepalive_timeout': True}
    assert connection_failure(OSError('secret in a URL')) == {}


def test_sanitized_close_diagnostics_reach_dashboard_without_raw_reason():
    now = datetime.now(timezone.utc)
    raw = {'observed_at': now.isoformat(), 'checks': {'dhan_market_feed': {
        'status': 'FAIL', 'error_type': 'ConnectionClosedError',
        'close_received_code': 1008, 'close_sent_code': 1000,
        'keepalive_timeout': False, 'raw_reason': 'PRIVATE_SECRET'}}}
    view = connections_view(raw, now)
    row = next(x for x in view['checks'] if x['name'] == 'dhan_market_feed')
    assert row['facts']['close_received_code'] == 1008
    assert row['facts']['keepalive_timeout'] is False
    assert 'PRIVATE_SECRET' not in json.dumps(view)
