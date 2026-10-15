import asyncio
from dataclasses import replace
from decimal import Decimal as D

import pytest

from dhan_cas_bot.seconds_strategies import NAMES, opportunity
from dhan_cas_bot.directional import Inputs
from tests.test_directional_engine import setup
from tests.test_session_strategies import calendar


def prepared(tmp_path, monkeypatch, name=NAMES[0]):
    engine, broker, ledger, clock, inputs=setup(tmp_path,name)
    seconds=engine.directional.seconds
    from dhan_cas_bot.domain import Level
    b=replace(engine.books['101'],bids=(Level(D('9.95'),650),))
    engine.books['101']=b
    sample=opportunity(name,clock[0],b,D(15),D(24900),'test-episode')
    seconds.tape.future_tick(D(24900),b.received_ns,b.epoch)
    seconds.evaluations={name:sample}
    monkeypatch.setattr(seconds,'refresh',lambda **kw:None)
    engine.directional.update(Inputs(calendar(),{}, {},clock[0]))
    return engine,broker,ledger,clock


def test_seconds_missing_live_future_cannot_send(tmp_path):
    async def run():
        engine,broker,ledger,clock,inputs=setup(tmp_path,NAMES[0])
        assert not await engine.cycle()
        assert broker.requests==[]
    asyncio.run(run())


@pytest.mark.parametrize('name',NAMES)
def test_seconds_use_existing_oms_without_minute_candle_fills(tmp_path,monkeypatch,name):
    async def run():
        engine,broker,ledger,clock=prepared(tmp_path,monkeypatch,name)
        assert await engine.cycle()
        assert len(broker.requests)==1
        assert engine.active is not None
        assert not await engine.cycle()
    asyncio.run(run())


@pytest.mark.parametrize('case',['unfunded','disarmed','route','stale','expired','thin','cash'])
def test_seconds_never_bypass_money_or_freshness_checks(tmp_path,monkeypatch,case):
    async def run():
        engine,broker,ledger,clock=prepared(tmp_path,monkeypatch)
        if case=='unfunded':engine.runtime.enabled_strategies=frozenset({'CAS_LAG_V1'})
        elif case=='disarmed':engine.runtime.disarm_new_entries()
        elif case=='route':engine.runtime.status.broker_route_verified=False
        elif case=='stale':engine.books['101']=replace(engine.books['101'],received_ns=1)
        elif case=='expired':clock[0]+=__import__('datetime').timedelta(seconds=6)
        elif case=='thin':
            from dhan_cas_bot.domain import Level
            engine.books['101']=replace(engine.books['101'],asks=(Level(D(10),1),))
        elif case=='cash':broker.cash=D(100)
        assert not await engine.cycle()
        assert broker.requests==[]
    asyncio.run(run())


def test_seconds_exit_uses_current_quote_before_a_minute_boundary(tmp_path,monkeypatch):
    async def run():
        from datetime import timedelta
        from dhan_cas_bot.domain import Level
        engine,broker,ledger,clock=prepared(tmp_path,monkeypatch)
        assert await engine.cycle()
        clock[0]+=timedelta(seconds=2)
        b=engine.books['101']
        engine.books['101']=replace(b,bids=(Level(D(15),650),),asks=(Level(D('15.05'),650),),received_ns=int(clock[0].timestamp()*1e9))
        engine.runtime.enabled_strategies=frozenset()  # Losing entry permission never disables exits.
        assert await engine.cycle()
        assert len(broker.requests)==2
        assert engine.runtime.status.reason.endswith('SECONDS_TARGET_REPRICED')
    asyncio.run(run())
