import asyncio
from dataclasses import replace
from decimal import Decimal as D

import pytest

from dhan_cas_bot.seconds_strategies import NAMES, opportunity
from dhan_cas_bot.directional import Inputs
from tests.test_directional_engine import setup
from tests.test_session_strategies import calendar


def test_seconds_discovery_uses_current_reconciled_cash_instead_of_an_old_budget(tmp_path):
    from datetime import timedelta
    from types import SimpleNamespace
    from dhan_cas_bot.domain import FundsSnapshot
    from dhan_cas_bot.risk import Allocation
    from dhan_cas_bot.ledger import Ledger
    from dhan_cas_bot.seconds_engine import SecondsEngine
    from tests.test_seconds_strategies import seeded_tape, NOW
    tape,books,cal=seeded_tape();at=[NOW+timedelta(seconds=1)]
    tape.future_tick(D('23030'),int(at[0].timestamp()*1e9),'m1')
    books={k:replace(b,received_ns=int(at[0].timestamp()*1e9)) for k,b in books.items()}
    def funds(cash):return FundsSnapshot(at[0],D(cash),D(cash),D(cash),D(0),'TEST')
    account=SimpleNamespace(fresh=True,funds=funds('7805'))
    ledger=Ledger(tmp_path/'discovery.sqlite3')
    allocations=[]
    def allocate(f):
        allocations.append(f.spendable_cash)
        return Allocation.start(f.spendable_cash,f.spendable_cash)
    engine=SimpleNamespace(now=lambda:at[0],books=books,runtime=SimpleNamespace(account_refresh=account,ledger=ledger),
        _allocation=allocate)
    parent=SimpleNamespace(engine=engine,inputs=SimpleNamespace(calendar=cal),enabled=(NAMES[0],))
    seconds=SecondsEngine(parent);seconds.tape=tape;seconds.last_budget=D(100)
    try:
        samples=seconds.signals()
        assert len(samples)==1
        assert samples[0].details['security_id']=='3'  # Same forecast gain, lower costs than the first affordable strike.
        assert seconds.signals()[0].details['security_id']=='3'
        assert len(allocations)==1  # A packet burst must not rescan every closed trade per packet.
        ledger.account_revision=1
        assert seconds.signals()[0].details['security_id']=='3'
        assert len(allocations)==2  # Monetary reconciliation invalidates the cache too.
        at[0]+=timedelta(seconds=.01)
        account.funds=funds('100')
        assert seconds.signals()==[]
        assert len(allocations)==3  # A new balance invalidates the discovery cache immediately.
        assert ledger.db.execute('SELECT count(*) FROM intents').fetchone()[0]==0
    finally:ledger.close()


def test_actual_quote_rule_reaches_production_buy_fill_exit_and_flat_ledger(tmp_path):
    """Causal synthetic tape, real rule/OMS; never evidence of real profit."""
    from datetime import timedelta
    from dhan_cas_bot.directional import DirectionalEngine
    from dhan_cas_bot.engine import SessionEngine
    from dhan_cas_bot.domain import Level
    from tests.test_seconds_strategies import seeded_tape, NOW
    async def run():
        original,broker,ledger,_,_=setup(tmp_path,NAMES[0])
        tape,books,cal=seeded_tape();clock=[NOW+timedelta(seconds=1)]
        tape.future_tick(D('23030'),int(clock[0].timestamp()*1e9),'m1')
        books={k:replace(b,received_ns=int(clock[0].timestamp()*1e9)) for k,b in books.items()}
        engine=SessionEngine(original.runtime,books,now_fn=lambda:clock[0])
        engine.instruments={k:b.instrument for k,b in books.items()}
        engine.directional=DirectionalEngine(engine,(NAMES[0],))
        engine.directional.seconds.tape=tape
        engine.directional.update(Inputs(cal,{}, {},clock[0]))
        try:
            assert await engine.cycle()
            assert [r['transactionType'] for r in broker.requests]==['BUY']
            held=engine.active['security_id'];b=engine.books[held]
            import json
            target=D(json.loads(engine.active['payload'])['signal']['details']['target_price'])
            clock[0]+=timedelta(seconds=1)
            tick=b.instrument.tick_size
            # Use a real tick-aligned later book, not a fabricated candle fill.
            from decimal import ROUND_CEILING
            bid=(target/tick).to_integral_value(rounding=ROUND_CEILING)*tick
            engine.on_book(replace(b,bids=(Level(bid,650),),asks=(Level(bid+tick,650),),received_ns=int(clock[0].timestamp()*1e9)))
            assert await engine.cycle()
            await engine.cycle()
            assert [r['transactionType'] for r in broker.requests]==['BUY','SELL']
            assert engine.active is None and not any(broker.quantities.values())
            assert ledger.db.execute('SELECT count(*) FROM fills').fetchone()[0]==2
        finally:ledger.close()
    asyncio.run(run())


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
