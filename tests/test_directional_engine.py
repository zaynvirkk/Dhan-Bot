"""Production OMS integration with a synthetic broker, never a funded account."""
import asyncio
import json
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal as D

import pytest

from dhan_cas_bot.directional import DirectionalEngine, Inputs
from dhan_cas_bot.domain import Instrument, Level, OptionBook, OptionType, Segment
from dhan_cas_bot.engine import SessionEngine
from dhan_cas_bot.ledger import Ledger
from dhan_cas_bot.runtime import AutoLive
from dhan_cas_bot.session_strategies import GAP, REBOUND, Bar, Evaluation
from tests.acceptance.cas.support import mandate
from tests.test_production_lifecycles import MatchingBroker
from tests.test_session_strategies import at, calendar


def setup(tmp_path, strategy=GAP):
    ledger = Ledger(tmp_path/"ledger.sqlite3")
    broker = MatchingBroker(ledger)
    runtime = AutoLive(ledger, broker, mandate(live=True), software_verified=True)
    runtime.status.current_account_funded = runtime.status.broker_route_verified = True
    clock = [at()+timedelta(minutes=1, seconds=3)]
    engine = SessionEngine(runtime, {}, now_fn=lambda:clock[0])
    inst = Instrument("101", "NIFTY", Segment.NSE_FNO, date(2026,10,13), OptionType.CE, D(24900), 65, D(".05"), 1800)
    engine.on_book(OptionBook(inst,(Level(D("9.8"),650),),(Level(D(10),650),),"m1",int(clock[0].timestamp()*1e9)))
    engine.directional = DirectionalEngine(engine, (strategy,))
    runtime.enabled_strategies = frozenset((strategy,))
    sample = Evaluation(strategy, "SIGNAL", "TEST", at(), "CE", D(24900), date(2026,10,6),
                        at("2026-10-06","15:10") if strategy==REBOUND else at(clock="15:34"))
    rows = {at()-timedelta(minutes=i): Bar(at()-timedelta(minutes=i), D(10), D(10), 13000, 6500) for i in range(3)}
    inputs = Inputs(calendar(), {strategy:sample}, {"101":rows}, clock[0], "")
    engine.directional.update(inputs)
    return engine, broker, ledger, clock, inputs


def test_directional_signal_does_not_fake_cas_evidence(tmp_path):
    async def run():
        engine, broker, ledger, _, _ = setup(tmp_path)
        assert not engine.runtime.status.official_cas_signal_seen
        assert not engine.runtime.permit_entry()
        assert await engine.cycle()
        assert len(broker.requests) == 1
        assert json.loads(engine.active["payload"])["strategy"] == GAP
        assert not engine.runtime.status.official_cas_signal_seen
        assert not await engine.cycle()  # no pyramiding from the same signal
    asyncio.run(run())


@pytest.mark.parametrize("case", ["stale_book", "stale_input", "calendar", "disarmed", "late", "missing_option", "cash", "pending"])
def test_missing_or_stale_input_cannot_send_buy(tmp_path, case):
    async def run():
        engine, broker, ledger, clock, inputs = setup(tmp_path)
        if case == "stale_book":
            book = engine.books["101"]
            engine.books["101"] = replace(book, received_ns=book.received_ns-5_000_000_000)
        elif case == "stale_input": engine.directional.update(replace(inputs, received_at=clock[0]-timedelta(minutes=5)))
        elif case == "calendar": engine.directional.update(replace(inputs, calendar=None))
        elif case == "disarmed": engine.runtime.disarm_new_entries()
        elif case == "late": clock[0] += timedelta(minutes=2)
        elif case == "missing_option": engine.directional.update(replace(inputs, option_bars={}))
        elif case == "cash": broker.cash=D("10")
        elif case == "pending":
            from dhan_cas_bot.domain import Intent
            ledger.create_intent(Intent("pending","BUY",engine.books["101"].instrument,65,D(10),"p",clock[0],"x"),D(700))
            ledger.record_attempt("a", "pending", "UNKNOWN", {})
        assert not await engine.cycle()
        assert broker.requests == []
    asyncio.run(run())


def test_no_fill_signal_is_consumed_across_restart(tmp_path):
    async def run():
        engine, broker, ledger, clock, inputs = setup(tmp_path)
        broker.next_fill = 0
        assert await engine.cycle()
        await engine.cycle()
        restored = SessionEngine(engine.runtime, engine.books, now_fn=lambda:clock[0])
        restored.directional = DirectionalEngine(restored, (GAP,))
        restored.directional.update(inputs)
        assert not await restored.cycle()
        assert len(broker.requests) == 1
    asyncio.run(run())


def test_rebound_survives_overnight_and_disabled_strategy_still_manages_exit(tmp_path):
    async def run():
        engine, broker, ledger, clock, inputs = setup(tmp_path, REBOUND)
        sample = replace(inputs.evaluations[REBOUND], exit_at=at("2026-10-06","15:10"))
        engine.directional.update(replace(inputs, evaluations={REBOUND:sample}))
        assert await engine.cycle()
        clock[0] = at("2026-10-06","10:00")
        restored = SessionEngine(engine.runtime, {}, now_fn=lambda:clock[0])
        restored.directional = DirectionalEngine(restored, ())
        engine.runtime.disarm_new_entries()
        cal = replace(calendar("2026-10-06", "2026-10-07"), checked_at=at("2026-10-06","09:00"))
        book = replace(engine.books["101"], received_ns=int(clock[0].timestamp()*1e9))
        restored.on_book(book)
        restored.directional.update(Inputs(cal, {}, {}, clock[0], ""))
        assert not await restored.cycle()  # CAS signal absence is not an exit
        assert len(broker.requests) == 1
        clock[0] = at("2026-10-06","15:10")
        restored.on_book(replace(book, received_ns=int(clock[0].timestamp()*1e9)))
        restored.directional.update(Inputs(cal, {}, {}, clock[0], ""))
        assert await restored.cycle()
        assert broker.requests[-1]["transactionType"] == "SELL"
        await restored.cycle()
        assert restored.active is None
    asyncio.run(run())


def test_disarm_during_funds_read_prevents_dispatch(tmp_path):
    async def run():
        engine, broker, ledger, _, _ = setup(tmp_path)
        read = broker.funds
        async def disarm():
            engine.runtime.disarm_new_entries()
            return await read()
        broker.funds = disarm
        assert not await engine.cycle()
        assert not broker.requests
    asyncio.run(run())


def test_exit_is_not_blocked_by_wide_spread_and_cannot_reuse_stale_book(tmp_path):
    async def run():
        engine, broker, ledger, clock, inputs = setup(tmp_path)
        assert await engine.cycle()
        clock[0] = at(clock="15:34")
        engine.directional.update(replace(inputs, received_at=clock[0]))
        assert not await engine.cycle()  # old morning quote is unusable
        book=engine.books["101"]
        engine.on_book(replace(book, bids=(Level(D(1),650),), received_ns=int(clock[0].timestamp()*1e9)))
        assert await engine.cycle()  # spread policy applies only to buying
        assert broker.requests[-1]["transactionType"]=="SELL"
    asyncio.run(run())


def test_shared_cash_no_second_engine_entry_while_position_open(tmp_path):
    async def run():
        engine, broker, ledger, clock, inputs = setup(tmp_path)
        engine.directional.enabled=(GAP,REBOUND)
        engine.runtime.enabled_strategies=frozenset((GAP,REBOUND))
        second=replace(inputs.evaluations[GAP],strategy=REBOUND,exit_at=at("2026-10-06","15:10"))
        engine.directional.update(replace(inputs,evaluations={GAP:inputs.evaluations[GAP],REBOUND:second}))
        assert await engine.cycle()
        assert not await engine.cycle()
        assert len(broker.requests)==1
        assert ledger.db.execute("SELECT count(*) FROM lifecycles WHERE state!='CLOSED'").fetchone()[0]==1
    asyncio.run(run())


def test_minute_worker_to_production_oms_uses_only_known_bars(tmp_path):
    from dhan_cas_bot.strategy_inputs import StrategyInputWorker
    from tests.test_session_strategies import bars, futures
    async def run():
        engine, broker, ledger, clock, inputs = setup(tmp_path)
        # Use a new ledger/session so the hand-authored test signal above
        # cannot substitute for the actual detector in this integration case.
        ledger.db.execute("DELETE FROM metadata")
        engine.directional.signals.clear()
        engine.instruments={"101":engine.books["101"].instrument}
        clock[0]=at()+timedelta(seconds=2)
        worker=StrategyInputWorker(engine.directional,"fixture-token","99",wake=asyncio.Event(),stop=asyncio.Event())
        async def fetch_calendar(now): return calendar()
        async def fetch(security,segment,instrument,start,end,**kwargs):
            return bars() if security=="13" else futures() if security=="99" else inputs.option_bars["101"]
        worker.calendar_source.fetch=fetch_calendar
        worker.minutes.fetch=fetch
        await worker.refresh()
        assert engine.directional.inputs.evaluations[GAP].side=="CE"
        assert not await engine.cycle()  # processing window not reached
        clock[0]=at()+timedelta(minutes=1,seconds=3)
        engine.on_book(replace(engine.books["101"],received_ns=int(clock[0].timestamp()*1e9)))
        assert await engine.cycle()
        assert len(broker.requests)==1
        evidence=ledger.db.execute("SELECT payload FROM observations WHERE kind='STRATEGY_EVALUATION'").fetchone()
        assert json.loads(evidence[0])["side"]=="CE"
    asyncio.run(run())


def test_expired_directional_position_never_sends_an_expired_sell(tmp_path):
    async def run():
        engine, broker, ledger, clock, inputs = setup(tmp_path)
        assert await engine.cycle()
        clock[0]=at("2026-10-14","10:00")
        engine.directional.update(replace(inputs,calendar=calendar("2026-10-14","2026-10-15"),received_at=clock[0]))
        engine.on_book(replace(engine.books["101"],received_ns=int(clock[0].timestamp()*1e9)))
        assert not await engine.cycle()
        assert len(broker.requests)==1
        assert engine.runtime.status.state=="SETTLEMENT_PENDING"
    asyncio.run(run())
