import asyncio
import httpx
import pytest
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
