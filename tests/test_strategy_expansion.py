"""Real production paths with synthetic broker data; no funded fixture orders."""
import asyncio
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal as D

from dhan_cas_bot.session_strategies import Bar, Evaluation
from dhan_cas_bot.strategy_inputs import strategy_names
from tests.test_directional_engine import setup
from tests.test_session_strategies import at, calendar


def test_new_intraday_names_are_real_admitted_strategies():
    names=['OPEN_DRIVE_FAST','TREND_PULLBACK_SWING','VOLUME_REVERSAL_DOUBLE',
           'ORDINARY_FUTURE_OI_TARGET','EXPIRY_BASIS_LEAD_TRAIL']
    assert strategy_names({'strategies':names})==tuple(names)


def test_expansion_signal_uses_only_completed_inputs():
    from dhan_cas_bot.expanded_strategies import evaluate
    now=at(clock='10:00'); spot={}; future={}
    t=at(clock='09:16')
    while t<=now:
        elapsed=int((t-at(clock='09:16')).total_seconds()/60)
        px=D(25000)+elapsed*D(3)
        spot[t]=Bar(t,D(25000) if elapsed==0 else px,px,100,1000,px+1,px-1)
        future[t]=Bar(t,px,px,1000,1000+elapsed*10,px+1,px-1)
        t+=timedelta(minutes=1)
    r=evaluate('OPEN_DRIVE_FAST',now,calendar(),spot,future,{date(2026,10,13)})
    assert r.state=='SIGNAL' and r.side=='CE'
    assert r.details['exit_target']=='1.25' and r.details['exit_stop']=='.85'
    del spot[now]
    future_time=now+timedelta(minutes=1)
    spot[future_time]=Bar(future_time,D(25500),D(25500),100,1000,D(25501),D(25499))
    assert evaluate('OPEN_DRIVE_FAST',now,calendar(),spot,future,{date(2026,10,13)}).state=='UNKNOWN'


def test_new_engine_sends_real_oms_buy_and_fast_exit(tmp_path):
    async def run():
        engine,broker,ledger,clock,inputs=setup(tmp_path,'OPEN_DRIVE_FAST')
        ledger.db.execute('DELETE FROM metadata')
        engine.directional.signals.clear()
        sample=replace(inputs.evaluations['OPEN_DRIVE_FAST'],details={'exit_target':'1.25','exit_stop':'.85'})
        engine.directional.update(replace(inputs,evaluations={sample.strategy:sample}))
        assert await engine.cycle()
        assert broker.requests[0]['transactionType']=='BUY'
        assert engine.active is not None
        exit_bar=at()+timedelta(minutes=2)
        rows={**inputs.option_bars['101'],exit_bar:Bar(exit_bar,D('13.5'),D('13.5'),13000,6500)}
        clock[0]=exit_bar+timedelta(minutes=1,seconds=3)
        engine.on_book(replace(engine.books['101'],received_ns=int(clock[0].timestamp()*1e9)))
        engine.directional.update(replace(inputs,option_bars={'101':rows},received_at=clock[0]))
        assert await engine.cycle()
        assert broker.requests[-1]['transactionType']=='SELL'
        await engine.cycle()
        assert engine.active is None
    asyncio.run(run())


def test_unfillable_engine_does_not_starve_other_signal(tmp_path):
    from dhan_cas_bot.session_strategies import GAP,REBOUND
    async def run():
        engine,broker,ledger,clock,inputs=setup(tmp_path)
        engine.directional.enabled=(GAP,REBOUND)
        engine.runtime.enabled_strategies=frozenset((GAP,REBOUND))
        second=replace(inputs.evaluations[GAP],strategy=REBOUND,exit_at=at('2026-10-06','15:10'))
        engine.directional.update(replace(inputs,evaluations={GAP:inputs.evaluations[GAP],REBOUND:second}))
        choose=engine.directional.candidate
        def candidate(signal,allocation):
            if signal.strategy==GAP:
                engine.directional.last_reason='NO_AFFORDABLE_LIQUID_CONTRACT'
                return None
            return choose(signal,allocation)
        engine.directional.candidate=candidate
        assert await engine.cycle()
        assert len(broker.requests)==1
        assert ledger.metadata(engine.directional.signal_key(inputs.evaluations[GAP])+':assessment')['reason']=='NO_AFFORDABLE_LIQUID_CONTRACT'
        assert __import__('json').loads(engine.active['payload'])['strategy']==REBOUND
    asyncio.run(run())


def test_feature_failure_is_local_and_never_fabricates_a_source():
    from dhan_cas_bot.strategy_features import FeatureSource
    class Broker:
        async def _request(self,*args,**kw):raise RuntimeError('private provider response')
    async def run():
        source=FeatureSource(Broker(),'fixture',lambda:at())
        async def missing(*args,**kw):raise RuntimeError('private response')
        source.upstox=missing
        values=await source.refresh(at(),calendar(),date(2026,10,13),{'IV_CHEAP_TREND','PCR_CONFIRM'})
        assert 'iv' not in values and 'insights' not in values
        assert all('private' not in str(v) for v in values.values())
    asyncio.run(run())


def test_insight_bucket_cannot_be_used_early_or_as_terminal_summary():
    from dhan_cas_bot.strategy_features import parse_insights
    raw={'status':'success','data':{'pcr':'999','insights':[{'time':'10:00','pcr':'1.2'}]}}
    assert parse_insights(raw,'pcr',at(clock='10:04'))=={}
    assert parse_insights(raw,'pcr',at(clock='10:05'))=={at(clock='10:05'):D('1.2')}


def test_closed_scores_ignore_unfilled_attempts_open_positions_and_future_fills(tmp_path):
    from dhan_cas_bot.strategy_arbiter import scores
    engine,broker,ledger,clock,inputs=setup(tmp_path)
    async def run():
        assert await engine.cycle()
        assert scores(ledger,clock[0])=={}  # exposure is still open
        ledger.db.execute("UPDATE lifecycles SET state='CLOSED'")
        assert scores(ledger,clock[0])=={}  # inconsistent flat state is excluded
    asyncio.run(run())


def test_exit_variants_cannot_retry_same_family_after_zero_fill(tmp_path):
    async def run():
        engine,broker,ledger,clock,inputs=setup(tmp_path,'OPEN_DRIVE_FAST')
        engine.directional.enabled=('OPEN_DRIVE_FAST','OPEN_DRIVE_DOUBLE')
        engine.runtime.enabled_strategies=frozenset(engine.directional.enabled)
        base=inputs.evaluations['OPEN_DRIVE_FAST']
        engine.directional.update(replace(inputs,evaluations={s:replace(base,strategy=s) for s in engine.directional.enabled}))
        broker.next_fill=0
        assert await engine.cycle()
        await engine.cycle()
        await engine.cycle()
        assert len(broker.requests)==1
    asyncio.run(run())


def test_dashboard_projects_all_engines_without_provider_text():
    from dhan_cas_bot.dashboard.data import strategy_projection
    from dhan_cas_bot.expanded_strategies import NAMES
    rows=[{'strategy':n,'enabled':True,'state':'UNKNOWN','reason':'MISSING_SAME_STRIKE_OPTION',
           'details':{'future_15m':'.01','token':'private-secret'},'family':'OPEN_DRIVE'} for n in NAMES]
    output=strategy_projection(rows)
    assert len(output)==len(NAMES)
    assert output[0]['reason']=='MISSING_SAME_STRIKE_OPTION'
    assert all('private-secret' not in str(r) for r in output)


def test_large_strategy_history_remains_readable_and_preserves_day_counts():
    import json
    from dhan_cas_bot.dashboard.history import advance_history
    from tests.test_dashboard_history import report,NOW
    from dhan_cas_bot.expanded_strategies import NAMES
    value=None
    for i in range(30):
        now=NOW+timedelta(minutes=i);data=report(now)
        data['runtime']['strategy_evaluations']=[{'strategy':n,'state':'NO_SIGNAL','reason':'EXPANDED_RULE_NOT_MET',
            'evaluated_at':now.isoformat(),'details':{k:'12345.123' for k in ('future_15m','future_vwap','basis_change')}} for n in NAMES]
        value=advance_history(value,data,now)
    assert len(json.dumps(value))<1_600_000
    assert value['days'][0]['samples']==30
    assert value['events'][-1]['at']==now.isoformat()


def test_profitable_qualified_cas_is_not_starved_by_unranked_directional_signal(tmp_path):
    from tests.test_production_lifecycles import setup as cas_setup,book,obs
    from dhan_cas_bot.directional import DirectionalEngine,Inputs
    from dhan_cas_bot.session_strategies import CAS
    from dataclasses import replace
    async def run():
        engine,broker,ledger,clock=cas_setup(tmp_path)
        name='EXPIRY_OPTION_ACCEL_TARGET'
        engine.directional=DirectionalEngine(engine,(name,))
        engine.runtime.enabled_strategies=frozenset((name,CAS))
        # Seed only the selector's already-computed estimate, never fill evidence.
        engine.directional.ranking={CAS:{'ranking_available':True,'mean_estimated_net_return':'.02','filled_closed':16}}
        engine.directional.ranked_at=clock[0]
        engine.on_book(book('CE',1))
        sample=Evaluation(name,'SIGNAL','TEST',clock[0]-timedelta(minutes=1),'CE',D(25000),clock[0].date(),clock[0]+timedelta(minutes=10))
        cal=replace(calendar(),opens=clock[0]-timedelta(hours=5),closes=clock[0]+timedelta(minutes=19),
                    checked_at=clock[0],day=clock[0].date())
        rows={sample.evaluated_at-timedelta(minutes=i):Bar(sample.evaluated_at-timedelta(minutes=i),D(10),D(10),13000,6500) for i in range(3)}
        engine.directional.update(Inputs(cal,{name:sample},{'100':rows},clock[0]))
        await engine.on_iep(obs('25100',1),dispatch=False)
        await engine.on_iep(obs('25100',2),dispatch=False)
        assert await engine.cycle()
        assert __import__('json').loads(engine.active['payload']).get('strategy',CAS)==CAS
        assert len(broker.requests)==1
    asyncio.run(run())
