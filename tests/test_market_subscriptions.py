import asyncio
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal as D
from types import SimpleNamespace
import json

from dhan_cas_bot.domain import OptionType

from tests.test_seconds_strategies import seeded_tape, NOW


def catalogue():
    _,books,_=seeded_tape()
    base=next(iter(books.values())).instrument
    return {str(10000+e*1000+k*2+s):replace(base,security_id=str(10000+e*1000+k*2+s),
        expiry=base.expiry+timedelta(days=e*7),strike=D(20000+k*50),
        option_type=OptionType(side))
        for e in range(3) for k in range(121) for s,side in enumerate(('CE','PE'))}


def test_subscription_window_covers_both_existing_selectors_and_preserves_holding():
    from dhan_cas_bot.market_subscriptions import market_ids
    cat=catalogue();day=NOW.date();anchors=(D(23000),D(23130));held={next(iter(cat))}
    selected=market_ids(cat,day,anchors=anchors,held=held,future_id='future')
    assert held|{'future'}<=selected and len(selected)<200
    for expiry in sorted({i.expiry for i in cat.values()}):
        for anchor in anchors:
            nearest=sorted((i for i in cat.values() if i.expiry==expiry),key=lambda i:(abs(i.strike-anchor),i.security_id))[:24]
            assert {i.security_id for i in nearest}<=selected
    shifted=market_ids(cat,day,anchors=(D(25000),),held=held,future_id='future')
    assert shifted!=selected and held<=shifted


def test_unknown_anchor_cannot_invent_a_chain_and_expiry_cas_keeps_full_coverage():
    from dhan_cas_bot.market_subscriptions import market_ids
    cat=catalogue();day=min(i.expiry for i in cat.values());held={next(reversed(cat))}
    assert market_ids(cat,day,anchors=(),held=held,future_id='future')==held|{'future'}
    ids=market_ids(cat,day,anchors=(D(23000),),held=held,future_id='future',full_expiry=day)
    assert {i.security_id for i in cat.values() if i.expiry==day}<=ids
    assert held|{'future'}<=ids


def test_dynamic_subscriptions_add_before_removal_and_never_reconnect():
    from dhan_cas_bot.market_subscriptions import MarketSubscriptions
    async def run():
        sent=[]
        class Socket:
            async def send(self,value):sent.append(json.loads(value))
        socket=Socket();runner=SimpleNamespace(socket=socket,subscriptions_ready=True)
        policy=MarketSubscriptions({'future'})
        books={'old':object(),'held':object()}
        assert await policy.sync(runner,'epoch-1',{'future','old','held'},books)
        sent.clear()
        assert await policy.sync(runner,'epoch-1',{'future','new','held'},books)
        assert [r['RequestCode'] for r in sent]==[21,22]
        assert sent[0]['InstrumentList']==[{'ExchangeSegment':'NSE_FNO','SecurityId':'new'}]
        assert 'held' in books and 'old' not in books
        sent.clear();assert await policy.sync(runner,'epoch-1',{'future','new','held'},books)
        assert sent==[] and runner.socket is socket
    asyncio.run(run())


def test_subscription_failure_cannot_claim_coverage_or_keep_removed_books():
    from dhan_cas_bot.market_subscriptions import MarketSubscriptions
    async def run():
        closed=[]
        class Socket:
            async def send(self,value):raise TimeoutError()
            async def close(self):closed.append(True)
        runner=SimpleNamespace(socket=Socket(),subscriptions_ready=True)
        policy=MarketSubscriptions({'future'});books={'old':object()}
        assert not await policy.sync(runner,'epoch-1',{'future','new'},books)
        assert policy.last_error=='TimeoutError' and closed==[True]
        assert 'new' not in policy.applied
    asyncio.run(run())


def test_reconnect_replays_desired_additions_after_bootstrap_and_batches_at_100():
    from dhan_cas_bot.market_subscriptions import MarketSubscriptions
    async def run():
        sent=[]
        class Socket:
            async def send(self,value):sent.append(json.loads(value))
        runner=SimpleNamespace(socket=Socket(),subscriptions_ready=False)
        policy=MarketSubscriptions({'future'})
        desired={'future'}|{str(i) for i in range(250)}
        assert not await policy.sync(runner,'first',desired,{})
        assert sent==[] and policy.applied==set()
        runner.subscriptions_ready=True
        assert await policy.sync(runner,'first',desired,{})
        assert [x['InstrumentCount'] for x in sent]==[100,100,50]
        sent.clear();runner.socket=Socket()
        assert await policy.sync(runner,'next',desired,{})
        assert [x['InstrumentCount'] for x in sent]==[100,100,50]
        assert policy.applied==desired
    asyncio.run(run())


def test_minute_window_covers_atm_and_four_outward_strikes_on_both_sides():
    from dhan_cas_bot.market_subscriptions import market_ids
    cat=catalogue();anchor=D(23017)
    ids=market_ids(cat,NOW.date(),anchors=(anchor,))
    for expiry in {i.expiry for i in cat.values()}:
        for side in OptionType:
            rows=[i for i in cat.values() if i.expiry==expiry and i.option_type==side]
            atm=min(rows,key=lambda i:abs(i.strike-anchor)).strike
            outward=sorted((i for i in rows if i.strike>=atm),key=lambda i:i.strike) if side==OptionType.CE else sorted((i for i in rows if i.strike<=atm),key=lambda i:-i.strike)
            assert {i.security_id for i in outward[:5]}<=ids
