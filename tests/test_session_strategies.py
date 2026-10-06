"""Information boundaries and calendar rules; all provider responses are fixtures."""
from datetime import date, datetime, timedelta
from decimal import Decimal as D

import pytest

from dhan_cas_bot.domain import ContractError
from dhan_cas_bot.session_strategies import (
    IST, GAP, REBOUND, Bar, Calendar, evaluate, parse_bars, parse_session,
)


def at(day="2026-10-05", clock="09:45"):
    return datetime.fromisoformat(f"{day}T{clock}:00").replace(tzinfo=IST)


def calendar(day="2026-10-05", next_day="2026-10-06"):
    return Calendar(at(day, "09:15"), at(day, "15:40"),
                    at("2026-10-01", "09:15"), at("2026-10-01", "15:40"),
                    at(next_day, "09:15"), at(next_day, "15:40"), at(day, "09:00"))


def bars(now=None, prices=("24820", "24840", "24860")):
    now = now or at()
    out = {at(clock="09:16"): Bar(at(clock="09:16"), D("24750"), D("24750"), 100, 1000)}
    out[at("2026-10-01", "15:40")] = Bar(at("2026-10-01", "15:40"), D("25000"), D("25000"), 100, 1000)
    for i, price in zip((2, 1, 0), prices):
        t = now - timedelta(minutes=i)
        out[t] = Bar(t, D(price), D(price), 100, 1000)
    return out


def futures(now=None):
    now = now or at()
    return {t: Bar(t, D(p), D(p), 100, 1000) for t, p in
            [(now-timedelta(minutes=5), "25000"), (now, "25050")]}


def test_missing_calendar_is_unknown_not_a_closed_day():
    result = evaluate(GAP, at(), None, bars(), futures(), {date(2026, 10, 6)})
    assert result.state == "UNKNOWN" and result.side is None


def test_monday_gap_can_signal_and_nonstandard_expiry_comes_from_metadata():
    r = evaluate(GAP, at(), calendar(), bars(), futures(), {date(2026, 10, 8)})
    assert r.state == "SIGNAL" and r.side == "CE"
    r = evaluate(GAP, at(), calendar(), bars(), futures(), {date(2026, 10, 5)})
    assert r.reason == "EXPIRY_SESSION_OUTSIDE_RESEARCH_SCOPE" and r.side is None


def test_future_or_missing_minute_cannot_supply_a_signal():
    spot = bars()
    del spot[at()]
    spot[at()+timedelta(minutes=1)] = Bar(at()+timedelta(minutes=1), D(24890), D(24890), 100, 1000)
    assert evaluate(GAP, at(), calendar(), spot, futures(), {date(2026,10,6)}).state == "UNKNOWN"
    assert evaluate(GAP, at(clock="09:46"), calendar(), bars(), futures(), {date(2026,10,6)}).side is None


def test_bar_timestamp_is_start_and_unfinished_bar_is_excluded():
    payload = {"timestamp": [int(at(clock="09:44").timestamp()), int(at(clock="09:45").timestamp())],
               "open": ["10", "11"], "high": ["10", "12"], "low": ["9", "10"],
               "close": ["10", "11"], "volume": [100, 200], "open_interest": [1000, 1100]}
    result = parse_bars(payload, at()+timedelta(seconds=5))
    assert list(result) == [at()]
    payload["volume"] = [100]
    with pytest.raises(ContractError): parse_bars(payload, at())


def test_malformed_calendar_never_looks_like_a_holiday():
    for payload in ({}, {"status":"error", "data":[]}, {"status":"success", "data":{}}):
        with pytest.raises(ContractError): parse_session(payload, date(2026,10,5))
    assert parse_session({"status":"success", "data":[]}, date(2026,10,5)) is None
    payload = {"status":"success", "data":[{"exchange":"NFO", "start_time":int(at().timestamp()*1000),
                                            "end_time":int(at("2026-10-06").timestamp()*1000)}]}
    with pytest.raises(ContractError): parse_session(payload, date(2026,10,5))


def test_rebound_uses_completed_1510_bar_and_next_actual_session():
    now = at("2026-10-06", "15:10")
    cal = calendar("2026-10-06", "2026-10-08")
    spot = {at("2026-10-06", "09:16"): Bar(at("2026-10-06", "09:16"), D(25000), D(25000), 0, 0),
            now: Bar(now, D(24800), D(24800), 0, 0)}
    r = evaluate(REBOUND, now, cal, spot, {}, {date(2026,10,6), date(2026,10,13)})
    assert r.side == "CE" and r.exit_at == at("2026-10-08", "15:10")
    assert r.minimum_expiry == date(2026,10,9)
    assert evaluate(REBOUND, now+timedelta(minutes=1), cal, spot, {}, {date(2026,10,13)}).side is None

