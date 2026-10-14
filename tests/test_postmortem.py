from decimal import Decimal as D
from research.postmortem import exit_scenario,session_stop


def quote(t,bid,qty=65):return {'received_ns':t*10**9,'bid':[[bid,qty]]}


def test_exit_cannot_fill_at_trigger_quote_before_latency():
    rows=[quote(1,'130'),quote(2,'110'),quote(3,'105'),quote(4,'109')]
    r=exit_scenario(rows,65,D('100'),1*10**9,5*10**9,D('.5'),2)
    assert r['trigger_ns']==2*10**9 and r['arrival_ns']==4*10**9
    assert r['status']=='LIMIT_MISS'  # trigger bid110 minus0.10, arrival109


def test_later_peak_does_not_change_earlier_exit_decision():
    rows=[quote(1,'130'),quote(2,'110'),quote(3,'110')]
    a=exit_scenario(rows,65,D('100'),1*10**9,5*10**9,D('.5'),1)
    b=exit_scenario(rows+[quote(4,'1000')],65,D('100'),1*10**9,5*10**9,D('.5'),1)
    assert a==b


def test_pre_entry_profit_and_thin_depth_cannot_create_protection():
    rows=[quote(1,'1000'),quote(2,'120',1),quote(3,'95')]
    r=exit_scenario(rows,65,D('100'),2*10**9,4*10**9,D('.5'),1)
    assert r['status']=='NO_PROFIT_TRIGGER'


def test_unknown_quote_after_latency_is_not_an_invented_fill():
    rows=[quote(1,'130'),quote(2,'110'),quote(20,'110')]
    r=exit_scenario(rows,65,D('100'),1*10**9,25*10**9,D('.5'),1)
    assert r['status']=='UNKNOWN_ARRIVAL_QUOTE'


def test_session_floor_uses_only_closed_results_and_stays_latched():
    r=session_stop([D(100),D(-30),D(1000)],D('.75'))
    assert r=={'closed_through':2,'net':'70','floor':'75.00','stopped':True}

