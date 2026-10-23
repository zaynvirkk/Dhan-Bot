from types import SimpleNamespace
from datetime import timedelta
import json
import httpx
import pytest
from tests.test_session_strategies import at, calendar
from dhan_cas_bot.service import refresh_idle_session_state
from dhan_cas_bot.broker import request_failure_receipt


def runtime(state='WAITING_EXCHANGE_SESSION',pending=()):
    return SimpleNamespace(status=SimpleNamespace(state=state,reason='',auto_live_armed=True),
        ledger=SimpleNamespace(pending_intents=lambda:list(pending)))


def update(rt,**kwargs):
    defaults=dict(account_admitted=True,metadata_error='',funded={'VOLATILITY_SHOCK_V1'},
                  has_funded_directional=True,expiry_today=False,active=None)
    refresh_idle_session_state(rt,**(defaults|kwargs))


def test_verified_open_session_clears_preopen_state_without_granting_route_authority():
    rt=runtime();update(rt)
    assert rt.status.state=='ARMED_WAITING_SIGNAL'
    assert not hasattr(rt.status,'broker_route_verified')


@pytest.mark.parametrize('state',['RECOVERING','ENTRY_HALTED','POSITION_OPEN','ENTRY_PENDING','EXIT_PENDING','SETTLEMENT_PENDING'])
def test_session_open_does_not_erase_an_existing_recovery_or_position_state(state):
    rt=runtime(state);update(rt)
    assert rt.status.state==state


def test_unknown_probe_is_explicit_recovery_even_with_fresh_account_and_no_orders():
    rt=runtime(pending=[{'lifecycle_id':'route-probe','state':'SEND_UNKNOWN'}]);update(rt)
    assert rt.status.state=='RECOVERING' and rt.status.reason=='ROUTE_OUTCOME_UNKNOWN'
    update(rt,account_admitted=False)
    assert rt.status.state=='RECOVERING'  # Closing time cannot hide the liability.


def test_active_position_status_is_owned_by_existing_exit_manager():
    rt=runtime('POSITION_OPEN',pending=[{'lifecycle_id':'route-probe','state':'SEND_UNKNOWN'}])
    update(rt,active={'lifecycle_id':'held'})
    assert rt.status.state=='POSITION_OPEN'


def test_http_receipt_keeps_provider_code_without_tokens_or_arbitrary_error_text():
    request=httpx.Request('POST','https://fixture/orders?token=TOPSECRET',headers={'access-token':'TOPSECRET'})
    response=httpx.Response(400,request=request,json={'errorType':'Input_Exception','errorCode':'DH-905',
        'errorMessage':'Invalid IP TOPSECRET'})
    try:response.raise_for_status()
    except httpx.HTTPStatusError as exc:receipt=request_failure_receipt(exc)
    assert receipt['error']=='HTTPStatusError' and receipt['http_status']==400
    assert receipt['broker_error_code']=='DH-905' and receipt['broker_reason']=='INVALID_IP'
    assert 'TOPSECRET' not in json.dumps(receipt)


def test_timeout_and_non_json_error_do_not_fabricate_rejection():
    assert request_failure_receipt(TimeoutError('TOPSECRET'))=={'error':'TimeoutError'}
    r=httpx.Response(502,request=httpx.Request('POST','https://fixture/orders'),text='TOPSECRET')
    try:r.raise_for_status()
    except httpx.HTTPStatusError as exc:receipt=request_failure_receipt(exc)
    assert receipt['http_status']==502 and 'TOPSECRET' not in json.dumps(receipt)
    assert not receipt.get('definitively_rejected',False)


def test_gateway_error_schema_retains_inner_cause_with_credentials_redacted():
    request=httpx.Request('POST','https://fixture/orders',headers={'access-token':'TOPSECRET','client-id':'1234567890'})
    response=httpx.Response(400,request=request,json={'errorCode':'BAD_REQUEST_ERROR',
        'internalErrorCode':'RS-9005','internalErrorMessage':'todo mandatory fields; token TOPSECRET account 1234567890'})
    try:response.raise_for_status()
    except httpx.HTTPStatusError as exc:receipt=request_failure_receipt(exc)
    assert receipt['broker_internal_error_code']=='RS-9005'
    assert 'mandatory fields' in receipt['broker_message']
    assert 'TOPSECRET' not in json.dumps(receipt) and '1234567890' not in json.dumps(receipt)


def test_real_http_adapter_and_oms_keep_error_receipt_without_retry(tmp_path):
    import asyncio
    from decimal import Decimal as D
    from tests.test_directional_engine import setup
    from dhan_cas_bot.broker import DhanBroker
    from dhan_cas_bot.orders import OrderManager
    from dhan_cas_bot.domain import Intent
    async def run():
        e,b,l,c,_=setup(tmp_path);requests=[]
        def rejected(request):
            requests.append(request)
            return httpx.Response(400,json={'errorCode':'DH-905','errorType':'Input_Exception',
                'errorMessage':'invalid input TOPSECRET'})
        broker=DhanBroker(b.account_id,'TOPSECRET',allow_writes=True)
        broker.client=httpx.AsyncClient(transport=httpx.MockTransport(rejected))
        try:
            intent=Intent('r','BUY',e.books['101'].instrument,65,D('.05'),'r',c[0],'route-probe')
            with pytest.raises(httpx.HTTPStatusError):
                await OrderManager(l,broker).submit(intent,reserved_cash=D(30))
            receipt=json.loads(l.db.execute('SELECT response FROM attempts').fetchone()[0])
            assert receipt['http_status']==400 and receipt['broker_error_code']=='DH-905'
            assert 'TOPSECRET' not in json.dumps(receipt) and len(requests)==1
            assert l.pending_intents()[0]['state']=='SEND_UNKNOWN'
            assert not l.db.execute('SELECT 1 FROM orders').fetchone()
        finally:await broker.close()
    asyncio.run(run())
