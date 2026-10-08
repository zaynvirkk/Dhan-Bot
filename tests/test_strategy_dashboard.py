from datetime import datetime, timezone
import json

from dhan_cas_bot.dashboard.data import runtime_view


def test_strategy_rows_are_allowlisted_not_raw_provider_errors():
    now=datetime(2026,10,6,4,0,tzinfo=timezone.utc)
    raw={"observed_at":now.isoformat(),"strategies":["GAP_FADE_DOUBLE","secret"],
         "strategy_evaluations":[{"strategy":"GAP_FADE_DOUBLE","state":"SIGNAL","enabled":True,
            "reason":"GAP_FADE_CONFIRMED","evaluated_at":now.isoformat(),"side":"CE",
            "details":{"gap":"-.008", "access_token":"sensitive"},"password":"private"},
            {"strategy":"NIFTY_SELLOFF_REBOUND_1510","state":"UNKNOWN","reason":"provider token secret"}]}
    result=runtime_view(raw,now)
    assert result["strategies"]==["GAP_FADE_DOUBLE"]
    assert result["strategy_evaluations"][0]["details"]["gap"]=="-0.008"
    assert "sensitive" not in json.dumps(result) and "private" not in json.dumps(result) and "secret" not in json.dumps(result)
    assert result["strategy_evaluations"][1]["reason"]=="UNKNOWN"


def test_condition_projection_preserves_precision_and_filters_private_text():
    now=datetime(2026,10,8,4,15,tzinfo=timezone.utc)
    raw={'observed_at':now.isoformat(),'strategy_evaluations':[{'strategy':'GAP_FADE_DOUBLE',
         'state':'NO_SIGNAL','reason':'GAP_FADE_CONDITIONS_NOT_MET','next_check_at':now.isoformat(),
         'details':{'persistent':False},'conditions':[
             {'key':'gap_size','state':'FAIL','value':'0.00321','minimum':'0.005','token':'private'},
             {'key':'persistence','state':'FAIL','expected':'RISING'},
             {'key':'secret','state':'PASS','value':'private'}]}]}
    row=runtime_view(raw,now)['strategy_evaluations'][0]
    assert row['conditions'][0]['minimum']=='0.005'
    assert row['conditions'][0]['value']=='0.00321'
    assert row['conditions'][1]['expected']=='RISING'
    assert row['details']['persistent'] is False
    assert len(row['conditions'])==2
    assert row['next_check_at']==now.isoformat()
    assert 'private' not in json.dumps(row) and 'secret' not in json.dumps(row)


def test_stale_conditions_do_not_remain_green_in_observer_projection():
    from datetime import timedelta
    from dhan_cas_bot.dashboard.data import daily_monitor_view
    now=datetime(2026,10,8,4,15,tzinfo=timezone.utc)
    raw={'mode':'READ_ONLY','writes_to_broker':False,'observed_at':(now-timedelta(minutes=5)).isoformat(),
         'strategy_evaluations':[{'strategy':'GAP_FADE_DOUBLE','state':'NO_SIGNAL',
             'conditions':[{'key':'gap_size','state':'PASS','value':'.01','minimum':'.005'}]}]}
    assert daily_monitor_view(raw,now)['strategy_evaluations'][0]['conditions'][0]['state']=='UNKNOWN'


def test_missing_condition_number_cannot_be_displayed_as_passed():
    from dhan_cas_bot.dashboard.data import condition_projection
    row=condition_projection([{'key':'gap_size','state':'PASS','value':'NaN','minimum':'.005'}])[0]
    assert row['state']=='UNKNOWN' and row['value'] is None
