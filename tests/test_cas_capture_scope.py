import asyncio
from datetime import datetime
from decimal import Decimal as D

import pytest


@pytest.mark.parametrize('clock,expected', [('09:15:00',False),('15:04:59',False),
    ('15:05:00',True),('15:14:59',True),('15:45:00',True),('15:45:01',False)])
def test_flat_cas_capture_reserves_space_for_the_real_reference_and_auction(clock,expected):
    from dhan_cas_bot.replay_journal import capture_market
    at=datetime.fromisoformat('2026-10-21T'+clock+'+05:30')
    assert capture_market(at,has_directional=False,has_position=False) is expected


def test_directional_preopen_history_and_afterhours_managed_recovery_are_never_cut():
    from dhan_cas_bot.replay_journal import capture_market
    at=datetime.fromisoformat('2026-10-21T03:30:00+05:30')
    assert capture_market(at,has_directional=True,has_position=False)
    assert capture_market(at,has_directional=False,has_position=True)


def test_batch_waits_for_sparse_arrival_and_preserves_duplicate_receipts():
    from dhan_cas_bot.replay_journal import queued_capture_batch
    async def run():
        queue=asyncio.Queue()
        first={'received_ns':100,'processed_ns':120,'data_b64':'same'}
        second={'received_ns':101,'processed_ns':130,'data_b64':'same'}
        queue.put_nowait(first)
        task=asyncio.create_task(queued_capture_batch(queue,maximum_rows=2,maximum_wait=1))
        await asyncio.sleep(0)
        queue.put_nowait(second)
        assert await asyncio.wait_for(task,.5)==[first,second]
        assert queue._unfinished_tasks==2, 'Only durable writer may acknowledge receipts'
    asyncio.run(run())


def test_idle_tail_is_flushed_and_full_batch_does_not_consume_the_next_receipt():
    from dhan_cas_bot.replay_journal import queued_capture_batch
    async def run():
        queue=asyncio.Queue()
        for n in range(3):queue.put_nowait({'received_ns':n})
        batch=await queued_capture_batch(queue,maximum_rows=2,maximum_wait=.005)
        assert batch==[{'received_ns':0},{'received_ns':1}]
        tail=await asyncio.wait_for(queued_capture_batch(queue,maximum_wait=.005),.5)
        assert tail==[{'received_ns':2}]
        for _ in batch+tail:queue.task_done()
        await asyncio.wait_for(queue.join(),.1)
    asyncio.run(run())


def test_batch_round_trip_is_lossless_and_cap_failure_remains_closed(tmp_path):
    from dhan_cas_bot.replay_journal import ReplayJournal,read_capture
    at=datetime.fromisoformat('2026-10-21T15:05:00+05:30')
    rows=[{'received_ns':n,'processed_ns':n+9,'role':'market','epoch':'same',
           'data_b64':'unchanged-raw-packet'*20} for n in range(128)]
    journal=ReplayJournal(tmp_path,minimum_free=0,daily_cap=1000000)
    journal.write(rows,at)
    saved=list(read_capture(tmp_path/'replay-2026-10-21.jsonl.gz'))
    assert [{k:v for k,v in r.items() if k not in {'capture_id','sequence'}} for r in saved]==rows
    assert [r['sequence'] for r in saved]==list(range(1,129))
    before=(tmp_path/'replay-2026-10-21.jsonl.gz').read_bytes()
    journal.daily_cap=len(before)
    with pytest.raises(OSError,match='cap reached'):journal.write(rows,at)
    assert journal.health['state']=='CAP_REACHED'
    assert (tmp_path/'replay-2026-10-21.jsonl.gz').read_bytes()==before
