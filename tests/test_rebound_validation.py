from datetime import timedelta
from types import SimpleNamespace

import pytest

from research.gauntlet.core import Bar, Contract, Order, D
from research.expiry.signals import stamp
from research.rebound_validation.data import signal, close_time, normalize
from research.rebound_validation.replay import trade


def bar(day, hm, price='10', volume=10000):
    p = D(price)
    return Bar(stamp(day, hm), p, p, p, p, volume, 10000)


def scenario(day='2026-07-30', next_day='2026-07-31'):
    c = Contract('x', 'NIFTY', '2026-08-04', 'CE', D('25000'), 65, D('.05'), 1300, True)
    o = Order(c, stamp(day, '15:10'), D('10.5'), 65, 'test', D('10'))
    s = {'day': day, 'exit_day': next_day, 'exit_at': stamp(next_day, '15:10').isoformat()}
    rows = {}
    for d in (day, next_day):
        at = stamp(d, '09:15')
        while at < close_time(d):
            b = bar(d, at.strftime('%H:%M'))
            rows[at] = b
            at += timedelta(minutes=1)
    ds = SimpleNamespace(days=[day, next_day], rows=lambda *_: rows)
    return ds, s, o, rows


def test_signal_ignores_uncompleted_and_future_extremes():
    d = '2026-07-30'
    rows = {stamp(d, '09:15'): bar(d, '09:15', '100'),
            stamp(d, '15:09'): bar(d, '15:09', '99.3'),
            stamp(d, '15:10'): bar(d, '15:10', '80')}
    assert signal(d, rows, '2026-07-31')['fires'] is False
    rows[stamp(d, '15:09')] = bar(d, '15:09', '99.25')
    assert signal(d, rows, '2026-07-31')['fires'] is True


def test_late_session_stop_is_monitored():
    ds, s, o, rows = scenario()
    rows[stamp(s['day'], '15:20')] = bar(s['day'], '15:20', '4')
    rows[stamp(s['day'], '15:22')] = bar(s['day'], '15:22', '3')
    result = trade(ds, s, o)
    assert result['reason'] == 'STOP_CLOSE'
    assert result['trigger_at'] == stamp(s['day'], '15:21').isoformat()
    assert result['exit_parts'][0]['at'] == stamp(s['day'], '15:22').isoformat()
    assert D(result['exit_parts'][0]['price']) == D('2.95')


def test_last_bar_trigger_latches_across_closed_session():
    ds, s, o, rows = scenario()
    rows[stamp(s['day'], '15:29')] = bar(s['day'], '15:29', '4')
    rows[stamp(s['exit_day'], '09:15')] = bar(s['exit_day'], '09:15', '2')
    result = trade(ds, s, o)
    assert result['reason'] == 'STOP_CLOSE'
    assert result['exit_parts'][0]['at'] == stamp(s['exit_day'], '09:15').isoformat()
    assert D(result['exit_parts'][0]['price']) < D('2')


def test_partial_exit_survives_overnight_without_reset():
    ds, s, o, rows = scenario()
    o = Order(o.contract, o.decided, o.limit, 130, o.signal_id, o.reference_close)
    rows[stamp(s['day'], '15:27')] = bar(s['day'], '15:27', '4')
    rows[stamp(s['day'], '15:29')] = bar(s['day'], '15:29', '3', 1300)
    result = trade(ds, s, o)
    assert [p['quantity'] for p in result['exit_parts']] == [65, 65]
    assert result['exit_parts'][1]['at'] == stamp(s['exit_day'], '09:15').isoformat()


def test_missing_late_holding_bar_is_unknown():
    ds, s, o, rows = scenario()
    del rows[stamp(s['day'], '15:20')]
    with pytest.raises(ValueError, match='UNKNOWN_HOLDING_BAR'):
        trade(ds, s, o)


def test_target_touch_is_not_a_completed_close_trigger():
    ds, s, o, rows = scenario()
    b = bar(s['day'], '15:20')
    rows[b.start] = Bar(b.start, D(10), D(40), D(9), D(10), b.volume, b.oi)
    assert trade(ds, s, o)['reason'] == 'TIMED_CLOSE'


def test_entry_limit_does_not_reprice_from_future_high():
    ds, s, o, rows = scenario()
    rows[stamp(s['day'], '15:11')] = bar(s['day'], '15:11', '12')
    assert trade(ds, s, o) == {'status': 'LIMIT_MISS'}


def test_zero_capacity_exit_remains_unknown():
    ds, s, o, rows = scenario()
    for hm in ('15:10', '15:11', '15:12'):
        rows[stamp(s['exit_day'], hm)] = bar(s['exit_day'], hm, volume=0)
    with pytest.raises(ValueError, match='UNKNOWN_EXIT_CAPACITY'):
        trade(ds, s, o)


def test_new_regime_monitors_through_1540():
    ds, s, o, rows = scenario('2026-08-03', '2026-08-04')
    rows[stamp(s['day'], '15:34')] = bar(s['day'], '15:34', '4')
    result = trade(ds, s, o)
    assert result['exit_parts'][0]['at'] == stamp(s['day'], '15:36').isoformat()


def test_unreconciled_tape_never_fills_missing_minutes():
    ds, s, o, rows = scenario()
    b = bar(s['day'], '09:15')
    out = normalize(o.contract, s['day'], [b], {'actual_volume': 100, 'expected_volume': 101})
    assert len(out) == 1
    out = normalize(o.contract, s['day'], [b], {'actual_volume': 100, 'expected_volume': 100})
    assert len(out) == 375
    assert out[stamp(s['day'], '15:29')].volume == 0
    assert out[stamp(s['day'], '15:29')].close == b.close


def test_conflicting_duplicate_observation_is_rejected():
    ds, s, o, rows = scenario()
    with pytest.raises(ValueError, match='CONFLICTING_DUPLICATE'):
        normalize(o.contract, s['day'], [bar(s['day'], '09:15'), bar(s['day'], '09:15', '11')],
                  {'actual_volume': 100, 'expected_volume': 100})


def test_rolling_contract_requires_exact_strike_and_valid_parallel_arrays():
    from research.rebound_validation.dhan_history import matching_rows
    at = int(stamp('2026-07-30', '15:10').timestamp())
    x = {'timestamp': [at, at+60], 'strike': [25000, 25050],
         'open': [10, 20], 'high': [10, 20], 'low': [10, 20], 'close': [10, 20],
         'volume': [100, 200], 'oi': [10000, 10000]}
    rows = matching_rows(x, D(25000))
    assert len(rows) == 1 and rows[0][4] == 10
    x['volume'] = [100]
    with pytest.raises(ValueError, match='PARALLEL_ARRAY_LENGTH'):
        matching_rows(x, D(25000))


def test_control_sampling_preserves_matching_strata_and_count():
    from research.rebound_validation.controls import sample_dates
    groups = {'a': ('earlier', 3, 0), 'b': ('earlier', 3, 0),
              'c': ('earlier', 5, 2), 'd': ('earlier', 5, 2), 'e': ('earlier', 5, 2)}
    selected = sample_dates(groups, ['a', 'c', 'd'], 7)
    assert len(selected) == 3
    assert sum(groups[d] == ('earlier', 3, 0) for d in selected) == 1
    assert sum(groups[d] == ('earlier', 5, 2) for d in selected) == 2
    assert selected == sample_dates(groups, ['a', 'c', 'd'], 7)


def test_control_volatility_bucket_never_reads_current_or_future_close():
    from datetime import date
    from research.rebound_validation.controls import matched_groups
    days = [(date(2026, 1, 1)+timedelta(days=i)).isoformat() for i in range(60)]
    rows = [[d+'T15:29:00+05:30', 1, 1, 1, 100+(i%7), 0, 0] for i,d in enumerate(days)]
    day = days[40]
    plan = {day: {'partition': 'validation', 'potential': {'exit_day': days[41]}}}
    contracts = {'|'.join((day, 'NIFTY', days[41], 'CE')): {'contracts': [{'expiry': days[44]}]}}
    groups, errors = matched_groups(plan, rows, contracts)
    assert not errors and day in groups
    for r in rows:
        if r[0][:10] >= day:
            r[4] = 100000
    assert matched_groups(plan, rows, contracts) == (groups, errors)


def test_unknown_contract_stops_bankroll_instead_of_skipping():
    from research.rebound_validation.replay import run
    d = '2026-07-30'
    s = {'day': d, 'exit_day': '2026-07-31', 'at': stamp(d, '15:10').isoformat()}
    ds = SimpleNamespace(plan={d: {'partition': 'recent', 'signals': {
        'NIFTY_SELLOFF_REBOUND_FULL_SESSION_V2': s}, 'errors': {}}}, contracts={}, provider='test')
    r = run(ds, 'recent')
    assert r['final_bankroll'] is None
    assert r['ledger'][0]['status'] == 'UNKNOWN'


def test_dated_fees_change_on_effective_dates():
    from research.rebound_validation.fees import schedule
    assert schedule('2026-03-31').sell_stt_rate == D('.001')
    assert schedule('2026-04-01').sell_stt_rate == D('.0015')
    a, b = schedule('2026-02-28'), schedule('2026-03-01')
    assert a.exchange_rate+a.ipft_rate == b.exchange_rate+b.ipft_rate
    assert a.ipft_rate > b.ipft_rate


def test_dated_order_matches_parent_when_fees_match():
    from research.rebound_validation.fees import make_order, schedule
    from research.expiry.fast_order import make_order as parent
    ds, s, o, rows = scenario()
    known = [rows[o.decided-timedelta(minutes=i)] for i in (3, 2, 1)]
    for cash in ('1', '680', '750', '9411.18', '40000'):
        assert make_order(o.contract, known, o.decided, D(cash), 'test', schedule(s['day'])) == parent(o.contract, known, o.decided, D(cash), 'test')


def test_dated_order_rejects_future_information():
    from research.rebound_validation.fees import make_order, schedule
    ds, s, o, rows = scenario()
    known = [rows[o.decided-timedelta(minutes=i)] for i in (2, 1, 0)]
    with pytest.raises(ValueError, match='FUTURE_OR_MISSING'):
        make_order(o.contract, known, o.decided, D('9411.18'), 'test', schedule(s['day']))
