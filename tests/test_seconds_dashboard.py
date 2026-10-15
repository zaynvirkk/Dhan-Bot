from datetime import datetime,timezone
import json
from dhan_cas_bot.dashboard.data import seconds_view

NOW=datetime(2026,10,15,8,tzinfo=timezone.utc)


def test_paper_results_cannot_become_money_permission_or_expose_provider_data():
    raw={'mode':'SIMULATION','writes_to_broker':False,'observed_at':NOW.isoformat(),
         'token':'PRIVATE','results':[{'strategy':'SECONDS_FUTURES_CATCHUP','cash':'7805','net':'12','signals':1,
           'entries':1,'closed':1,'missed':0,'broker_order_id':'PRIVATE','last_result':'MODEL_CLOSED'}]}
    out=seconds_view(raw,NOW)
    assert out['mode']=='SIMULATION' and out['writes_to_broker'] is False
    assert out['results'][0]['net']=='12.00'
    assert 'PRIVATE' not in json.dumps(out) and 'authority' not in out
    raw['writes_to_broker']=True
    assert seconds_view(raw,NOW) is None


def test_stale_experiment_signal_is_never_displayed_as_current():
    raw={'mode':'SIMULATION','writes_to_broker':False,'observed_at':'2026-10-15T07:00:00Z',
         'evaluations':[{'strategy':'SECONDS_EVENT_IMPULSE','state':'SIGNAL','side':'CE'}]}
    out=seconds_view(raw,NOW)
    assert not out['fresh']
    assert out['evaluations'][0]['state']=='UNKNOWN' and out['evaluations'][0]['side'] is None
