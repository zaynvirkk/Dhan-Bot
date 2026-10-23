from datetime import datetime, timezone
from types import SimpleNamespace
import json
from dhan_cas_bot.ledger import Ledger
from dhan_cas_bot.dashboard.data import route_check_view
from tests.test_directional_engine import setup
from dhan_cas_bot.domain import Intent
from decimal import Decimal as D


def test_missing_order_identity_still_shows_today_unknown_http_route(tmp_path):
    e,b,l,clock,inputs=setup(tmp_path)
    t=clock[0];inst=e.books['101'].instrument
    i=Intent('unknown','BUY',inst,65,D('.05'),'correlation',t,'route-probe')
    l.create_intent(i,D(30));l.record_attempt('a',i.intent_id,'UNKNOWN',{'error':'HTTPStatusError',
        'http_status':400,'broker_error_code':'DH-905','broker_reason':'INVALID_IP','secret':'TOPSECRET'})
    result=route_check_view(l.db,t)
    assert result['state']=='SEND_UNKNOWN' and result['reason']=='HTTP_OUTCOME_UNKNOWN'
    assert result['http_status']==400 and result['broker_error_code']=='DH-905'
    assert result['broker_reason']=='INVALID_IP' and 'TOPSECRET' not in json.dumps(result)
    assert l.pending_intents()  # Displaying the error is not resolution.
