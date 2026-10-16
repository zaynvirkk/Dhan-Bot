"""Live-exposed counterexamples; synthetic fixtures do not prove trading returns."""
import asyncio
import json
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal as D

from dhan_cas_bot.risk import FeeSchedule
from dhan_cas_bot.domain import Level
from dhan_cas_bot.strategy_arbiter import execution_score, scores
from tests.test_execution_feedback import receipt
from tests.test_session_strategies import at


def test_feedback_counts_filled_orders_not_zero_fill_exit_retries(tmp_path):
    from dhan_cas_bot.ledger import Ledger
    ledger=Ledger(tmp_path/'ledger.sqlite3');now=at(clock='11:00')
    for n in range(3):
        name='closed'+str(n);stamp=now-timedelta(minutes=n+2)
        receipt(ledger,name,stamp,requested=100,filled=100)
        for k in range(3):
            ident=name+'retry'+str(k)
            ledger.db.execute('INSERT INTO intents VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                (ident,ident,name,'SELL','101',100,'12','CANCELLED','0','{}',stamp.isoformat()))
            ledger.db.execute('INSERT INTO attempts VALUES(?,?,?,?,?)',(ident,ident,stamp.isoformat(),'ACK','{}'))
    row=scores(ledger,now)['OPEN_DRIVE_FAST']
    assert D(row['mean_filled_buy_orders'])==1
    assert D(row['mean_filled_sell_orders'])==1
    ledger.close()


def test_later_published_charges_cannot_leak_into_earlier_feedback(tmp_path):
    from dhan_cas_bot.ledger import Ledger
    ledger=Ledger(tmp_path/'ledger.sqlite3');now=at(clock='11:00')
    for n in range(3):receipt(ledger,'closed'+str(n),now-timedelta(minutes=n+2),requested=100,filled=100)
    before=scores(ledger,now)['OPEN_DRIVE_FAST']['mean_estimated_net_return']
    ledger.db.execute('INSERT INTO order_charges VALUES(?,?,?,?,?,?)',
        ('closed0BUY','closed0BUY','1000',1,(now+timedelta(hours=2)).isoformat(),'{}'))
    assert scores(ledger,now)['OPEN_DRIVE_FAST']['mean_estimated_net_return']==before
    assert D(scores(ledger,now+timedelta(hours=3))['OPEN_DRIVE_FAST']['mean_estimated_net_return'])<D(before)
    ledger.close()


def test_estimated_economics_use_measured_execution_counts_and_only_extra_friction(tmp_path):
    from tests.test_directional_engine import setup
    engine,_,ledger,clock,inputs=setup(tmp_path,'OPEN_DRIVE_FAST')
    sample=inputs.evaluations['OPEN_DRIVE_FAST'];book=engine.books['101']
    history={sample.strategy:{'ranking_available':True,'filled_closed':3,
        'mean_gross_return':'.01511581028943917875','mean_holding_minutes':'.051',
        'mean_entry_fill_fraction':'.375','mean_filled_buy_orders':'1','mean_filled_sell_orders':'1',
        'mean_entry_friction_fraction':'.004'}}
    row=execution_score(sample,(book.instrument,65,D('81.3'),replace(book,
        bids=(Level(D(81),650),))),history,clock[0])
    exposure=65*D('81.3');gross=D(history[sample.strategy]['mean_gross_return'])
    expected=exposure*gross-FeeSchedule().buy(exposure,1)-FeeSchedule().sell(exposure*(1+gross),1)
    assert D(row['estimated_net_profit'])==expected
    assert expected>0
    assert row['cost_basis']=='PRIOR_FILLED_ORDERS'
    ledger.close()


def test_current_wider_spread_still_penalises_measured_economics(tmp_path):
    from tests.test_directional_engine import setup
    from dhan_cas_bot.domain import Level
    engine,_,ledger,clock,inputs=setup(tmp_path,'OPEN_DRIVE_FAST')
    sample=inputs.evaluations['OPEN_DRIVE_FAST'];book=engine.books['101']
    history={sample.strategy:{'ranking_available':True,'filled_closed':3,
        'mean_gross_return':'.2','mean_holding_minutes':'1','mean_entry_fill_fraction':'1',
        'mean_filled_buy_orders':'1','mean_filled_sell_orders':'1','mean_entry_friction_fraction':'.01'}}
    tight=execution_score(sample,(book.instrument,65,D(10),replace(book,bids=(Level(D('9.95'),650),))),history,clock[0])
    wide=execution_score(sample,(book.instrument,65,D(10),replace(book,bids=(Level(D(9),650),))),history,clock[0])
    assert D(tight['incremental_friction_cash'])==0
    assert D(wide['incremental_friction_cash'])==D('58.5')
    assert D(wide['estimated_net_profit'])<D(tight['estimated_net_profit'])
    ledger.close()


def test_profit_floor_is_not_delayed_by_unfilled_retry_brokerage(tmp_path,monkeypatch):
    from tests.test_seconds_oms import prepared
    from dhan_cas_bot.domain import Level
    async def run():
        engine,broker,ledger,clock=prepared(tmp_path,monkeypatch)
        engine.directional.profit_retain=D('.5')
        assert await engine.cycle()
        key='profit-exit:'+engine.active['lifecycle_id']
        book=engine.books['101']
        for bid in ('13.5','12.2'):
            clock[0]+=timedelta(seconds=.2)
            engine.directional.seconds.tape.future_tick(D(24900),int(clock[0].timestamp()*1e9),'m1')
            engine.on_book(replace(book,bids=(Level(D(bid),650),),asks=(Level(D(bid)+D('.05'),650),),received_ns=int(clock[0].timestamp()*1e9)))
            await engine.cycle()
        assert ledger.metadata(key)['triggered']
        assert broker.requests[-1]['transactionType']=='SELL'
        assert ledger.metadata('directional-exit:'+engine.active['lifecycle_id'])['reason']=='NET_PROFIT_FLOOR'
        ledger.close()
    asyncio.run(run())


def test_seconds_choose_better_qualified_contract_instead_of_first_atm():
    from tests.test_seconds_strategies import seeded_tape, NOW
    from dhan_cas_bot.seconds_strategies import NAMES
    from dhan_cas_bot.domain import Level
    tape,books,cal=seeded_tape();stamp=NOW+timedelta(seconds=1)
    tape.future_tick(D(23030),int(stamp.timestamp()*1e9),'m1')
    books={k:replace(b,received_ns=int(stamp.timestamp()*1e9)) for k,b in books.items()}
    # The nearest option has already repriced by two points. A farther one
    # has a larger qualifying discrepancy on the same side, before entry.
    first=books['1'];books['1']=replace(first,bids=(Level(first.top_bid.price+2,650),),asks=(Level(first.top_ask.price+2,650),))
    sample=tape.evaluate(stamp,books,(),cal)[NAMES[0]]
    assert sample.state=='SIGNAL'
    assert sample.details['security_id']!='1'
    assert sample.details['contract_selection']=='MAX_QUALIFIED_NET_HEADROOM'


def test_seconds_entry_limit_is_bounded_by_spread_and_unchanged_net_cost_gate():
    from tests.test_seconds_strategies import book,NOW
    from dhan_cas_bot.seconds_strategies import entry_assessment,opportunity,NAMES
    b=book(bid='99.5',ask='100')
    signal=opportunity(NAMES[0],NOW,b,D(108),D(23000),'entry')
    result=entry_assessment(signal,{'1':b},D(7805),NOW)
    assert result.candidate[2]==D('100.5')
    assert result.details['entry_limit_policy']=='SPREAD_BOUNDED_IOC'
    assert entry_assessment(signal,{'1':b},D(100),NOW).candidate is None
    weak=replace(signal,details={**signal.details,'target_price':'100.3'})
    assert entry_assessment(weak,{'1':b},D(7805),NOW).candidate is None


def test_larger_entry_allowance_falls_back_when_only_old_ceiling_is_affordable():
    from tests.test_seconds_strategies import book,NOW
    from dhan_cas_bot.seconds_strategies import entry_assessment,opportunity,NAMES
    from dhan_cas_bot.risk import worst_case_entry_cash
    b=book(bid='99.5',ask='100');target=D(108)
    signal=opportunity(NAMES[0],NOW,b,target,D(23000),'entry')
    budget=worst_case_entry_cash(65,D('100.1'))+FeeSchedule().sell(65*target,3)
    result=entry_assessment(signal,{'1':b},budget,NOW)
    assert result.candidate is not None
    assert result.candidate[2]==D('100.1')


def test_reported_higher_costs_are_not_discarded_when_predicting_new_economics(tmp_path):
    from tests.test_directional_engine import setup
    engine,_,ledger,clock,inputs=setup(tmp_path,'OPEN_DRIVE_FAST')
    sample=inputs.evaluations['OPEN_DRIVE_FAST'];book=engine.books['101']
    history={sample.strategy:{'ranking_available':True,'filled_closed':3,
        'mean_gross_return':'.2','mean_holding_minutes':'1','mean_entry_fill_fraction':'1',
        'mean_filled_buy_orders':'1','mean_filled_sell_orders':'1',
        'mean_entry_friction_fraction':'.02','mean_cost_fraction':'.3'}}
    row=execution_score(sample,(book.instrument,65,D(10),book),history,clock[0])
    assert D(row['estimated_net_profit'])<0
    ledger.close()


def test_dashboard_cost_basis_is_explicit_and_private_provider_text_is_filtered():
    from dhan_cas_bot.dashboard.data import selection_projection
    row={'strategy':'SECONDS_FUTURES_CATCHUP','cost_basis':'PRIOR_FILLED_ORDERS',
         'estimated_buy_orders':1,'estimated_sell_orders':1,'incremental_friction_cash':'1.25'}
    result=selection_projection({'candidates':[row]})['candidates'][0]
    assert result['cost_basis']=='PRIOR_FILLED_ORDERS'
    assert result['incremental_friction_cash']=='1.25'
    result=selection_projection({'candidates':[{**row,'cost_basis':'private-provider-secret'}]})
    assert 'private-provider-secret' not in str(result)


def test_order_latency_counts_when_ranking_speed_of_cash_reuse(tmp_path):
    from tests.test_directional_engine import setup
    engine,_,ledger,clock,inputs=setup(tmp_path,'OPEN_DRIVE_FAST')
    sample=inputs.evaluations['OPEN_DRIVE_FAST'];book=engine.books['101']
    history={sample.strategy:{'ranking_available':True,'filled_closed':3,
        'mean_gross_return':'.2','mean_holding_minutes':'.02',
        'mean_dispatch_to_exit_minutes':'2','mean_entry_fill_fraction':'1'}}
    row=execution_score(sample,(book.instrument,65,D(10),book),history,clock[0])
    assert D(row['estimated_profit_per_minute'])==D(row['estimated_net_profit'])/2
    assert row['scoring_minutes']=='2'
    ledger.close()


def test_budget_fallback_cannot_step_below_instrument_lower_price_band():
    from tests.test_seconds_strategies import book,NOW
    from dhan_cas_bot.seconds_strategies import entry_assessment,opportunity,NAMES
    from dhan_cas_bot.risk import worst_case_entry_cash
    b=book(bid='99.5',ask='100')
    b=replace(b,instrument=replace(b.instrument,lower_limit=D('100.3')))
    target=D(108);signal=opportunity(NAMES[0],NOW,b,target,D(23000),'band')
    budget=worst_case_entry_cash(65,D('100.1'))+FeeSchedule().sell(65*target,3)
    assert entry_assessment(signal,{'1':b},budget,NOW).candidate is None
