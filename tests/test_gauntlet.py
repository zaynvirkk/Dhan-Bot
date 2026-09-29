from datetime import datetime,timedelta
from decimal import Decimal as D
import pytest
from research.gauntlet.core import Bar,Contract,snapshot,make_order,entry,cash_after,exit_trade
from research.gauntlet.signals import event_rule,forced_rule,scheduled_vol_rule

T=datetime.fromisoformat('2026-07-21T10:00:00+05:30')
C=Contract('NSE_FO|1|28-07-2026','X','2026-07-28','CE',D(100),50,D('.05'),500,True)
def bar(i,price='10',volume=20000,oi=10000,high=None,low=None):
    p=D(price)
    return Bar(T+timedelta(minutes=i),p,D(high or price),D(low or price),p,volume,oi)

def order():
    return make_order(C,[bar(-3),bar(-2),bar(-1)],T,D('9411.18'),'signal')[0]

def test_incomplete_bar_is_not_knowledge():
    assert snapshot([bar(-1),bar(0)],T)==(bar(-1),)
    with pytest.raises(ValueError):make_order(C,[bar(0)],T,D(9000),'future')

def test_future_perturbation_cannot_change_order():
    a=[bar(-3),bar(-2),bar(-1),bar(0),bar(1)]
    b=a[:3]+[bar(0,'1000'),bar(1,'0.01')]
    assert make_order(C,snapshot(a,T),T,D('9411.18'),'s')==make_order(C,snapshot(b,T),T,D('9411.18'),'s')

def test_quantity_whole_lots_and_cash_including_fees():
    o=order();assert o.quantity%50==0
    from dhan_cas_bot.risk import FeeSchedule
    spend=o.limit*o.quantity
    assert spend+FeeSchedule().buy(spend,2)<=D('9411.18')*D('.95')

def test_high_above_limit_misses_without_resizing():
    o=order();n=o.quantity
    assert entry(o,[bar(1,high='20')])['status']=='MODELED_LIMIT_MISS'
    assert o.quantity==n

def test_low_next_volume_cannot_retroactively_reduce_quantity():
    assert entry(order(),[bar(1,volume=10)])['status']=='MODELED_CAPACITY_MISS'

def test_missing_tape_is_unknown():
    assert entry(order(),[])['status']=='UNKNOWN_ENTRY_BAR'

def test_stock_expiry_block():
    c=Contract('x','x','2026-07-21','CE',D(100),50,D('.05'),500,False)
    assert make_order(c,[bar(-3),bar(-2),bar(-1)],T,D(9000),'x')[1]=='DHAN_STOCK_EXPIRY_BLOCK'

def test_target_not_credited_in_entry_bar():
    o=order();fill=entry(o,[bar(1)])
    result=exit_trade(o,fill,[bar(1,high='30'),bar(2),bar(3)],None,T+timedelta(minutes=3))
    assert result['reason']=='TIMED_CLOSE'

def test_missing_holding_bar_invalidates_path():
    o=order();fill=entry(o,[bar(1)])
    result=exit_trade(o,fill,[bar(3,high='30')],None,T+timedelta(minutes=3))
    assert result['status']=='UNKNOWN_HOLDING_BAR'

def test_flat_premium_loses_real_fees():
    cash,fees=cash_after(D('9411.18'),order(),D(10),D(10))
    assert fees>0 and cash==D('9411.18')-fees

def test_invalidation_deadline_is_not_postponed_by_later_bars():
    o=order();fill=entry(o,[bar(1)])
    result=exit_trade(o,fill,[bar(i) for i in range(2,11)],T+timedelta(minutes=3),T+timedelta(minutes=10),liquidate_minutes=2)
    assert result['reason']=='INVALIDATION'
    assert result['time']==(T+timedelta(minutes=4)).isoformat()

def test_partial_liquidation_preserves_unfilled_remainder():
    o=order();fill=entry(o,[bar(1)])
    result=exit_trade(o,fill,[bar(i,volume=1000) for i in range(2,6)],None,T+timedelta(minutes=5),liquidate_minutes=3)
    assert result['status']=='UNKNOWN_EXIT_CAPACITY'
    assert result['remaining']==o.quantity-200

def test_invalidation_known_at_entry_completion_is_not_delayed_again():
    o=order();fill=entry(o,[bar(1)])
    result=exit_trade(o,fill,[bar(i) for i in range(2,11)],T+timedelta(minutes=2),T+timedelta(minutes=10),liquidate_minutes=2)
    assert result['time']==(T+timedelta(minutes=3)).isoformat()
    assert result['reason']=='INVALIDATION'

def test_ambiguous_target_and_invalidation_is_not_credited_as_winner():
    o=order();fill=entry(o,[bar(1)])
    result=exit_trade(o,fill,[bar(2,high='30'),bar(3),bar(4)],T+timedelta(minutes=3),T+timedelta(minutes=4))
    assert result['reason']=='INVALIDATION'
    assert result['price']==D(10)

def test_event_persistence_needs_contiguous_completed_bars():
    good=[bar(-3,'104'),bar(-2,'105'),bar(-1,'106')]
    assert event_rule(good,D(100),D(101),D(4),D(106),1)
    assert not event_rule([good[0],bar(-7,'105'),good[2]],D(100),D(101),D(4),D(106),1)

def test_vol_model_cannot_know_late_calendar_or_use_insufficient_prior_events():
    assert not scheduled_vol_rule(T+timedelta(seconds=1),T,T+timedelta(minutes=30),D(1),D(100),[.1]*8)
    assert not scheduled_vol_rule(T,T,T+timedelta(minutes=30),D(1),D(100),[.1]*7)

def test_option_download_batch_does_not_expose_other_days():
    from research.gauntlet.option_history import split_rows,plan_ranges
    rows=[['2026-07-21T10:00:00+05:30',1,1,1,1,100,100],['2026-07-22T10:00:00+05:30',99,99,99,99,100,100]]
    result=split_rows(rows,['2026-07-21'])
    assert result=={'2026-07-21':[rows[0]]}
    jobs=[{'contract_key':'a','day':d} for d in ('2026-07-01','2026-07-28','2026-07-29')]
    assert len(plan_ranges(jobs))==2
    with pytest.raises(ValueError):split_rows([rows[0],[rows[0][0],2,2,2,2,100,100]],['2026-07-21'])

def test_no_trade_gap_repair_requires_exact_exchange_volume(monkeypatch):
    from research.gauntlet import tape,contracts
    monkeypatch.setattr(contracts,'previous_session',lambda day:'2026-07-20')
    monkeypatch.setattr(tape,'record',lambda key,day:('10',1000,50,2,1) if day=='2026-07-21' else ('9',900,50,0,0))
    rows=[['2026-07-21T10:00:00+05:30',10,10,10,10,100,1000]]
    fixed,audit=tape.normalize('NSE_FO|1','2026-07-21',rows)
    assert audit['status']=='EXACT_DAILY_VOLUME_RECONCILED'
    assert sum(r[5] for r in fixed)==100
    assert fixed[0][4]=='9'  # only prior-session information before first trade
    assert fixed[0][5:]==[0,900]
    bad=[rows[0][:5]+[50,1000]]
    unchanged,audit=tape.normalize('NSE_FO|1','2026-07-21',bad)
    assert audit['status']=='UNKNOWN_VOLUME_MISMATCH' and unchanged==bad

def test_exact_contract_lookup_skips_futures_without_strikes(monkeypatch):
    from research.gauntlet import contracts
    monkeypatch.setattr(contracts,'previous_session',lambda day:'2026-07-20')
    monkeypatch.setattr(contracts,'exchange_contracts',lambda day:[
        {'FinInstrmTp':'STF','StrkPric':''},
        {'FinInstrmTp':'IDO','FinInstrmId':'1','XpryDt':'2026-07-28',
         'NewBrdLotQty':'50','TckrSymb':'X','OptnTp':'CE','StrkPric':'100'},
    ])
    c=contracts.exact_signal_contract({'at':T.isoformat(),'contract_key':'NSE_FO|1|28-07-2026'})
    assert c.key==C.key and c.strike==D(100)

def test_report_cannot_present_unresolved_holding_as_terminal_cash():
    from research.report import unresolved_path
    result={'status':'UNKNOWN_COVERAGE','ledger':[
        {'status':'MODELED_ROUND_TRIP'},
        {'status':'UNKNOWN_EXIT_CAPACITY','entry':{'status':'MODELED_FILL'}},
    ]}
    assert unresolved_path(result)
    result['ledger'][-1]={'status':'UNKNOWN_DATA_ERROR','entry':{'status':'MODELED_FILL'}}
    assert unresolved_path(result)
    result['ledger'][-1]={'status':'NO_ORDER_UNDER_MODEL'}
    assert not unresolved_path(result)
