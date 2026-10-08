"""Displayed condition evidence must explain, never modify, trading decisions."""
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal as D

from dhan_cas_bot.session_strategies import GAP, REBOUND, Bar, evaluate
from tests.test_session_strategies import at, calendar, bars, futures


def conditions(result):
    return {c['key']:c for c in result.conditions}


def test_no_signal_identifies_actual_failure_values_and_thresholds():
    spot=bars(prices=('24860','24840','24820'))
    result=evaluate(GAP,at(),calendar(),spot,futures(),{date(2026,10,6)})
    assert result.state=='NO_SIGNAL' and result.side is None
    checks=conditions(result)
    assert checks['gap_size']['state']=='PASS'
    assert checks['gap_size']['value']=='-0.01'
    assert checks['gap_size']['minimum']=='0.005'
    assert checks['persistence']['state']=='FAIL'
    assert checks['futures_direction']['state']=='PASS'
    assert result.next_check_at==at(clock='09:50')


def test_missing_future_does_not_erase_known_gap_or_appear_as_zero():
    result=evaluate(GAP,at(),calendar(),bars(),{}, {date(2026,10,6)})
    checks=conditions(result)
    assert result.state=='UNKNOWN'
    assert checks['gap_size']['state']=='PASS'
    assert checks['futures_direction']['state']=='UNKNOWN'
    assert checks['futures_direction']['value'] is None


def test_preview_between_scheduled_checks_does_not_emit_a_signal():
    now=at(clock='09:46')
    result=evaluate(GAP,now,calendar(),bars(now),futures(now),{date(2026,10,6)})
    assert result.state=='WAITING' and result.side is None
    assert all(c['state']=='PASS' for c in result.conditions)
    assert result.next_check_at==at(clock='09:50')


def test_selloff_displays_distance_from_threshold_without_becoming_signal():
    now=at(clock='15:10')
    spot=bars(now,prices=('24670','24660','24650'))
    result=evaluate(REBOUND,now,calendar(),spot,{}, {date(2026,10,13)})
    assert result.state=='NO_SIGNAL'
    check=conditions(result)['selloff']
    assert check['maximum']=='-0.0075'
    assert D(check['value'])>D(check['maximum']) and check['state']=='FAIL'
    assert result.next_check_at==at('2026-10-06','15:10')


def test_explanation_does_not_use_future_or_previous_minute_as_current():
    spot=bars()
    spot[at()+timedelta(minutes=1)]=spot.pop(at())
    result=evaluate(GAP,at(),calendar(),spot,futures(),{date(2026,10,6)})
    assert conditions(result)['gap_fill']['value'] is None
    assert conditions(result)['gap_fill']['state']=='UNKNOWN'


def test_unknown_calendar_cannot_invent_next_check():
    result=evaluate(GAP,at(),None,bars(),futures(),{date(2026,10,6)})
    assert result.next_check_at is None
    assert all(c['state']=='UNKNOWN' for c in result.conditions)
