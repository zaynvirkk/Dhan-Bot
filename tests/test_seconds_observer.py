import asyncio
import httpx
import pytest
from decimal import Decimal
from types import SimpleNamespace
from dhan_cas_bot.domain import ContractError, Level
from dhan_cas_bot.seconds_observer import fetch_nifty_master


def test_master_stream_keeps_only_nifty_options_and_futures_without_full_body_read():
    async def run():
        header='SEGMENT,INSTRUMENT,UNDERLYING_SYMBOL,SECURITY_ID\n'
        payload=header+'NSE_FNO,OPTSTK,OTHER,99\n'+'NSE_FNO,OPTIDX,NIFTY,1\n'+'NSE_FNO,FUTIDX,NIFTY,2\n'
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request:httpx.Response(200,content=payload))) as client:
            result=await fetch_nifty_master(client=client)
        assert b'OTHER' not in result
        assert b'OPTIDX,NIFTY,1' in result and b'FUTIDX,NIFTY,2' in result
    asyncio.run(run())


def test_master_stream_rejects_oversized_or_missing_column_sources():
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request:httpx.Response(200,content=b'x'*100))) as client:
            with pytest.raises(ValueError):await fetch_nifty_master(client=client,max_bytes=50)
            with pytest.raises(ValueError):await fetch_nifty_master(client=client)
    asyncio.run(run())


def test_current_future_quote_does_not_misuse_last_trade_time_as_book_time():
    from dhan_cas_bot.seconds_strategies import future_quote_mid
    quote=SimpleNamespace(bids=(Level(Decimal('23000'),65),),asks=(Level(Decimal('23000.05'),65),),provider_ts_ms=1)
    assert future_quote_mid(quote)==Decimal('23000.025')
    for bids,asks in [((),quote.asks),(quote.bids,()),(quote.asks,quote.bids),
                      (quote.bids,(Level(Decimal('23100'),65),))]:
        with pytest.raises(ContractError):future_quote_mid(SimpleNamespace(bids=bids,asks=asks))
