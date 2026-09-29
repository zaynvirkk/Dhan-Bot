from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace

import pytest

from research.gauntlet.core import Bar, Contract, Order, D
from research.expiry.signals import stamp
from research.execution_frontier.replay import direction, fill, order_for, prior_trends, run, trade


def fixture():
    at = stamp('2026-07-30', '15:10')
    c = Contract('x', 'NIFTY', '2026-08-04', 'CE', D(25000), 65, D('.05'), 1300, True)
    o = Order(c, at, D('10.5'), 65, 'test', D(10))
    rows = {}
    for i in range(-3, 7):
        t = at+timedelta(minutes=i)
        rows[t] = Bar(t, D(10), D(11), D(10), D(10), 10000, 10000)
    return o, rows


def test_future_high_cannot_erase_resting_limit_fill():
    o, rows = fixture()
    at = o.decided+timedelta(minutes=1)
    rows[at] = replace(rows[at], high=D(100))
    r = fill(o, rows)
    assert r['price'] == o.limit
    assert r['at'] == at+timedelta(minutes=1)


def test_touch_and_one_tick_penetration_do_not_credit_fill():
    o, rows = fixture()
    for n in (1, 2, 3):
        at = o.decided+timedelta(minutes=n)
        rows[at] = replace(rows[at], open=D('10.5'), close=D('10.5'), low=D('10.45'))
    assert fill(o, rows)['status'] == 'LIMIT_DEADLINE_MISS'


def test_deadline_precedes_later_cheap_price():
    o, rows = fixture()
    for n in (1, 2, 3):
        at = o.decided+timedelta(minutes=n)
        rows[at] = replace(rows[at], open=D(11), high=D(12), low=D(11), close=D(11))
    assert fill(o, rows)['status'] == 'LIMIT_DEADLINE_MISS'


def test_possible_partial_fill_is_unknown_not_a_miss():
    o, rows = fixture()
    at = o.decided+timedelta(minutes=1)
    rows[at] = replace(rows[at], volume=100)
    with pytest.raises(ValueError, match='UNKNOWN_PARTIAL_ENTRY'): fill(o, rows)


def test_open_model_does_not_retry_on_a_later_low():
    o, rows = fixture()
    at = o.decided+timedelta(minutes=1)
    rows[at] = replace(rows[at], open=D(11))
    assert fill(o, rows, entry_model='open')['status'] == 'LIMIT_DEADLINE_MISS'
    assert fill(o, rows)['status'] == 'MODELED_FILL'


def test_decision_excludes_future_prices():
    o, rows = fixture()
    known = [rows[o.decided-timedelta(minutes=n)] for n in (3, 2, 1)]
    known[-1] = rows[o.decided]
    with pytest.raises(ValueError, match='FUTURE_OR_STALE'):
        order_for(o.contract, known, o.decided, D(9411), D('.95'), D('.05'))


@pytest.mark.parametrize('allocation', [D('.25'), D('.50'), D('.95')])
def test_whole_lot_allocation_includes_fees(allocation):
    from research.rebound_validation.fees import schedule
    from math import ceil
    o, rows = fixture()
    known = [rows[o.decided-timedelta(minutes=n)] for n in (3, 2, 1)]
    r, _ = order_for(o.contract, known, o.decided, D('9411.18'), allocation, D('.05'))
    turn = r.quantity*r.limit
    assert r.quantity % r.contract.lot == 0
    assert turn+schedule('2026-07-30').buy(turn, ceil(r.quantity/r.contract.freeze)) <= D('9411.18')*allocation


def test_calls_puts_and_regimes_are_symmetric():
    assert direction('SELLOFF_PUT', D('-.01'), None) == 'PE'
    assert direction('RALLY_CALL', D('.01'), None) == 'CE'
    assert direction('TWO_SIDED_REVERSAL', D('.01'), None) == 'PE'
    assert direction('TREND_PULLBACK', D('-.01'), D('.02')) == 'CE'
    assert direction('TREND_PULLBACK', D('-.01'), D('-.02')) is None
    assert direction('TREND_CONTINUATION', D('-.01'), D('-.02')) == 'PE'


def test_trend_never_uses_today_or_future_close():
    from datetime import date
    rows = []
    for i in range(24):
        d = (date(2026, 1, 1)+timedelta(days=i)).isoformat()
        rows.append([stamp(d, '15:29').isoformat(), 100+i, 100+i, 100+i, 100+i, 1, 1])
    baseline = prior_trends(rows)['2026-01-22']
    for r in rows[21:]: r[1:5] = [99999]*4
    assert prior_trends(rows)['2026-01-22'] == baseline


def test_entry_bar_cannot_supply_an_earlier_stop():
    o, rows = fixture()
    at = o.decided+timedelta(minutes=1)
    rows[at] = replace(rows[at], low=D(1), close=D(1))
    s = {'day': '2026-07-30', 'exit_day': '2026-07-30', 'exit_at': stamp('2026-07-30','15:15').isoformat()}
    ds = SimpleNamespace(days=['2026-07-30'], rows=lambda *_: rows)
    r = trade(ds, s, o)
    assert r['reason'] == 'TIMED_CLOSE'
    assert r['entry_at'] == stamp('2026-07-30','15:12').isoformat()


def test_unknown_exposure_stops_all_later_signals():
    s = {'at':stamp('2026-07-30','15:10').isoformat(), 'day':'2026-07-30', 'exit_day':'2026-07-31',
         'detail': {'session_return':'-.01'}}
    ds = SimpleNamespace(plan={'2026-07-30':{'partition':'recent','errors':{},'potential':s}}, contracts={}, provider='fixture')
    r = run(ds, {}, 'recent', 'SELLOFF_CALL', D('.95'))
    assert r['final_bankroll'] is None
    assert r['unknown'][1].endswith('UNKNOWN_CONTRACT_SELECTION')


def overnight_fixture():
    from research.rebound_validation.data import close_time
    o, rows = fixture()
    for day in ('2026-07-30','2026-07-31'):
        at=stamp(day,'09:15')
        while at<close_time(day):
            rows[at]=Bar(at,D(10),D(11),D(10),D(10),10000,10000)
            at+=timedelta(minutes=1)
    s={'day':'2026-07-30','exit_day':'2026-07-31','exit_at':stamp('2026-07-31','15:10').isoformat()}
    return SimpleNamespace(days=['2026-07-30','2026-07-31'], rows=lambda *_:rows),s,o,rows


def test_resting_entry_retains_last_minute_stop_overnight():
    ds,s,o,rows=overnight_fixture()
    at=stamp(s['day'],'15:29')
    rows[at]=Bar(at,D(4),D(4),D(4),D(4),10000,10000)
    r=trade(ds,s,o)
    assert r['reason']=='STOP_CLOSE'
    assert r['exit_parts'][0]['at']==stamp(s['exit_day'],'09:15').isoformat()


def test_unknown_post_fill_minute_cannot_be_relabelled_no_trade():
    ds,s,o,rows=overnight_fixture()
    del rows[stamp(s['day'],'15:29')]
    with pytest.raises(ValueError,match='UNKNOWN_HOLDING_BAR'):
        trade(ds,s,o)
