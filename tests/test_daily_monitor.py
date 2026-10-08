"""Negative boundaries for the independently deployed read-only observer."""
import asyncio
from datetime import datetime,timedelta,timezone
import json

import httpx
import pytest

from dhan_cas_bot.daily_monitor import ChartReader, monitor_report
from dhan_cas_bot.dashboard.data import daily_monitor_view
from dhan_cas_bot.session_strategies import GAP, REBOUND


def test_observer_refuses_order_and_arbitrary_http_before_transport():
    calls=[]
    client=httpx.AsyncClient(transport=httpx.MockTransport(lambda req: calls.append(req)))
    reader=ChartReader('private', client=client)
    for method,path in [('POST','/orders'),('DELETE','/orders/1'),('GET','/fundlimit'),('POST','https://example.com/charts/intraday'),('POST','/charts/intraday?x=1')]:
        with pytest.raises(ValueError):
            asyncio.run(reader._request(method,path,json={}))
    assert not calls
    asyncio.run(client.aclose())


def test_chart_transport_is_fixed_endpoint_without_redirects():
    calls=[]
    def handle(req):
        calls.append(req)
        return httpx.Response(200,json={'timestamp':[]})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            r=ChartReader('private',client=client)
            assert await r._request('POST','/charts/intraday',json={'securityId':'13'}) == {'timestamp':[]}
    asyncio.run(run())
    assert str(calls[0].url)=='https://api.dhan.co/v2/charts/intraday'
    assert calls[0].headers['access-token']=='private'


def test_failed_refresh_replaces_signal_with_unknown_and_never_grants_authority():
    now=datetime(2026,10,7,4,15,tzinfo=timezone.utc)
    result=monitor_report(now,None,{}, {},set(),error='INPUTS_UNAVAILABLE')
    assert result['mode']=='READ_ONLY' and result['writes_to_broker'] is False
    assert len(result['strategy_evaluations'])==2
    assert all(row['state']=='UNKNOWN' and row['side'] is None for row in result['strategy_evaluations'])
    assert 'authority' not in result


def test_projection_drops_secrets_and_rejects_write_mode():
    now=datetime(2026,10,7,4,15,tzinfo=timezone.utc)
    raw={'observed_at':now.isoformat(),'mode':'READ_ONLY','writes_to_broker':False,
         'error':'private-token','authority':'ENABLED','token':'secret',
         'strategy_evaluations':[{'strategy':GAP,'state':'SIGNAL','reason':'GAP_FADE_CONFIRMED','side':'CE'}]}
    result=daily_monitor_view(raw,now)
    assert result['fresh'] and result['mode']=='READ_ONLY'
    assert 'secret' not in json.dumps(result) and 'private-token' not in json.dumps(result)
    assert 'authority' not in result
    raw['writes_to_broker']=True
    assert daily_monitor_view(raw,now) is None


def test_stale_observer_is_not_a_current_signal():
    now=datetime(2026,10,7,4,15,tzinfo=timezone.utc)
    raw={'observed_at':(now-timedelta(minutes=3)).isoformat(),'mode':'READ_ONLY','writes_to_broker':False,
         'strategy_evaluations':[{'strategy':REBOUND,'state':'SIGNAL','reason':'SELLOFF_THRESHOLD_MET','side':'CE'}]}
    result=daily_monitor_view(raw,now)
    assert not result['fresh']
    assert result['strategy_evaluations'][0]['state']=='UNKNOWN'
    assert result['strategy_evaluations'][0]['side'] is None


def test_observer_unit_cannot_write_trader_state_or_open_ledger():
    from pathlib import Path
    text=Path('ops/dhan-daily-monitor.service').read_text()
    assert 'Environment=DHAN_BROKER_READ_ONLY=1' in text
    assert 'ReadWritePaths=/var/lib/sablestone-dhan-dashboard\n' in text
    assert 'InaccessiblePaths=-/var/lib/sablestone-dhan/ledger.sqlite3 ' in text
    assert 'dhan-cas run' not in text
    assert 'activate-live' not in text


def test_restart_restores_only_actual_same_day_decisions_not_future_or_private_data():
    from dhan_cas_bot.daily_monitor import restore_decisions
    now=datetime(2026,10,8,4,16,tzinfo=timezone.utc)
    valid={'strategy':GAP,'state':'NO_SIGNAL','reason':'GAP_FADE_CONDITIONS_NOT_MET',
           'evaluated_at':(now-timedelta(minutes=1)).isoformat(),'secret':'private',
           'conditions':[{'key':'gap_size','state':'FAIL','value':'.002','minimum':'.005'}]}
    raw={'mode':'READ_ONLY','writes_to_broker':False,'last_decisions':[valid,
          {'strategy':REBOUND,'state':'SIGNAL','evaluated_at':(now+timedelta(minutes=1)).isoformat()}]}
    restored=restore_decisions(raw,now)
    assert set(restored)=={GAP}
    assert 'private' not in json.dumps(restored)
    assert restored[GAP]['conditions'][0]['minimum']=='0.005'
    assert restore_decisions(raw,now+timedelta(days=1))=={}
    assert restore_decisions({**raw,'writes_to_broker':True},now)=={}
