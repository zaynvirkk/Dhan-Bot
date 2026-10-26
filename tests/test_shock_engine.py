import asyncio
import json
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal as D
from types import SimpleNamespace
import pytest
from tests.test_volatility_shock import tapes, signal, book
from tests.test_session_strategies import at, calendar
from tests.test_production_lifecycles import MatchingBroker
from tests.acceptance.cas.support import mandate
from dhan_cas_bot.directional import DirectionalEngine, Inputs
from dhan_cas_bot.engine import SessionEngine
from dhan_cas_bot.runtime import AutoLive
from dhan_cas_bot.ledger import Ledger
from dhan_cas_bot.domain import Level
from dhan_cas_bot.volatility_shock import SHOCK


def setup(tmp_path):
    ledger=Ledger(tmp_path/'ledger.sqlite3');broker=MatchingBroker(ledger)
    runtime=AutoLive(ledger,broker,mandate(live=True),software_verified=True)
    runtime.enabled_strategies=frozenset({SHOCK})
    runtime.status.current_account_funded=runtime.status.broker_route_verified=True
    runtime.future_input=SimpleNamespace(health=lambda now:{'current':True},tape=SimpleNamespace(future=[(0,D(23130))]))
    t,spot,future=tapes();clock=[t+timedelta(seconds=2)]
    engine=SessionEngine(runtime,{},now_fn=lambda:clock[0]);b=book()
    engine.instruments={b.instrument.security_id:b.instrument};engine.on_book(b)
    engine.directional=DirectionalEngine(engine,[SHOCK],profit_retain=D('.5'))
    inputs=Inputs(calendar(),{SHOCK:signal()},{},clock[0],spot_bars=spot,future_bars=future)
    engine.directional.update(inputs)
    return engine,broker,ledger,clock,inputs


def test_shock_sends_real_oms_request_now_without_cas_or_option_candles_and_closes(tmp_path):
    async def run():
        e,b,l,c,inputs=setup(tmp_path)
        assert not e.runtime.status.official_cas_signal_seen
        assert await e.cycle()
        assert len(b.requests)==1 and b.requests[0]['validity']=='IOC'
        assert D(b.requests[0]['price'])<=D('20')*D('1.004')
        active=e.active;payload=json.loads(active['payload'])
        assert payload['strategy']==SHOCK and payload['shock']['exit_policy']=='SHOCK_EXIT_V1'
        assert 'profit_exit' not in payload
        await e.cycle()  # holding; does not buy again or inherit generic targets
        c[0]+=timedelta(seconds=1)
        fresh=replace(e.books['s'],received_ns=int(c[0].timestamp()*1e9),bids=(Level(D(11),650),),asks=(Level(D('11.05'),650),))
        e.on_book(fresh)
        assert await e.cycle()
        assert b.requests[-1]['transactionType']=='SELL'
        await e.cycle()
        assert e.active is None and l.metadata('shock-last-closed')
        assert l.metadata('shock-exit:'+active['lifecycle_id'])['triggered_reason']=='SHOCK_PREMIUM_STOP'
    asyncio.run(run())


@pytest.mark.parametrize('fault',['late','funded','disarm','future','book','pending','foreign'])
def test_shock_all_authority_and_freshness_gates_still_bind(tmp_path,fault):
    async def run():
        e,b,l,c,i=setup(tmp_path)
        if fault=='late':c[0]+=timedelta(seconds=31)
        if fault=='funded':e.runtime.enabled_strategies=frozenset()
        if fault=='disarm':e.runtime.disarm_new_entries()
        if fault=='future':e.runtime.future_input=None
        if fault=='book':e.books.clear()
        if fault=='foreign':b.quantities['other']=65
        if fault=='pending':
            from dhan_cas_bot.domain import Intent
            l.create_intent(Intent('p','BUY',e.instruments['s'],65,D(20),'p',c[0],'unknown'),D(1400))
            l.record_attempt('p','p','UNKNOWN',{})
        assert not await e.cycle() and not b.requests
    asyncio.run(run())


def test_zero_fill_and_restart_cannot_retry_or_renew_same_episode(tmp_path):
    async def run():
        e,b,l,c,i=setup(tmp_path);b.next_fill=0
        assert await e.cycle()
        await e.cycle()
        e.directional=DirectionalEngine(e,[SHOCK]);e.directional.update(i)
        assert not await e.cycle() and len(b.requests)==1
        later=replace(i.evaluations[SHOCK],evaluated_at=i.evaluations[SHOCK].evaluated_at+timedelta(minutes=1))
        e.directional.update(replace(i,evaluations={SHOCK:later}))
        assert e.directional.shock.sample.evaluated_at==i.evaluations[SHOCK].evaluated_at
    asyncio.run(run())


def test_disabled_entry_owner_still_manages_existing_shock_position(tmp_path):
    async def run():
        e,b,l,c,i=setup(tmp_path);assert await e.cycle()
        await e.cycle()  # reconcile the simulated broker's fill first
        # MatchingBroker has no exchange clock. Bind its observed synthetic
        # fill to this test's clock before testing elapsed holding time.
        l.db.execute('UPDATE fills SET occurred_at=?',(c[0].isoformat(),))
        e.directional=DirectionalEngine(e,[]);e.directional.inputs=i
        e.runtime.enabled_strategies=frozenset()
        c[0]+=timedelta(minutes=121)
        e.on_book(replace(e.books['s'],received_ns=int(c[0].timestamp()*1e9)))
        assert await e.cycle() and b.requests[-1]['transactionType']=='SELL'
    asyncio.run(run())


def test_reconnect_consumes_incomplete_episode_without_disabling_position_management(tmp_path):
    e,b,l,c,i=setup(tmp_path)
    original=e.directional.shock.sample
    e.directional.shock.invalidate()
    e.directional.update(i)
    assert l.metadata(e.directional.signal_key(original)+':consumed')['reason']=='SHOCK_RECONNECT_INVALIDATED'


@pytest.mark.parametrize('reason',['ENTRY_DEADLINE_MISSED','DECISION_COMMITTED'])
def test_reconnect_preserves_first_consumption_receipt(tmp_path,reason):
    e,b,l,c,i=setup(tmp_path)
    key=e.directional.signal_key(e.directional.shock.sample)+':consumed'
    receipt={'reason':reason,'lifecycle_id':'original','blocking_reason':'SHOCK_SCENARIO_BELOW_FLOOR'}
    l.put_metadata(key,receipt)
    e.directional.shock.invalidate()
    assert l.metadata(key)==receipt
    assert e.directional.shock.sample is None and not b.requests


def test_restart_restores_today_assessment_for_display_without_rearming(tmp_path):
    e,b,l,c,i=setup(tmp_path)
    original=e.directional.shock.sample
    checks=[{'security_id':'s','reason':'SHOCK_SCENARIO_BELOW_FLOOR','scenario_multiple':'1.725','quantity':65}]
    e.directional.record_assessment(original,'NO_AFFORDABLE_LIQUID_CONTRACT',checks)
    e.directional=DirectionalEngine(e,[SHOCK])
    row=e.directional.view()[0]
    assert row['shock_candidates']==checks
    assert row['last_execution_reason']=='SHOCK_SCENARIO_BELOW_FLOOR'
    assert row['candidate_signal_at']==original.evaluated_at.isoformat()
    assert e.directional.shock.sample is None and not b.requests
    # The following session must not inherit today's diagnostic as current.
    c[0]+=timedelta(days=1)
    e.directional=DirectionalEngine(e,[SHOCK])
    assert e.directional.view()[0]['shock_candidates']==[]


def test_scenario_rejection_is_not_reported_as_unaffordable(tmp_path,monkeypatch):
    async def run():
        e,b,l,c,i=setup(tmp_path)
        checks=[{'reason':'NO_AFFORDABLE_LIQUID_CONTRACT'},
                {'reason':'SHOCK_SCENARIO_BELOW_FLOOR','quantity':65,'scenario_multiple':'1.725'}]
        monkeypatch.setattr('dhan_cas_bot.shock_engine.select_shock_candidate',lambda *a:(None,checks))
        assert not await e.cycle() and not b.requests
        assessment=l.metadata(e.directional.signal_key(e.directional.shock.sample)+':assessment')
        assert assessment['reason']=='SHOCK_SCENARIO_BELOW_FLOOR'
        assert assessment['assessed_at']==c[0].isoformat()
    asyncio.run(run())


def test_live_future_reversal_prevents_dispatch(tmp_path):
    async def run():
        e,b,l,c,i=setup(tmp_path)
        e.runtime.future_input.tape.future=[(0,D(22000))]
        assert not await e.cycle() and not b.requests
    asyncio.run(run())


def test_profit_peak_requires_full_depth_reachable_by_the_actual_exit_limit(tmp_path):
    async def run():
        e,b,l,c,i=setup(tmp_path)
        assert await e.cycle();await e.cycle()
        active=e.active
        c[0]+=timedelta(seconds=1)
        # There is plenty of displayed depth, but most cannot be reached by
        # the existing two-tick IOC sale limit. It cannot arm a profit floor.
        e.on_book(replace(e.books['s'],received_ns=int(c[0].timestamp()*1e9),
            bids=(Level(D(40),65),Level(D(38),650)),asks=(Level(D('40.05'),650),)))
        await e.cycle()
        guard=l.metadata('shock-exit:'+active['lifecycle_id'])
        assert guard['quote_executable'] is False and guard['net_liquidation_profit'] is None
        assert D(guard['peak_net_profit'])==0 and guard['trailing_armed'] is False
    asyncio.run(run())
