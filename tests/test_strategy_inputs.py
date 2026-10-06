import asyncio
from datetime import date, timedelta

import httpx
import pytest

from dhan_cas_bot.domain import ContractError
from dhan_cas_bot.strategy_inputs import CalendarSource, MinuteSource, selected_contracts, strategy_names, route_window
from dhan_cas_bot.session_strategies import GAP, REBOUND, CAS
from tests.test_session_strategies import at, calendar


def test_no_calendar_fallback_to_weekday_after_failure():
    async def run():
        async def handler(request):
            return httpx.Response(503, json={"error":"unavailable"})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            source = CalendarSource("fixture-token", client=client)
            with pytest.raises(httpx.HTTPStatusError): await source.fetch(at())
    asyncio.run(run())


def test_calendar_queries_holiday_and_weekend_instead_of_assuming_next_weekday():
    async def run():
        requested=[]
        async def handler(request):
            day=request.url.path.rsplit("/",1)[1]; requested.append(day)
            opens = {"2026-10-05", "2026-10-01", "2026-10-08"}
            rows=[{"exchange":"NFO","start_time":int(at(day,"09:15").timestamp()*1000),"end_time":int(at(day,"15:40").timestamp()*1000)}] if day in opens else []
            return httpx.Response(200,json={"status":"success","data":rows})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            cal=await CalendarSource("fixture-token",client=client).fetch(at())
            assert cal.next_opens.date()==date(2026,10,8)
            assert cal.previous_opens.date()==date(2026,10,1)
            assert {"2026-10-04","2026-10-06","2026-10-07"}<=set(requested)
    asyncio.run(run())


def test_chart_requests_are_read_only_and_incomplete_rows_are_dropped():
    class Broker:
        async def _request(self, method, path, **kwargs):
            assert (method,path)==("POST","/charts/intraday")
            assert kwargs["json"]["interval"]=="1"
            return {"timestamp":[int(at().timestamp())],"open":["1"],"high":["1"],"low":["1"],"close":["1"],"volume":[1]}
    async def run():
        source=MinuteSource(Broker(),now_fn=lambda:at())
        assert await source.fetch("13","IDX_I","INDEX",at()-timedelta(days=1),at())=={}
    asyncio.run(run())


def test_bad_strategy_config_is_not_silently_ignored():
    assert strategy_names({})==(CAS,)
    assert strategy_names({"strategies":[GAP,REBOUND,CAS]})==(GAP,REBOUND,CAS)
    for value in ("ALL", [], ["typo"], [GAP,GAP]):
        with pytest.raises(ContractError): strategy_names({"strategies":value})


def test_route_window_requires_current_calendar_for_directional_engines():
    assert not route_window((GAP,),at(),None,False)
    assert route_window((GAP,),at(),calendar(),False)
    assert not route_window((CAS,),at(),calendar(),True)
    assert route_window((CAS,),at(clock="15:06"),calendar(),True)
    assert not route_window((CAS,),at(clock="15:06"),calendar(),False)
