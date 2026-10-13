from datetime import datetime, timezone
import json

from websockets.exceptions import ConnectionClosedError
from websockets.frames import Close

from dhan_cas_bot.commissioning import connection_failure
from dhan_cas_bot.dashboard.data import connections_view


def test_upstox_check_finishes_on_index_snapshot_without_waiting_for_more_frames():
    import asyncio
    from dhan_cas_bot import commissioning as checks, MarketDataFeed_pb2 as proto

    status = proto.FeedResponse()
    status.marketInfo.casMarketStatus['NSE_INDEX'].status = 'NORMAL_OPEN'
    index = proto.FeedResponse()
    index.feeds[checks.NIFTY_KEY].fullFeed.indexFF.ltpc.ltp = 22500

    class Socket:
        calls = 0

        async def recv(self):
            self.calls += 1
            assert self.calls <= 2, 'A completed index check must not drain a live stream'
            return (status if self.calls == 1 else index).SerializeToString()

    socket = Socket()
    result, price = asyncio.run(checks.read_upstox_check(socket))
    assert socket.calls == 2
    assert result['index_seen'] and result['cas_status_seen']
    assert price == 22500


def test_upstox_check_rejects_market_status_without_a_usable_index():
    import asyncio
    import pytest
    from dhan_cas_bot import commissioning as checks, MarketDataFeed_pb2 as proto
    from dhan_cas_bot.domain import ContractError

    class Socket:
        calls = 0

        async def recv(self):
            self.calls += 1
            if self.calls == 1:
                return proto.FeedResponse().SerializeToString()
            raise asyncio.TimeoutError()

    with pytest.raises(ContractError):
        asyncio.run(checks.read_upstox_check(Socket()))


def test_contract_resolution_does_not_block_socket_deadlines(monkeypatch):
    import asyncio
    import threading
    import time
    from datetime import date
    from dhan_cas_bot import commissioning as checks

    started, finished = threading.Event(), threading.Event()
    monkeypatch.setattr(checks.RuleSource, 'current_expiry', lambda *a, **kw: date(2026, 10, 13))
    monkeypatch.setattr(checks.RuleSource, 'parse_freeze', lambda *a, **kw: {'NIFTY': 3510})

    def slow_master(*a, **kw):
        started.set()
        time.sleep(.1)
        finished.set()
        return []

    monkeypatch.setattr(checks, 'load_dhan_master', slow_master)

    async def exercise():
        task = asyncio.create_task(checks.resolve_check_contracts(b'master', b'freeze', date(2026, 10, 13)))
        while not started.is_set():
            await asyncio.sleep(.001)
        assert not finished.is_set(), 'Contract parsing blocked the feed-check event loop'
        return await task

    assert asyncio.run(exercise()) == (date(2026, 10, 13), 3510, [])


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


def test_dhan_documented_deactive_data_plan_is_not_lost_as_unknown():
    now = datetime.now(timezone.utc)
    for provider_value, expected in [('Deactive', 'Inactive'), ('Active', 'Active'),
                                     ('Expired', 'Expired'), ('token=SECRET', 'UNKNOWN')]:
        raw = {'observed_at': now.isoformat(), 'checks': {'dhan_auth': {
            'status': 'PASS', 'account_matches': True, 'data_plan': provider_value}}}
        view = connections_view(raw, now)
        auth = next(x for x in view['checks'] if x['name'] == 'dhan_auth')
        assert auth['facts']['data_plan'] == expected
        assert 'SECRET' not in json.dumps(view)
