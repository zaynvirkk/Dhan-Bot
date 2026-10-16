"""Session-review and isolated-input counterexamples, never profit evidence."""
import asyncio, json, gzip
from datetime import datetime, timezone, timedelta
from decimal import Decimal as D
from types import SimpleNamespace
import pytest
from dhan_cas_bot.ledger import Ledger
from tests.test_connected_service import full_packet

NOW=datetime(2026,10,16,5,tzinfo=timezone.utc)


def test_repeated_valid_future_book_refreshes_receipt_without_inventing_a_move():
    from dhan_cas_bot.future_input import FutureInput
    from dhan_cas_bot.seconds_strategies import SecondsTape
    tape=SecondsTape();ns=int(NOW.timestamp()*1e9)
    feed=FutureInput(tape,'100',lambda:'option-epoch')
    packet=full_packet(100,23000,23000.05)
    feed.connect();feed.receive(packet,ns)
    feed.receive(packet,ns+2_000_000_000)
    assert tape.future_current(NOW+timedelta(seconds=2))
    assert tape.future[-1][1]==tape.future[0][1]
    feed.disconnect()
    assert not tape.future_current(NOW+timedelta(seconds=2))
    assert feed.health(NOW+timedelta(seconds=2))['reason']=='FUTURES_DISCONNECTED'


def test_bad_future_packet_never_becomes_a_fresh_input():
    from dhan_cas_bot.future_input import FutureInput
    from dhan_cas_bot.seconds_strategies import SecondsTape
    tape=SecondsTape();ns=int(NOW.timestamp()*1e9)
    feed=FutureInput(tape,'100',lambda:'option-epoch');feed.connect()
    feed.receive(full_packet(100,23000,23000.05),ns)
    feed.receive(b'broken',ns+100_000_000)
    assert not tape.future_current(NOW+timedelta(seconds=.1))
    assert feed.health(NOW+timedelta(seconds=.1))['reason']=='FUTURES_PACKET_REJECTED'


def test_continuous_capture_keeps_repeated_receipts_and_caps_visibly(tmp_path):
    from dhan_cas_bot.replay_journal import ReplayJournal,read_capture
    journal=ReplayJournal(tmp_path,minimum_free=0,daily_cap=100000)
    journal.write([{'role':'market','epoch':'e','received_ns':1,'data_b64':'YWJj'},
                   {'role':'market','epoch':'e','received_ns':2,'data_b64':'YWJj'}],NOW)
    rows=list(read_capture(tmp_path/'replay-2026-10-16.jsonl.gz'))
    assert [r['received_ns'] for r in rows]==[1,2]
    assert rows[0]['sequence']<rows[1]['sequence']
    assert journal.health['state']=='RECORDING'
    before=(tmp_path/'replay-2026-10-16.jsonl.gz').read_bytes()
    journal.daily_cap=1
    with pytest.raises(OSError):journal.write([{'role':'future','epoch':'e','received_ns':3,'data_b64':'ZA=='}],NOW)
    assert journal.health['state']=='CAP_REACHED'
    assert (tmp_path/'replay-2026-10-16.jsonl.gz').read_bytes()==before


def test_session_review_does_not_label_a_gross_win_as_net_without_charges(tmp_path):
    from dhan_cas_bot.dashboard.learning import session_reviews
    ledger=Ledger(tmp_path/'ledger')
    try:
        ledger.db.execute("INSERT INTO lifecycles VALUES('l','2026-10-16','100','1000','CLOSED',?)",(json.dumps({'strategy':'SECONDS_FUTURES_CATCHUP','instrument':{'strike':'23000','option_type':'CE'}}),))
        for ident,side,price,sec in [('a','BUY','10',0),('b','SELL','10.2',5)]:
            ledger.db.execute("INSERT INTO intents VALUES(?,?,?,?,?,?,?,?,?,?,?)",(ident,ident,'l',side,'100',65,price,'FILLED','0','{}',(NOW+timedelta(seconds=sec)).isoformat()))
            ledger.db.execute("INSERT INTO fills VALUES(?,?,?,?,?,?,?,?,?)",(ident,ident,ident,'100',65,price,'0',(NOW+timedelta(seconds=sec)).isoformat(),'{}'))
        ledger.put_metadata('directional-exit:l',{'reason':'SECONDS_INPUT_LOST','due':NOW.isoformat()})
        out=session_reviews(ledger.db,NOW)
        day=out['days'][0]
        assert day['gross_pnl']=='13.00' and day['net_pnl'] is None
        assert day['charges_complete'] is False
        assert day['input_loss_exits']==1
        assert day['trades'][0]['exit_reason']=='SECONDS_INPUT_LOST'
        assert day['trades'][0]['net_pnl'] is None
    finally:ledger.close()


def test_review_cash_memory_survives_restart_and_rejects_failed_reads(tmp_path):
    from dhan_cas_bot.dashboard.learning import remember_cash
    def report(cash,ok=True):return {'account_read_ok':ok,'account':{'fresh':True,'available_cash':cash,'observed_at':NOW.isoformat()}}
    path=tmp_path/'learning-cash.json'
    remember_cash(path,report('1000'),NOW)
    second=report('1100');second['account']['observed_at']=(NOW+timedelta(seconds=10)).isoformat()
    remember_cash(path,second,NOW+timedelta(seconds=10))
    out=remember_cash(path,report('0',False),NOW+timedelta(seconds=20))
    assert out['days'][0]['first_cash']=='1000.00'
    assert out['days'][0]['last_cash']=='1100.00'
    assert out['days'][0]['cash_change']=='100.00'
    assert '1100.00' in path.read_text()


def test_learning_keeps_last_review_if_live_database_temporarily_fails(tmp_path):
    from dhan_cas_bot.dashboard.learning import build_learning
    previous={'schema':1,'status':'AVAILABLE','observed_at':NOW.isoformat(),'days':[{'date':'2026-10-13','gross_pnl':'2791.75'}],'lessons':[]}
    (tmp_path/'learning.json').write_text(json.dumps(previous))
    value=build_learning({'state_dir':str(tmp_path/'missing')},tmp_path/'snapshot.json',{},NOW+timedelta(minutes=1))
    assert value['status']=='STALE' and value['days']==previous['days']
    assert value['observed_at']==previous['observed_at']


def test_production_observation_sink_does_not_fsync_on_the_quote_callback(tmp_path,monkeypatch):
    from dhan_cas_bot.seconds_engine import SecondsEngine
    from tests.test_seconds_strategies import seeded_tape
    from dhan_cas_bot.seconds_strategies import NAMES
    tape,books,calendar=seeded_tape();ledger=Ledger(tmp_path/'sink')
    queued=[]
    runtime=SimpleNamespace(ledger=ledger,observation_sink=lambda rows:queued.append(rows))
    engine=SimpleNamespace(now=lambda:NOW,books=books,runtime=runtime)
    seconds=SecondsEngine(SimpleNamespace(engine=engine,inputs=SimpleNamespace(calendar=calendar),enabled=NAMES));seconds.tape=tape
    monkeypatch.setattr(ledger,'observe_batch',lambda *args:pytest.fail('quote path blocked on durable observation I/O'))
    try:
        seconds.refresh(force=True)
        assert len(queued)==1 and len(queued[0])==5
    finally:ledger.close()


def test_review_archive_preserves_older_sessions_outside_recent_ledger_window(tmp_path):
    from dhan_cas_bot.dashboard.learning import archive_reviews
    path=tmp_path/'session-memory.json'
    first={'schema':1,'status':'AVAILABLE','days':[{'date':'2026-10-13','gross_pnl':'2791.75'}]}
    archive_reviews(path,first)
    second=archive_reviews(path,{'schema':1,'status':'AVAILABLE','days':[{'date':'2026-10-16','gross_pnl':'367.25'}]})
    assert [r['date'] for r in second['days']]==['2026-10-16','2026-10-13']
    assert json.loads(path.read_text())['days'][1]['gross_pnl']=='2791.75'


def test_late_pong_after_cancelled_ping_does_not_crash_the_connection():
    from websockets.asyncio.connection import Connection
    async def run():
        connection=Connection.__new__(Connection)
        connection.loop=asyncio.get_running_loop()
        waiter=connection.loop.create_future();waiter.cancel()
        connection.pong_waiters={b'late':(waiter,connection.loop.time())}
        connection.acknowledge_pings(b'late')
        assert connection.pong_waiters=={} and waiter.cancelled()
    asyncio.run(run())


def test_release_proof_covers_shipped_lessons_and_browser_code(tmp_path):
    from dhan_cas_bot.release import source_digest
    root=tmp_path/'dhan_cas_bot/dashboard';(root/'static').mkdir(parents=True)
    (root/'lessons.json').write_text('[]')
    (root/'static/app.js').write_text('original')
    before=source_digest(tmp_path)
    (root/'lessons.json').write_text('[{"date":"2026-10-16"}]')
    after=source_digest(tmp_path)
    assert before!=after
    (root/'static/app.js').write_text('changed')
    assert source_digest(tmp_path)!=after


def test_oi_only_message_cannot_refresh_futures_quote_health():
    import struct
    from dhan_cas_bot.future_input import FutureInput
    from dhan_cas_bot.seconds_strategies import SecondsTape
    tape=SecondsTape();ns=int(NOW.timestamp()*1e9)
    feed=FutureInput(tape,'100',lambda:'e');feed.connect()
    feed.receive(full_packet(100,23000,23000.05),ns)
    oi=struct.pack('<BHBI',5,12,2,100)+struct.pack('<I',1000)
    assert feed.receive(oi,ns+2_000_000_000) is False
    assert feed.health(NOW+timedelta(seconds=2))['current'] is False


def test_health_only_refresh_cannot_erase_archived_trade_results(tmp_path):
    from dhan_cas_bot.dashboard.learning import archive_reviews
    path=tmp_path/'memory.json'
    first={'schema':1,'status':'AVAILABLE','days':[{'date':'2026-10-13','closed_trades':16,'gross_pnl':'2791.75'}]}
    archive_reviews(path,first)
    out=archive_reviews(path,{'schema':1,'status':'AVAILABLE','days':[{'date':'2026-10-13','closed_trades':0,'gross_pnl':'0.00','health':{'samples':10}}]})
    assert out['days'][0]['gross_pnl']=='2791.75'
    assert out['days'][0]['health']['samples']==10


def test_provider_future_disconnect_reaches_transport_reconnect_handler():
    import struct
    from dhan_cas_bot.future_input import FutureInput
    from dhan_cas_bot.dhan_feed import DhanFeedDisconnect
    from dhan_cas_bot.seconds_strategies import SecondsTape
    feed=FutureInput(SecondsTape(),'100',lambda:'e');feed.connect()
    frame=struct.pack('<BHBIH',50,10,2,100,805)
    with pytest.raises(DhanFeedDisconnect):feed.receive(frame,int(NOW.timestamp()*1e9))
