"""Mandate negatives first; synthetic prices never establish an economic edge."""
from dataclasses import replace
from datetime import timedelta, date
from decimal import Decimal as D
import pytest
from tests.test_session_strategies import at, calendar
from dhan_cas_bot.session_strategies import Bar
from dhan_cas_bot.domain import Instrument, OptionType, Segment, OptionBook, Level
from dhan_cas_bot.volatility_shock import (
    SHOCK, ShockConfig, evaluate_completed_shock, shock_universe,
    select_shock_candidate, option_value, implied_volatility, shock_exit,
    shock_allocation, contract_cutoff,
)


def tapes():
    end=at(clock='10:00');spot={};future={}
    for n in range(45):
        t=end-timedelta(minutes=44-n)
        p=D(23000)+D(n%3)
        if n>=40:p+=D((n-39)*20)
        spot[t]=Bar(t,p,p,0,0,p+D(1),p-D(1))
        f=p+D(30)
        future[t]=Bar(t,f,f,300 if n>=42 else 100,1000,f+D(1),f-D(1))
    return end,spot,future


def signal():
    t,s,f=tapes()
    return evaluate_completed_shock(t+timedelta(seconds=2),calendar(),s,f,bar_at=t)


def book(strike=D(23100),ask=D('20'),bid=D('19.9'),sid='s',expiry=date(2026,10,13)):
    i=Instrument(sid,'NIFTY',Segment.NSE_FNO,expiry,OptionType.CE,strike,65,D('.05'),1800)
    return OptionBook(i,(Level(bid,650),),(Level(ask,650),),'e',int((at(clock='10:00')+timedelta(seconds=2)).timestamp()*1e9))


def test_completed_shock_is_causal_and_no_option_history_is_required():
    s=signal()
    assert s.state=='SIGNAL' and s.side=='CE'
    assert s.details['rule_version']=='shock_v1'
    t,spot,fut=tapes()
    spot[t+timedelta(minutes=1)]=replace(spot[t],available=t+timedelta(minutes=1),close=D(99999))
    assert evaluate_completed_shock(t+timedelta(seconds=2),calendar(),spot,fut,bar_at=t)==s


@pytest.mark.parametrize('fault',['gap','future_gap','zero_baseline','zero_volume','late','calendar','forming'])
def test_unusable_inputs_never_manufacture_signal(fault):
    t,s,f=tapes();now=t+timedelta(seconds=2);cal=calendar()
    if fault=='gap':s.pop(t-timedelta(minutes=10))
    if fault=='future_gap':f.pop(t-timedelta(minutes=10))
    if fault=='zero_baseline':
        s={k:replace(v,open=D(23000),close=D(23000),high=D(23000),low=D(23000)) for k,v in s.items()}
    if fault=='zero_volume':f={k:replace(v,volume=0) for k,v in f.items()}
    if fault=='late':now=t+timedelta(seconds=31)
    if fault=='calendar':cal=None
    if fault=='forming':now=t-timedelta(seconds=1)
    assert evaluate_completed_shock(now,cal,s,f,bar_at=t).state!='SIGNAL'


def test_scoped_full_capital_does_not_change_legacy_policy():
    from dhan_cas_bot.risk import Allocation
    a=Allocation.start(D(100000),D(100000))
    assert a.ceiling==D(25000)
    b=shock_allocation(a)
    assert b.ceiling==D(100000) and b.remaining==D(100000)
    assert Allocation.start(D(100000),D(100000)).ceiling==D(25000)


@pytest.mark.parametrize('fault',['spread','stale','no_bid_depth','cash','expired','future_time','crossed'])
def test_unfillable_book_is_rejected(fault):
    b=book();now=at(clock='10:00')+timedelta(seconds=2);cash=D(7772)
    if fault=='spread':b=replace(b,bids=(Level(D(18),650),))
    if fault=='stale':now+=timedelta(seconds=5)
    if fault=='no_bid_depth':b=replace(b,bids=(Level(D('19.9'),1),))
    if fault=='cash':cash=D(20)
    if fault=='expired':b=replace(b,instrument=replace(b.instrument,expiry=now.date()-timedelta(days=1)))
    if fault=='future_time':b=replace(b,received_ns=b.received_ns+10_000_000_000)
    if fault=='crossed':b=replace(b,bids=(Level(D(21),650),))
    c,checks=select_shock_candidate(signal(),[b.instrument],{b.instrument.security_id:b},cash,now,calendar())
    assert c is None and checks


def test_iv_roundtrip_and_impossible_quotes():
    p=option_value(D(23000),D(23100),D('.02'),D('.25'),'CE')
    iv=implied_volatility(D(23000),D(23100),D('.02'),p,'CE')
    assert abs(iv-D('.25'))<D('.000001')
    with pytest.raises(ValueError):implied_volatility(D(23000),D(22000),D('.02'),D(1),'CE')
    assert option_value(D(23000),D(23100),D(0),D('.25'),'CE')==0
    assert abs(option_value(D(100),D(100),D(1),D('.2'),'CE')-D('7.9655674554'))<D('.000001')
    call=option_value(D(102),D(100),D('.2'),D('.3'),'CE')
    put=option_value(D(102),D(100),D('.2'),D('.3'),'PE')
    assert abs(call-put-D(2))<D('.00000001')


def test_candidate_uses_max_affordable_whole_lots_and_current_two_tick_cap():
    b=book();now=at(clock='10:00')+timedelta(seconds=2)
    c,checks=select_shock_candidate(signal(),[b.instrument],{'s':b},D(7772),now,calendar())
    assert c and c.quantity%65==0 and c.entry_cash+c.exit_reserve<=D(7772)
    assert D(20)<=c.limit<=D('20.08')
    from dhan_cas_bot.risk import worst_case_entry_cash,FeeSchedule
    q=c.quantity+65
    assert worst_case_entry_cash(q,c.limit)+FeeSchedule().sell(q*max(c.limit,D(c.assumptions['scenario_premium'])),3)>D(7772)
    assert c.assumptions['scenario_only'] and c.scenario_multiple>=D('1.8')


def test_two_expiries_and_twelve_otm_candidates_come_from_listed_strikes():
    rows=[]
    for expiry in (date(2026,10,6),date(2026,10,13),date(2026,10,20)):
        for n in range(-5,21):rows.append(replace(book().instrument,security_id=f'{expiry}-{n}',expiry=expiry,strike=D(23000+n*50)))
    found=shock_universe(rows,'CE',D(23000),date(2026,10,5))
    assert len(found)==30 and {i.expiry for i in found}=={date(2026,10,6),date(2026,10,13)}
    assert min(i.strike for i in found)==D(22900) and max(i.strike for i in found)==D(23600)


def test_put_rule_is_symmetric_and_current_candidate_can_be_selected():
    t,s,f=tapes()
    def mirror(rows):
        return {k:replace(v,open=D(46000)-v.open,close=D(46000)-v.close,
            high=D(46000)-v.low,low=D(46000)-v.high) for k,v in rows.items()}
    evaluation=evaluate_completed_shock(t+timedelta(seconds=2),calendar(),mirror(s),mirror(f),bar_at=t)
    assert evaluation.state=='SIGNAL' and evaluation.side=='PE'
    b=book(strike=D(22900));b=replace(b,instrument=replace(b.instrument,option_type=OptionType.PE))
    selected,_=select_shock_candidate(evaluation,[b.instrument],{'s':b},D(7772),t+timedelta(seconds=2),calendar())
    assert selected and selected.instrument.option_type==OptionType.PE


def test_shock_worker_routes_without_legacy_expanded_rules(tmp_path):
    from tests.test_shock_engine import setup
    from dhan_cas_bot.strategy_inputs import StrategyInputWorker
    import asyncio
    e,b,l,c,i=setup(tmp_path)
    worker=StrategyInputWorker(e.directional,'fixture','f',wake=asyncio.Event(),stop=asyncio.Event())
    worker.calendar=i.calendar
    worker.expanded=lambda *a,**k:(_ for _ in ()).throw(AssertionError('wrong expanded dispatcher'))
    result=worker.evaluations(c[0].replace(second=0),i.spot_bars,i.future_bars,{book().instrument.expiry},{})
    assert result[SHOCK].state=='SIGNAL'


def test_expiry_universe_subscription_keeps_held_contract_without_full_chain():
    from dhan_cas_bot.market_subscriptions import market_ids
    rows={str(n):replace(book().instrument,security_id=str(n),strike=D(21000+n*50)) for n in range(100)}
    desired=market_ids(rows,date(2026,10,5),anchors=[D(23000)],held=['held'],shock=True)
    assert 'held' in desired and len(desired)<40


def test_exit_ratchet_persists_and_no_generic_double_target():
    state,reason=shock_exit(D(1000),D(1000),0,None,False)
    assert reason is None  # +100% profit is not a fixed take-profit.
    next_state,reason=shock_exit(D(1000),D(500),1,state,False)
    assert next_state['peak_net_profit']=='1000' and reason=='SHOCK_PROFIT_FLOOR'
    assert shock_exit(D(1000),D(-401),1,None,False)[1]=='SHOCK_PREMIUM_STOP'
    assert shock_exit(D(1000),None,121,{'peak_net_profit':'300'},False)[1]=='SHOCK_MAX_EXPOSURE'
    assert shock_exit(D(1000),D(50),46,None,False)[1]=='SHOCK_NO_MOMENTUM'
    assert shock_exit(D(1000),D(-10),2,None,True)[1]=='SHOCK_UNDERLYING_INVALIDATED'


def test_cutoff_is_contract_and_effective_date_specific():
    from datetime import datetime
    from dhan_cas_bot.session_strategies import IST
    day=date(2026,12,8)
    cal=replace(calendar(),opens=datetime(2026,12,8,9,15,tzinfo=IST),closes=datetime(2026,12,8,15,45,tzinfo=IST))
    b=book(expiry=day)
    assert contract_cutoff(b.instrument,cal).hour==15
    assert contract_cutoff(b.instrument,cal).minute==30
    assert contract_cutoff(replace(b.instrument,expiry=date(2026,12,15)),cal).minute==45
