from datetime import timedelta
from types import SimpleNamespace as S
from dhan_cas_bot.stream_minutes import CompletedIndexMinutes
from dhan_cas_bot.upstox_signal import NIFTY_KEY
from tests.test_session_strategies import at


def frame(start='09:59',stamp='10:00',kind=1,close=10):
    row=S(interval='I1',ts=int(at(clock=start).timestamp()*1000),open=10,high=max(11,close),low=9,close=close,vol=0)
    return S(type=kind,currentTs=int(at(clock=stamp).timestamp()*1000),feeds={NIFTY_KEY:S(fullFeed=S(indexFF=S(marketOHLC=S(ohlc=[row]))))})


def test_stream_does_not_create_completed_bars_from_forming_future_or_snapshot():
    source=CompletedIndexMinutes()
    for value in (frame(start='10:00'),frame(start='10:01'),frame(kind=0),frame(stamp='10:01')):
        assert not source.accept(value,'epoch-1',at(clock='10:00'))
    assert source.rows=={}


def test_stream_reconnect_conflict_and_stale_receipt_require_rest_repair():
    source=CompletedIndexMinutes()
    assert source.accept(frame(),'epoch-1',at(clock='10:00'))
    assert source.current(at(clock='10:00')) is not None
    assert not source.accept(frame(close=12),'epoch-1',at(clock='10:00'))
    assert source.current(at(clock='10:00')) is None
    source.reset()
    assert source.accept(frame(),'epoch-2',at(clock='10:00'))
    assert source.current(at(clock='10:02')) is None
    source.reset()
    assert source.current(at(clock='10:00')) is None


def test_rest_baseline_cannot_skip_a_missing_stream_minute():
    import asyncio
    from dhan_cas_bot.strategy_inputs import MinuteSource
    from dhan_cas_bot.session_strategies import Bar
    from decimal import Decimal as D
    class Broker:
        calls=0
        async def _request(self,*args,**kwargs):
            self.calls+=1
            return {k:[] for k in ('timestamp','open','high','low','close','volume')}
    async def run():
        stream=CompletedIndexMinutes();stream.accept(frame(),'epoch',at(clock='10:00'))
        broker=Broker();source=MinuteSource(broker,now_fn=lambda:at(clock='10:00'),stream=stream)
        key=('13','IDX_I','INDEX',False,at(clock='09:15'))
        t=at(clock='09:57');source.cache[key]={t:Bar(t,D(10),D(10),0,0,D(11),D(9))}
        await source.fetch(*key[:3],key[4],at(clock='10:00'))
        assert broker.calls==1
    asyncio.run(run())


def test_complete_stream_minute_replaces_rest_on_a_contiguous_baseline():
    import asyncio
    from dhan_cas_bot.strategy_inputs import MinuteSource
    from dhan_cas_bot.session_strategies import Bar
    from decimal import Decimal as D
    class Broker:
        async def _request(self,*args,**kwargs):raise AssertionError('stream unnecessarily polled REST')
    async def run():
        stream=CompletedIndexMinutes();stream.accept(frame(),'epoch',at(clock='10:00'))
        source=MinuteSource(Broker(),now_fn=lambda:at(clock='10:00'),stream=stream)
        key=('13','IDX_I','INDEX',False,at(clock='09:15'))
        t=at(clock='09:59');source.cache[key]={t:Bar(t,D(10),D(10),0,0,D(11),D(9))}
        rows=await source.fetch(*key[:3],key[4],at(clock='10:00'))
        assert at(clock='10:00') in rows
        assert source.spot_source=='UPSTOX_COMPLETED_I1_STREAM'
    asyncio.run(run())
