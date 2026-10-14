"""Deadline and data isolation cases for the real production minute worker."""
import asyncio
from dataclasses import replace
from datetime import timedelta

from dhan_cas_bot.strategy_inputs import StrategyInputWorker
from tests.test_directional_engine import setup
from tests.test_session_strategies import at, calendar, bars, futures


def test_live_chart_lower_boundary_cannot_erase_previous_completed_minute():
    from dhan_cas_bot.strategy_inputs import MinuteSource
    class Broker:
        async def _request(self,method,path,**kw):
            request=kw['json']
            from datetime import datetime
            from dhan_cas_bot.session_strategies import IST
            lower=datetime.fromisoformat(request['fromDate']).replace(tzinfo=IST)
            upper=datetime.fromisoformat(request['toDate']).replace(tzinfo=IST)
            # Observed Dhan behavior: the bar starting at lower is excluded.
            starts=[];t=lower+timedelta(minutes=1)
            while t<upper:
                starts.append(t);t+=timedelta(minutes=1)
            return {'timestamp':[int(t.timestamp()) for t in starts],
                    **{k:['10']*len(starts) for k in ('open','high','low','close')},
                    'volume':[100]*len(starts),'open_interest':[200]*len(starts)}
    async def run():
        clock=[at(clock='10:00')]
        source=MinuteSource(Broker(),now_fn=lambda:clock[0])
        for i in range(4):
            clock[0]=at(clock='10:00')+timedelta(minutes=i)
            rows=await source.fetch('99','NSE_FNO','FUTIDX',at(clock='09:15'),clock[0],oi=True)
            assert all(at(clock='09:16')+timedelta(minutes=n) in rows for n in range(45+i))
    asyncio.run(run())


def worker_fixture(tmp_path):
    engine, broker, ledger, clock, inputs = setup(tmp_path)
    ledger.db.execute('DELETE FROM metadata')
    engine.directional.signals.clear()
    clock[0] = at()+timedelta(seconds=2)
    engine.instruments={'101':engine.books['101'].instrument}
    worker=StrategyInputWorker(engine.directional,'fixture-token','99',wake=asyncio.Event(),stop=asyncio.Event())
    worker.calendar=calendar()
    async def fetch(security,segment,instrument,start,end,**kwargs):
        return bars() if security=='13' else futures() if security=='99' else inputs.option_bars['101']
    worker.minutes.fetch=fetch
    return worker,engine,clock,inputs


def test_auxiliary_read_cannot_hold_up_core_or_option_readiness(tmp_path):
    async def run():
        worker,engine,clock,inputs=worker_fixture(tmp_path)
        engine.directional.enabled=('ORDINARY_SECTOR_CONFIRM_TARGET',)
        started=asyncio.Event();release=asyncio.Event()
        async def slow(*args):
            started.set();await release.wait();return {}
        worker.features.refresh=slow
        task=asyncio.create_task(worker.refresh())
        try:
            await asyncio.wait_for(started.wait(),1)
            await asyncio.wait_for(asyncio.shield(task),.3)
            assert '101' in engine.directional.inputs.option_bars
        finally:
            release.set()
            await asyncio.gather(task,return_exceptions=True)
            await worker.close()
    asyncio.run(run())


def test_minute_boundary_cannot_move_evaluation_to_unfetched_future_bars(tmp_path):
    async def run():
        worker,engine,clock,inputs=worker_fixture(tmp_path)
        original=worker.minutes.fetch
        async def delayed(security,*args,**kwargs):
            result=await original(security,*args,**kwargs)
            if security=='99':clock[0]=at()+timedelta(minutes=1,seconds=2)
            return result
        worker.minutes.fetch=delayed
        try:
            await worker.refresh()
            sample=engine.directional.inputs.evaluations['GAP_FADE_DOUBLE']
            assert sample.evaluated_at==at()
            assert sample.state=='SIGNAL'
            assert sample.side=='CE'
        finally:await worker.close()
    asyncio.run(run())


def test_old_read_cannot_be_relabelled_as_current_signal(tmp_path):
    async def run():
        worker,engine,clock,inputs=worker_fixture(tmp_path)
        original=worker.minutes.fetch
        async def delayed(security,*args,**kwargs):
            result=await original(security,*args,**kwargs)
            if security=='99':clock[0]=at()+timedelta(minutes=3)
            return result
        worker.minutes.fetch=delayed
        try:
            await worker.refresh()
            sample=engine.directional.inputs.evaluations['GAP_FADE_DOUBLE']
            assert sample.state=='UNKNOWN'
            assert not engine.directional.signals
        finally:await worker.close()
    asyncio.run(run())


def test_unrelated_strategy_does_not_inherit_another_signals_missed_deadline(tmp_path):
    engine,broker,ledger,clock,inputs=setup(tmp_path)
    engine.directional.enabled=('GAP_FADE_DOUBLE','ORDINARY_FUTURE_TREND_TARGET')
    unknown=replace(inputs.evaluations['GAP_FADE_DOUBLE'],strategy='ORDINARY_FUTURE_TREND_TARGET',state='NO_SIGNAL',side=None)
    engine.directional.update(replace(inputs,evaluations={**inputs.evaluations,unknown.strategy:unknown}))
    engine.directional.last_reason='ENTRY_DEADLINE_MISSED'
    row=next(r for r in engine.directional.view() if r['strategy']==unknown.strategy)
    assert row['last_execution_reason'] is None


def test_auxiliary_completion_cannot_create_a_refresh_request_storm(tmp_path):
    async def run():
        worker,engine,clock,inputs=worker_fixture(tmp_path)
        calls=[]
        async def collect(*args):calls.append(True);return {}
        worker.features.refresh=collect
        try:
            await worker.refresh();await worker.aux_task
            await worker.refresh()
            if worker.aux_task:await worker.aux_task
            assert len(calls)==1
        finally:await worker.close()
    asyncio.run(run())


def test_dashboard_projects_input_holes_without_leaking_provider_payloads():
    from dhan_cas_bot.dashboard.data import runtime_view
    raw={'observed_at':at().isoformat(),'input_health':{'observed_at':at().isoformat(),'decision_bar_at':at().isoformat(),
        'spot':{'rows':30,'latest_completed':at().isoformat(),'current_complete':True,'missing_minutes':0,'error':''},
        'future':{'rows':29,'latest_completed':at().isoformat(),'current_complete':True,'missing_minutes':1,
            'first_missing':(at()-timedelta(minutes=1)).isoformat(),'error':'private-token in response'},
        'options':{'requested':10,'ready':8,'failed':2},'token':'private-token'}}
    result=runtime_view(raw,at())
    assert result['input_health']['future']['missing_minutes']==1
    assert result['input_health']['future']['error']=='UNKNOWN'
    assert 'private-token' not in str(result)


def test_incremental_provider_hole_cannot_hide_behind_cached_candles():
    from dhan_cas_bot.strategy_inputs import MinuteSource
    class Broker:
        calls=0
        async def _request(self,*args,**kw):
            self.calls+=1
            times=[at(clock='09:58'),at(clock='09:59')]
            if self.calls>1:times=times[1:]
            return {'timestamp':[int(t.timestamp()) for t in times],
                **{key:['10']*len(times) for key in ('open','high','low','close')},
                'volume':[100]*len(times),'open_interest':[200]*len(times)}
    async def run():
        source=MinuteSource(Broker(),now_fn=lambda:at(clock='10:00'))
        args=('99','NSE_FNO','FUTIDX',at(clock='09:15'),at(clock='10:00'))
        first=await source.fetch(*args,oi=True)
        assert at(clock='09:59') in first
        second=await source.fetch(*args,oi=True)
        assert at(clock='09:59') not in second
    asyncio.run(run())


def test_failed_optional_publication_cannot_erase_independent_index_reads(tmp_path):
    async def run():
        worker,engine,clock,inputs=worker_fixture(tmp_path)
        worker.indexes={'BANK':'2','IT':'3'}
        context=(at().date(),engine.instruments['101'].expiry)
        worker.aux_context=context
        async def failed(*args):raise RuntimeError('private provider payload')
        worker.features.refresh=failed
        try:
            await worker.auxiliary(at(),calendar(),context[1],{'SECTOR_CONFIRM'},context)
            assert {'BANK','IT'}<=worker.aux_features.keys()
            assert worker.aux_error=='RuntimeError'
            assert 'private provider payload' not in str(worker.input_health)
        finally:await worker.close()
    asyncio.run(run())
