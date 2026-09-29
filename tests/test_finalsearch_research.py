from datetime import timedelta
import pytest
from research.finalsearch.experiment import basket_order, trade, forecast, flow, choose
from research.gauntlet.core import Bar, Contract, Order, D
from research.expiry.signals import stamp

DAY = '2026-06-16'
AT = stamp(DAY, '15:15')

def contract(side='CE', strike='23000'):
    return Contract(side + strike, 'NIFTY', DAY, side, D(strike), 65, D('.05'), 1755, True)

def bar(at, price='10', high=None, low=None, volume=100000, oi=10000):
    p = D(price)
    return Bar(at, p, D(high or price), D(low or price), p, volume, oi)

def order(c):
    return Order(c, AT, D('10.50'), 65, 'test', D(10))

def full_tape(c, **kwargs):
    return {AT + timedelta(minutes=i): bar(AT + timedelta(minutes=i), **kwargs) for i in range(1, 13)}

def test_order_cannot_see_future_and_budget_reserves_exit_costs():
    cs = [contract(), contract('PE')]
    known = {c.key: [bar(AT - timedelta(minutes=i)) for i in (3, 2, 1)] for c in cs}
    orders, _ = basket_order(cs, known, AT, D('9411.18'))
    assert orders and len({o.quantity for o in orders}) == 1
    known[cs[0].key].append(bar(AT))
    with pytest.raises(ValueError, match='future'): basket_order(cs, known, AT, D('9411.18'))
    known = {cs[0].key: [bar(AT - timedelta(minutes=i), '.05') for i in (3, 2, 1)]}
    assert not basket_order(cs[:1], known, AT, D(50))[0]

def test_partial_entry_is_paid_unwind_not_free_no_trade():
    a, b = contract(), contract('PE'); tape = {a.key: full_tape(a), b.key: full_tape(b)}
    tape[b.key][AT + timedelta(minutes=1)] = bar(AT + timedelta(minutes=1), '12')
    result = trade([order(a), order(b)], tape, DAY, D('9411.18'))
    assert result['status'] == 'RESOLVED' and result['partial_entry']
    assert result['reason'] == 'PARTIAL_ENTRY_UNWIND'
    assert D(result['cash_after']) < D('9411.18') and len(result['fills']) == 1

def test_asynchronous_pair_highs_cannot_award_target():
    a, b = contract(), contract('PE'); tape = {a.key: full_tape(a), b.key: full_tape(b)}
    for c in (a, b): tape[c.key][AT + timedelta(minutes=3)] = bar(AT + timedelta(minutes=3), '10', high='100')
    result = trade([order(a), order(b)], tape, DAY, D('9411.18'))
    assert result['reason'] == 'TIMED_CLOSE'
    assert D(result['cash_after']) < D('9411.18')

def test_target_signal_is_not_credited_at_target_price():
    c = contract(); tape = {c.key: full_tape(c)}
    tape[c.key][AT + timedelta(minutes=2)] = bar(AT + timedelta(minutes=2), '22')
    result = trade([order(c)], tape, DAY, D('9411.18'))
    assert result['reason'] == 'COMPLETED_CLOSE_2X'
    assert result['exit_at'] == (AT + timedelta(minutes=4)).isoformat()
    assert D(result['cash_after']) < D('9411.18')

def test_missing_holding_and_exit_capacity_are_unknown():
    c = contract(); tape = {c.key: full_tape(c)}
    del tape[c.key][AT + timedelta(minutes=3)]
    assert trade([order(c)], tape, DAY, D('9411.18'))['status'] == 'UNKNOWN_HOLDING_BAR'
    tape[c.key] = full_tape(c)
    for i in (10, 11, 12): tape[c.key][AT + timedelta(minutes=i)] = bar(AT + timedelta(minutes=i), volume=0)
    assert trade([order(c)], tape, DAY, D('9411.18'))['status'] == 'UNKNOWN_EXIT_CAPACITY'

def test_forecast_uses_only_previous_sessions():
    spot = {}
    for i in range(1, 21):
        d = (AT - timedelta(days=i)).date().isoformat()
        spot[stamp(d, '15:15')] = bar(stamp(d, '15:14'), '23000')
        spot[stamp(d, '15:25')] = bar(stamp(d, '15:24'), '23010')
    assert forecast(spot, DAY, AT) == D(8)
    spot[stamp(DAY, '15:25')] = bar(stamp(DAY, '15:24'), '999999')
    assert forecast(spot, DAY, AT) == D(8)
    del spot[next(iter(spot))]
    with pytest.raises(ValueError, match='BASELINE'): forecast(spot, DAY, AT)

def test_strangle_uses_adjacent_common_strikes_without_outcome_selection():
    chain = [contract(side, str(k)) for side in ('CE', 'PE') for k in (22950, 23000, 23050)]
    assert [(c.side, c.strike) for c in choose(chain, D(23001), True)] == [('CE', D(23050)), ('PE', D(22950))]

def test_flow_requires_same_strike_history_and_is_future_invariant():
    c = contract(); spot = {AT - timedelta(minutes=i): bar(AT - timedelta(minutes=i+1), p) for i, p in [(2, '22999'), (1, '23001'), (0, '23002')]}
    tape = {c.key: {AT - timedelta(minutes=i+1): bar(AT - timedelta(minutes=i+1), '10', volume=1000, oi=10000) for i in range(33)}}
    for i in range(3): tape[c.key][AT-timedelta(minutes=i+1)] = bar(AT-timedelta(minutes=i+1), '13', volume=5000, oi=9000)
    assert flow([c], AT, spot, tape) == [c]
    tape[c.key][AT] = bar(AT, '99999', volume=0)
    assert flow([c], AT, spot, tape) == [c]
    del tape[c.key][AT-timedelta(minutes=5)]
    with pytest.raises(ValueError, match='OPTION'): flow([c], AT, spot, tape)
