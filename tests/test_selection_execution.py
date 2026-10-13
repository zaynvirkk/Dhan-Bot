"""Counterexamples on the real entry path; synthetic account only."""
import asyncio
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal as D

from dhan_cas_bot.domain import Level, OptionBook, OptionType
from tests.test_directional_engine import setup


def test_unranked_opposite_signals_do_not_make_an_alphabetical_money_bet(tmp_path):
    async def run():
        engine, broker, ledger, clock, inputs = setup(tmp_path, 'OPEN_DRIVE_FAST')
        base = inputs.evaluations['OPEN_DRIVE_FAST']
        put = replace(engine.books['101'].instrument, security_id='102', option_type=OptionType.PE)
        engine.on_book(OptionBook(put, (Level(D('9.8'),650),), (Level(D(10),650),), 'm1', int(clock[0].timestamp()*1e9)))
        other = replace(base, strategy='TREND_PULLBACK_SWING', side='PE')
        engine.directional.enabled = (base.strategy,other.strategy)
        engine.runtime.enabled_strategies = frozenset(engine.directional.enabled)
        engine.directional.update(replace(inputs, evaluations={base.strategy:base,other.strategy:other},
            option_bars={**inputs.option_bars,'102':inputs.option_bars['101']}))
        assert not await engine.cycle()
        assert broker.requests == []
        assert engine.directional.selection['reason'] == 'CONFLICTING_UNRANKED_SIGNALS'
    asyncio.run(run())


def test_cash_per_minute_beats_larger_return_but_longer_hold(tmp_path):
    async def run():
        engine, broker, ledger, clock, inputs = setup(tmp_path, 'OPEN_DRIVE_FAST')
        base = inputs.evaluations['OPEN_DRIVE_FAST']
        slow = replace(base,strategy='TREND_PULLBACK_SWING',exit_at=clock[0]+timedelta(minutes=60))
        engine.directional.enabled = (slow.strategy,base.strategy)
        engine.runtime.enabled_strategies = frozenset(engine.directional.enabled)
        engine.directional.update(replace(inputs,evaluations={base.strategy:base,slow.strategy:slow}))
        engine.directional.ranking = {
            base.strategy: {'ranking_available':True,'filled_closed':5,'mean_estimated_net_return':'.1','mean_gross_return':'.1','mean_holding_minutes':'2','mean_entry_fill_fraction':'1'},
            slow.strategy: {'ranking_available':True,'filled_closed':5,'mean_estimated_net_return':'.4','mean_gross_return':'.4','mean_holding_minutes':'60','mean_entry_fill_fraction':'1'}}
        engine.directional.ranked_at = clock[0]
        assert await engine.cycle()
        assert __import__('json').loads(engine.active['payload'])['strategy'] == base.strategy
        assert len(engine.directional.selection['candidates']) == 2
    asyncio.run(run())


def test_target_is_never_used_as_an_estimated_profit(tmp_path):
    async def run():
        engine, broker, ledger, clock, inputs = setup(tmp_path,'OPEN_DRIVE_FAST')
        assert await engine.cycle()
        row=engine.directional.selection['candidates'][0]
        assert row['estimated_net_profit'] is None
        assert row['estimated_profit_per_minute'] is None
        assert engine.directional.selection['mode'] == 'EXPERIMENTAL_EXECUTION_QUALITY'
    asyncio.run(run())


def test_incremental_candles_remove_missing_overlap_instead_of_preserving_it():
    from dhan_cas_bot.strategy_inputs import MinuteSource
    from tests.test_session_strategies import at
    class Broker:
        def __init__(self):self.requests=[]
        async def _request(self,method,path,**kw):
            self.requests.append(kw['json'])
            times=('09:15','09:16','09:17') if len(self.requests)==1 else ('09:17',)
            return {'timestamp':[int(at(clock=t).timestamp()) for t in times],
                    **{k:['10']*len(times) for k in ('open','high','low','close')},'volume':[100]*len(times)}
    async def run():
        broker=Broker(); clock=[at(clock='09:18')]
        source=MinuteSource(broker,now_fn=lambda:clock[0])
        first=await source.fetch('13','IDX_I','INDEX',at(clock='09:15'),clock[0])
        assert at(clock='09:17') in first
        clock[0]=at(clock='09:19')
        second=await source.fetch('13','IDX_I','INDEX',at(clock='09:15'),clock[0])
        assert broker.requests[1]['fromDate']>'2026-10-05 09:14:00'
        assert at(clock='09:17') not in second  # no stale success in a missing response
        assert at(clock='09:18') in second
    asyncio.run(run())


def test_data_admission_never_queues_an_order_behind_chart_requests(monkeypatch):
    from dhan_cas_bot.broker import DhanBroker
    import dhan_cas_bot.broker as module
    import httpx
    class Scheduler:
        def __init__(self):self.calls=0
        async def acquire(self):self.calls+=1
    async def run():
        data=Scheduler()
        monkeypatch.setattr(module,'data_reads',lambda *args:data)
        broker=DhanBroker('fixture-account','fixture-token',allow_writes=True)
        broker.client=httpx.AsyncClient(transport=httpx.MockTransport(lambda request:httpx.Response(200,json={})))
        await broker._request('POST','/charts/intraday',json={})
        assert data.calls==1
        await broker._request('POST','/orders',json={})
        assert data.calls==1
        await broker.close()
    asyncio.run(run())


def test_auction_cannot_bypass_conflicting_unranked_put(tmp_path):
    from tests.test_production_lifecycles import setup as cas_setup,book,obs
    from dhan_cas_bot.directional import DirectionalEngine,Inputs
    from dhan_cas_bot.session_strategies import Bar,Evaluation,CAS
    from tests.test_session_strategies import calendar
    async def run():
        engine,broker,ledger,clock=cas_setup(tmp_path)
        name='EXPIRY_OPTION_ACCEL_TARGET'
        engine.directional=DirectionalEngine(engine,(name,))
        engine.runtime.enabled_strategies=frozenset((name,CAS))
        engine.on_book(book('CE',1));engine.on_book(book('PE',1,bid='9.8'))
        sample=Evaluation(name,'SIGNAL','TEST',clock[0]-timedelta(minutes=1),'PE',D(25000),clock[0].date(),clock[0]+timedelta(minutes=10))
        cal=replace(calendar(),opens=clock[0]-timedelta(hours=5),closes=clock[0]+timedelta(minutes=19),checked_at=clock[0],day=clock[0].date())
        rows={sample.evaluated_at-timedelta(minutes=i):Bar(sample.evaluated_at-timedelta(minutes=i),D(10),D(10),13000,6500) for i in range(3)}
        engine.directional.update(Inputs(cal,{name:sample},{'200':rows},clock[0]))
        await engine.on_iep(obs('25100',1),dispatch=False)
        await engine.on_iep(obs('25100',2),dispatch=False)
        assert not await engine.cycle()
        assert broker.requests==[]
        assert engine.directional.selection['reason']=='CONFLICTING_UNRANKED_SIGNALS'
    asyncio.run(run())


def test_executable_costs_can_veto_a_previously_positive_engine(tmp_path):
    async def run():
        engine,broker,ledger,clock,inputs=setup(tmp_path,'OPEN_DRIVE_FAST')
        engine.directional.ranking={'OPEN_DRIVE_FAST':{'ranking_available':True,'filled_closed':5,
            'mean_estimated_net_return':'.001','mean_gross_return':'.001','mean_holding_minutes':'2'}}
        engine.directional.ranked_at=clock[0]
        assert not await engine.cycle()
        assert broker.requests==[]
        assert engine.directional.selection['reason']=='NO_POSITIVE_ESTIMATED_EDGE'
    asyncio.run(run())


def test_dashboard_selection_never_projects_provider_text_or_secret():
    from dhan_cas_bot.dashboard.data import selection_projection
    raw={'mode':'MEASURED_CASH_PER_MINUTE','reason':'SELECTED','selected':'OPEN_DRIVE_FAST',
         'token':'private-secret','candidates':[{'strategy':'OPEN_DRIVE_FAST','estimated_net_profit':'5',
               'estimated_profit_per_minute':'2','provider_response':'private-secret','limit':'private-secret'}]}
    result=selection_projection(raw)
    assert result['candidates'][0]['estimated_profit_per_minute']=='2.00'
    assert 'private-secret' not in str(result)
