"""Positive broker cancellation receipts, never absence-only order resolution."""
import asyncio
from datetime import datetime, timezone, timedelta
from decimal import Decimal as D
import json

import httpx
import pytest

from dhan_cas_bot.domain import ContractError, FundsSnapshot, Intent, Fill
from dhan_cas_bot.orders import OrderManager
from tests.test_directional_engine import setup


def fixture(tmp_path):
    e,b,l,_,_=setup(tmp_path)
    stamp=datetime.now(timezone.utc)
    inst=e.books['101'].instrument
    i=Intent('unknown','BUY',inst,65,D('.05'),'correlation',stamp,'route-probe')
    l.create_intent(i,D(30));l.record_attempt('original','unknown','UNKNOWN',{'error':'HTTPStatusError'})
    l.set_counter('probe.attempts:'+stamp.astimezone(__import__('zoneinfo').ZoneInfo('Asia/Kolkata')).date().isoformat(),1)
    l.set_counter('probe.spent',D(30))
    class Broker:
        account_id=b.account_id
        allow_writes=True
        resets=0
        cash=D('7772.25')
        result={'status':'SUCCESS','message':'All orders and positions exited successfully'}
        positions_rows=[]
        order_rows=[]
        trade_rows=[]
        fail_after=False
        async def funds(self):
            if self.resets and self.fail_after:raise TimeoutError()
            return FundsSnapshot(datetime.now(timezone.utc),self.cash,self.cash,self.cash,D(0),self.account_id)
        async def positions(self):return self.positions_rows
        async def orders(self):return self.order_rows
        async def trades(self):return self.trade_rows
        async def exit_all_positions(self):
            self.resets+=1
            if isinstance(self.result,Exception):raise self.result
            return self.result
    return l,Broker(),i


@pytest.mark.parametrize('fault',['position','order','trade','wrong_account','readonly','foreign_intent','timeout_attempt','old_day','inflight_recovery'])
def test_reset_never_dispatches_with_unverified_or_unowned_state(tmp_path,fault):
    from dhan_cas_bot.route_recovery import recover_owned_route
    l,b,i=fixture(tmp_path)
    if fault=='position':b.positions_rows=[{'netQty':65}]
    if fault=='order':b.order_rows=[{'orderStatus':'PENDING'}]
    if fault=='trade':b.trade_rows=[{'tradedQuantity':65}]
    if fault=='wrong_account':b.account_id='FOREIGN'
    if fault=='readonly':b.allow_writes=False
    if fault=='foreign_intent':l.db.execute("UPDATE intents SET lifecycle_id='foreign'")
    if fault=='timeout_attempt':l.db.execute("UPDATE attempts SET response=?",(json.dumps({'error':'TimeoutError'}),))
    if fault=='old_day':l.db.execute('UPDATE intents SET created_at=?',((i.created_at-timedelta(days=1)).isoformat(),))
    if fault=='inflight_recovery':l.incident('route-reset:unknown:started','ROUTE_RESET_STARTED',{})
    with pytest.raises((ValueError,ContractError)):asyncio.run(recover_owned_route(l,b,expected_account='TEST',apply=True))
    assert b.resets==0 and l.pending_intents()[0]['state']=='SEND_UNKNOWN'


@pytest.mark.parametrize('result',[{'status':'ERROR','message':'All orders and positions exited successfully'}, {},
    {'status':'SUCCESS','message':'No positions found'},TimeoutError()])
def test_unknown_or_incomplete_cancel_all_receipt_cannot_release_unknown(tmp_path,result):
    from dhan_cas_bot.route_recovery import recover_owned_route
    l,b,_=fixture(tmp_path);b.result=result
    with pytest.raises((ValueError,ContractError,TimeoutError)):asyncio.run(recover_owned_route(l,b,expected_account='TEST',apply=True))
    assert b.resets==1 and l.pending_intents()[0]['state']=='SEND_UNKNOWN'
    assert l.lifecycle_totals('route-probe')['reserved']==30


def test_post_cancel_read_failure_never_releases_reservation(tmp_path):
    from dhan_cas_bot.route_recovery import recover_owned_route
    l,b,_=fixture(tmp_path);b.fail_after=True
    with pytest.raises(TimeoutError):asyncio.run(recover_owned_route(l,b,expected_account='TEST',apply=True))
    assert b.resets==1 and l.pending_intents()


def test_empty_reads_without_apply_cannot_close_unknown(tmp_path):
    from dhan_cas_bot.route_recovery import recover_owned_route
    l,b,_=fixture(tmp_path)
    assert not asyncio.run(recover_owned_route(l,b,expected_account='TEST'))['resolved']
    assert b.resets==0 and l.pending_intents()


def test_recovery_closed_state_without_broker_receipt_remains_unresolved(tmp_path):
    l,b,_=fixture(tmp_path)
    l.db.execute("UPDATE intents SET state='RECOVERY_CLOSED'")
    assert l.pending_intents() and l.lifecycle_totals('route-probe')['unresolved']


@pytest.mark.parametrize('fault',['cash','position','order','trade'])
def test_new_post_cancel_broker_activity_cannot_release_unknown(tmp_path,fault):
    from dhan_cas_bot.route_recovery import recover_owned_route
    l,b,_=fixture(tmp_path);reset=b.exit_all_positions
    async def change():
        result=await reset()
        if fault=='cash':b.cash-=1
        if fault=='position':b.positions_rows=[{'netQty':65}]
        if fault=='order':b.order_rows=[{'orderStatus':'PENDING'}]
        if fault=='trade':b.trade_rows=[{'tradedQuantity':65}]
        return result
    b.exit_all_positions=change
    with pytest.raises(ContractError):asyncio.run(recover_owned_route(l,b,expected_account='TEST',apply=True))
    assert b.resets==1 and l.pending_intents()


def test_positive_cancel_all_and_post_receipts_close_liability_without_faking_original_status(tmp_path):
    from dhan_cas_bot.route_recovery import recover_owned_route
    l,b,_=fixture(tmp_path);counters=[tuple(r) for r in l.db.execute('SELECT * FROM counters ORDER BY name')]
    result=asyncio.run(recover_owned_route(l,b,expected_account='TEST',apply=True))
    assert result['resolved'] and b.resets==1 and not l.pending_intents()
    row=l.db.execute('SELECT * FROM intents').fetchone()
    assert row['state']=='RECOVERY_CLOSED' and row['reserved_cash']=='30'
    assert json.loads(l.db.execute('SELECT response FROM attempts').fetchone()[0])['error']=='HTTPStatusError'
    assert not l.db.execute('SELECT * FROM orders').fetchone() and not l.db.execute('SELECT * FROM fills').fetchone()
    totals=l.lifecycle_totals('route-probe')
    assert totals['quantity']==0 and totals['reserved']==0 and not totals['unresolved']
    assert [tuple(r) for r in l.db.execute('SELECT * FROM counters ORDER BY name')]==counters
    assert l.db.execute("SELECT 1 FROM incidents WHERE kind='BROKER_ACCOUNT_RESET_CONFIRMED'").fetchone()
    # A repeat command returns the saved receipt without another broker reset.
    assert asyncio.run(recover_owned_route(l,b,expected_account='TEST',apply=True))['already_resolved']
    assert b.resets==1


@pytest.mark.parametrize('kind',['order','fill'])
def test_late_broker_evidence_reopens_recovery_closed_obligation(tmp_path,kind):
    from dhan_cas_bot.route_recovery import recover_owned_route
    l,b,i=fixture(tmp_path);asyncio.run(recover_owned_route(l,b,expected_account='TEST',apply=True))
    if kind=='order':l.record_order('late',i.intent_id,b.account_id,'PENDING',{})
    else:l.record_fill_once(Fill('t','late',i.instrument.security_id,65,D('.05'),D(0),datetime.now(timezone.utc)),i.intent_id,{})
    assert l.pending_intents()[0]['state']=='SENT'
    assert l.lifecycle_totals('route-probe')['unresolved']


def test_raw_write_and_cancel_all_adapter_cannot_bypass_readonly_boundary():
    from dhan_cas_bot.broker import DhanBroker
    async def run():
        calls=[];b=DhanBroker('TEST','PRIVATE',allow_writes=False)
        b.client=httpx.AsyncClient(transport=httpx.MockTransport(lambda r:calls.append(r)))
        try:
            with pytest.raises(ContractError):await b.exit_all_positions()
            with pytest.raises(ContractError):await b._request('DELETE','/positions')
            assert not calls
        finally:await b.close()
    asyncio.run(run())
