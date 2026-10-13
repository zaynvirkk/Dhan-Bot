"""Counterexamples for live execution feedback; all receipts are temporary fixtures."""
import asyncio
import json
from datetime import timedelta
from decimal import Decimal as D

from dhan_cas_bot.ledger import Ledger
from dhan_cas_bot.strategy_arbiter import execution_score, scores, select_executable
from tests.test_directional_engine import setup
from tests.test_session_strategies import at, calendar


def receipt(ledger, name, stamp, *, requested=200, filled=100, sent=True, state='CLOSED'):
    db=ledger.db
    db.execute('INSERT INTO lifecycles VALUES(?,?,?,?,?,?)',
               (name,'session','101','9411.18',state,json.dumps({'strategy':'OPEN_DRIVE_FAST'})))
    # These receipts exercise the real ledger totals, not a mocked ranking.
    for side,qty,px in [('BUY',requested,'10'),('SELL',filled,'12')]:
        if side=='SELL' and not filled:continue
        ident=name+side
        db.execute('INSERT INTO intents VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                   (ident,ident,name,side,'101',qty,px,'CANCELLED' if side=='BUY' else 'FILLED','0','{}',stamp.isoformat()))
        if sent:
            db.execute('INSERT INTO attempts VALUES(?,?,?,?,?)',(ident,ident,stamp.isoformat(),'ACK','{}'))
        if filled:
            when=stamp+timedelta(seconds=30 if side=='SELL' else 0)
            db.execute('INSERT INTO fills VALUES(?,?,?,?,?,?,?,?,?)',
                       (ident,ident,ident,'101',filled,px,'0',when.isoformat(),'{}'))


def test_zero_partial_future_and_never_sent_entries_do_not_inflate_fill_reliability(tmp_path):
    ledger=Ledger(tmp_path/'feedback.sqlite3');now=at(clock='11:00')
    for n in range(3):receipt(ledger,'partial'+str(n),now-timedelta(minutes=5+n))
    for n in range(3):receipt(ledger,'missed'+str(n),now-timedelta(minutes=10+n),filled=0)
    receipt(ledger,'future',now+timedelta(minutes=1))
    receipt(ledger,'prepared',now-timedelta(minutes=1),filled=0,sent=False)
    receipt(ledger,'open',now-timedelta(minutes=1),state='OPEN')
    row=scores(ledger,now)['OPEN_DRIVE_FAST']
    assert row['filled_closed']==3
    assert row['closed_entry_opportunities']==6
    assert row['filled_entry_opportunities']==3
    assert D(row['entry_fill_rate'])==D('.5')
    assert D(row['mean_entry_fill_fraction'])==D('.25')


def test_missing_fill_reliability_is_unknown_not_a_perfect_fill_forecast(tmp_path):
    engine,_,_,clock,inputs=setup(tmp_path,'OPEN_DRIVE_FAST')
    sample=inputs.evaluations['OPEN_DRIVE_FAST'];book=engine.books['101']
    history={sample.strategy:{'ranking_available':True,'filled_closed':5,
        'mean_gross_return':'.2','mean_holding_minutes':'2'}}
    row=execution_score(sample,(book.instrument,65,D(10),book),history,clock[0])
    assert row['estimated_profit_per_minute'] is None
    assert row['entry_fill_rate'] is None


def test_more_reliable_fills_beat_a_higher_conditional_profit(tmp_path):
    engine,_,_,clock,inputs=setup(tmp_path,'OPEN_DRIVE_FAST')
    sample=inputs.evaluations['OPEN_DRIVE_FAST'];book=engine.books['101']
    from dataclasses import replace
    other=replace(sample,strategy='TREND_PULLBACK_SWING')
    history={s.strategy:{'ranking_available':True,'filled_closed':5,'mean_gross_return':gross,
        'mean_holding_minutes':'2','entry_fill_rate':fraction,'mean_entry_fill_fraction':fraction,
        'closed_entry_opportunities':10,'filled_entry_opportunities':5} for s,gross,fraction in
        [(sample,'.3','.1'),(other,'.2','.9')]}
    rows=[execution_score(s,(book.instrument,65,D(10),book),history,clock[0]) for s in (sample,other)]
    chosen,_,_=select_executable(rows)
    assert chosen['strategy']==other.strategy
    assert D(rows[0]['estimated_profit_per_minute'])<D(rows[1]['estimated_profit_per_minute'])


def test_real_entry_path_uses_fill_completion_before_committing_the_owner(tmp_path):
    from dataclasses import replace
    async def run():
        engine,broker,_,clock,inputs=setup(tmp_path,'OPEN_DRIVE_FAST')
        base=inputs.evaluations['OPEN_DRIVE_FAST'];other=replace(base,strategy='TREND_PULLBACK_SWING')
        engine.directional.enabled=(base.strategy,other.strategy)
        engine.runtime.enabled_strategies=frozenset(engine.directional.enabled)
        engine.directional.update(replace(inputs,evaluations={base.strategy:base,other.strategy:other}))
        engine.directional.ranking={s.strategy:{'ranking_available':True,'filled_closed':5,
            'mean_gross_return':gross,'mean_estimated_net_return':gross,
            'mean_holding_minutes':'2','mean_entry_fill_fraction':fraction}
            for s,gross,fraction in [(base,'.3','.1'),(other,'.2','.9')]}
        engine.directional.ranked_at=clock[0]
        assert await engine.cycle()
        assert json.loads(engine.active['payload'])['strategy']==other.strategy
        assert len(broker.requests)==1
    asyncio.run(run())


def test_known_negative_conditional_edge_does_not_become_unknown_without_fill_history(tmp_path):
    engine,_,_,clock,inputs=setup(tmp_path,'OPEN_DRIVE_FAST')
    sample=inputs.evaluations['OPEN_DRIVE_FAST'];book=engine.books['101']
    history={sample.strategy:{'ranking_available':True,'filled_closed':5,
        'mean_gross_return':'.001','mean_holding_minutes':'2'}}
    row=execution_score(sample,(book.instrument,65,D(10),book),history,clock[0])
    assert select_executable([row])[0] is None


def test_slow_or_failed_optional_source_does_not_serialize_other_feature_reads():
    from dhan_cas_bot.strategy_features import FeatureSource
    async def run():
        gates={key:asyncio.Event() for key in ('iv','daily','published')};release=asyncio.Event()
        class Broker:
            async def _request(self,method,path,**kw):
                key='iv' if path=='/optionchain' else 'daily';gates[key].set()
                await release.wait()
                if key=='iv':raise RuntimeError('private provider failure')
                days=[at()-timedelta(days=n) for n in range(1,31)]
                return {'timestamp':[int(t.timestamp()) for t in days],'close':['25000']*len(days)}
        source=FeatureSource(Broker(),'fixture',lambda:at())
        async def published(*args):
            gates['published'].set();await release.wait();return {'source_date':calendar().previous_opens.date()}
        source.published_chain=published
        task=asyncio.create_task(source.refresh(at(),calendar(),at().date(),
            {'IV_CHEAP_TREND','PUBLISHED_PCR','TREND_PULLBACK'}))
        try:
            await asyncio.wait_for(asyncio.gather(*(gate.wait() for gate in gates.values())),.3)
        finally:release.set()
        values=await task
        assert 'iv' not in values and 'prior_trend' in values and 'prior_chain' in values
    asyncio.run(run())


def test_concurrent_trend_and_institutions_share_one_daily_history_request():
    from dhan_cas_bot.strategy_features import FeatureSource
    async def run():
        calls=[]
        class Broker:
            async def _request(self,*args,**kw):
                calls.append(kw);await asyncio.sleep(0)
                days=[at()-timedelta(days=n) for n in range(1,31)]
                return {'timestamp':[int(t.timestamp()) for t in days],'close':['25000']*len(days)}
        source=FeatureSource(Broker(),'fixture',lambda:at())
        await asyncio.gather(source.daily_values(at()),source.daily_values(at()))
        assert len(calls)==1
    asyncio.run(run())


def test_feedback_dashboard_projection_hides_private_and_nonfinite_values():
    from dhan_cas_bot.dashboard.data import execution_feedback_projection
    result=execution_feedback_projection({'OPEN_DRIVE_FAST':{'filled_closed':3,'sessions':1,
        'entry_fill_rate':'.5','mean_entry_fill_fraction':'NaN','return_standard_error':'.04',
        'mean_estimated_net_return':'.01','private':'secret'},'secret':{'filled_closed':4}})
    assert len(result)==1 and D(result[0]['entry_fill_rate'])==D('.5')
    assert result[0]['mean_entry_fill_fraction'] is None
    assert 'secret' not in str(result)
