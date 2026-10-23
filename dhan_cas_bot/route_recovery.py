"""Explicit flat-account repair using a positive Dhan cancel-all receipt.

The original POST outcome stays unknown. RECOVERY_CLOSED records a subsequent
broker-confirmed account reset, never a fictional original order/rejection.
No normal trading loop calls this operator-only operation.
"""
import asyncio
from datetime import datetime, timezone
import json
from zoneinfo import ZoneInfo

from .domain import ContractError, json_safe
from .profit_activation import require_owned_route_recovery, owned_route_digest

CONFIRMATION='all orders and positions exited successfully'
IST=ZoneInfo('Asia/Kolkata')


async def flat_read(broker,expected_account,now):
    started=now()
    funds,positions,orders,trades=await asyncio.gather(broker.funds(),broker.positions(),broker.orders(),broker.trades())
    completed=now()
    if broker.account_id!=expected_account or funds.broker_account!=expected_account:
        raise ContractError('recovery account mismatch')
    if not all(isinstance(v,list) for v in (positions,orders,trades)) or positions or orders or trades:
        raise ContractError('recovery requires an empty broker position/order/trade book')
    cash=funds.spendable_cash
    if not cash.is_finite() or cash<=0 or not started<=funds.observed_at<=completed:
        raise ContractError('recovery requires a fresh positive broker cash receipt')
    if (completed-started).total_seconds()>5:
        raise ContractError('recovery account read expired')
    return {'started_at':started,'completed_at':completed,'account':expected_account,
            'cash':cash,'positions':0,'orders':0,'trades':0}


async def recover_owned_route(ledger,broker,*,expected_account,apply=False,now_fn=None):
    """Caller must stop the trader and own writer.lock throughout this operation."""
    now=now_fn or (lambda:datetime.now(timezone.utc))
    if broker.account_id!=expected_account or (apply and broker.allow_writes is not True):
        raise ContractError('matching authorised write account required')
    pending=ledger.pending_intents()
    if not pending:
        row=ledger.db.execute("SELECT * FROM intents WHERE state='RECOVERY_CLOSED' ORDER BY created_at DESC LIMIT 1").fetchone()
        if row and ledger.recovery_closed_valid(row):return {'resolved':True,'already_resolved':True,'broker_reset_submitted':False}
        raise ContractError('no owned unknown route to recover')
    before=await flat_read(broker,expected_account,now)
    fingerprint=require_owned_route_recovery(ledger,[],[])
    row=pending[0];intent_id=row['intent_id'];prefix='route-reset:'+intent_id
    created=datetime.fromisoformat(row['created_at'])
    if created.tzinfo is None or created>now() or created.astimezone(IST).date()!=now().astimezone(IST).date():
        raise ContractError('cancel-all only covers the current trading day')
    attempt=ledger.db.execute('SELECT response FROM attempts WHERE intent_id=? ORDER BY sent_at DESC LIMIT 1',(intent_id,)).fetchone()
    if not attempt or json.loads(attempt['response']).get('error')!='HTTPStatusError':
        raise ContractError('a still-in-flight or transport-unknown POST requires different recovery')
    if ledger.db.execute('SELECT 1 FROM incidents WHERE incident_id=?',(prefix+':started',)).fetchone():
        raise ContractError('an existing recovery attempt must be investigated, never retried automatically')
    if not apply:return {'resolved':False,'preflight_passed':True,'broker_reset_submitted':False}
    ledger.incident(prefix+':started','ROUTE_RESET_STARTED',{'account':expected_account,
        'intent_digest':fingerprint,'preflight':json_safe(before)})
    try:
        response=await broker.exit_all_positions()
    except BaseException as exc:
        from .broker import request_failure_receipt
        ledger.incident(prefix+':failure','ROUTE_RESET_FAILED',request_failure_receipt(exc))
        raise
    acknowledged=now()
    if (not isinstance(response,dict) or response.get('status')!='SUCCESS'
            or ' '.join(str(response.get('message','')).lower().strip().rstrip('.').split())!=CONFIRMATION):
        ledger.incident(prefix+':unconfirmed','ROUTE_RESET_UNCONFIRMED',{'explicit_confirmation':False})
        raise ContractError('broker did not explicitly confirm cancellation of all orders and positions')
    ledger.incident(prefix+':ack','ROUTE_RESET_ACK',{'at':acknowledged.isoformat(),'status':'SUCCESS','message':CONFIRMATION})
    after=[await flat_read(broker,expected_account,now),await flat_read(broker,expected_account,now)]
    if any(r['started_at']<acknowledged or r['cash']!=before['cash'] for r in after):
        raise ContractError('post-reset reconciliation is inconsistent')
    evidence={'account':expected_account,'original_post_outcome':'UNKNOWN',
        'cancel_response':{'status':'SUCCESS','message':CONFIRMATION},
        'acknowledged_at':acknowledged,'preflight':before,'postflight':after,'intent_digest':fingerprint}
    # Atomic evidence plus terminal recovery state; no original attempt or order
    # identity is replaced, and no probe budget/counter is reset.
    with ledger.transaction() as db:
        if owned_route_digest(ledger)!=fingerprint:raise ContractError('route obligation changed during recovery')
        db.execute('INSERT INTO incidents VALUES(?,?,?,?)',(prefix+':complete','BROKER_ACCOUNT_RESET_CONFIRMED',
            json.dumps(json_safe(evidence),sort_keys=True),now().isoformat()))
        if db.execute("UPDATE intents SET state='RECOVERY_CLOSED' WHERE intent_id=? AND state='SEND_UNKNOWN'",(intent_id,)).rowcount!=1:
            raise ContractError('route obligation changed before commit')
    return {'resolved':True,'already_resolved':False,'broker_reset_submitted':True,
            'original_post_outcome':'UNKNOWN','cash':str(before['cash']),'probe_caps_unchanged':True}
