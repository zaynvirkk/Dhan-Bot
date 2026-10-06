"""A monitoring journal cannot infer missing sessions or convert outages to no trades."""
from datetime import datetime, timedelta, timezone
import json

from dhan_cas_bot.dashboard.history import advance_history
from dhan_cas_bot.dashboard import collect as collector
from dhan_cas_bot.dashboard.data import runtime_view

NOW = datetime(2026, 10, 6, 4, 30, tzinfo=timezone.utc)


def report(now=NOW, state='NO_TRADE_DAY'):
    return {'runtime': runtime_view({'observed_at':now.isoformat(), 'state':state,
        'writes':True, 'auto_live_armed':True, 'monitoring_mode':'IDLE',
        'books_observed':0, 'feed_health':{'signal':{'connected':True}}}, now)}


def test_history_starts_now_never_invents_yesterday_or_trade_outcomes():
    value=advance_history(None, report(), NOW)
    assert value['started_at']==NOW.isoformat()
    assert [d['date'] for d in value['days']]==['2026-10-06']
    assert 'trades' not in json.dumps(value) and len(value['events'])==1


def test_restart_duplicates_are_idempotent_and_missing_runtime_is_unknown():
    value=advance_history(None, report(), NOW)
    assert advance_history(json.loads(json.dumps(value)), report(), NOW)==value
    later=NOW+timedelta(minutes=10)
    value=advance_history(value, report(), later)
    assert value['events'][-1]['state']=='UNKNOWN'
    assert value['events'][-1]['source_current'] is False
    assert value['days'][0]['gaps']==1 and value['days'][0]['unknown_samples']==1


def test_current_state_change_records_without_waiting_minute_and_unknown_keys_stay_private():
    value=advance_history(None, report(), NOW)
    later=NOW+timedelta(seconds=6)
    data=report(later,'RECOVERING');data['token']='secret';data['runtime']['reason']='secret';data['runtime']['observation']={'iep':'NaN','ltp':'24000.25','raw':'secret'}
    result=advance_history(value,data,later)
    assert len(result['events'])==2 and result['events'][-1]['state']=='RECOVERING'
    assert result['events'][-1]['iep'] is None and result['events'][-1]['ltp']=='24000.25'
    assert 'secret' not in json.dumps(result)


def test_history_uses_ist_day_and_bounds_retention():
    start=datetime(2026,9,1,18,29,tzinfo=timezone.utc);value=None
    for n in range(35):
        stamp=start+timedelta(days=n)
        value=advance_history(value,report(stamp),stamp)
    assert len(value['days'])==31 and len(value['events'])<=240
    stamp=stamp+timedelta(minutes=2)
    value=advance_history(value,report(stamp),stamp)
    assert value['days'][-1]['date']==stamp.astimezone(__import__('zoneinfo').ZoneInfo('Asia/Kolkata')).date().isoformat()


def test_collector_history_failure_is_visible_and_preserves_broken_evidence(tmp_path):
    output=tmp_path/'snapshot.json';history=tmp_path/'history.json'
    history.write_text('BROKEN private evidence')
    result=collector.write_report(output,report())
    assert result['history']['status']=='UNAVAILABLE'
    assert history.read_text()=='BROKEN private evidence'
    assert 'private evidence' not in output.read_text()


def test_history_roundtrip_survives_collector_restart(tmp_path):
    output=tmp_path/'snapshot.json'
    one=collector.write_report(output,report())
    assert one['history']['status']=='AVAILABLE'
    assert (tmp_path/'history.json').is_file()
    two=collector.write_report(output,report())
    assert two['history']['started_at']==one['history']['started_at']


def test_detail_limit_preserves_daily_sample_count():
    value=None
    for n in range(250):
        stamp=NOW+timedelta(minutes=n)
        value=advance_history(value,report(stamp),stamp)
    assert len(value['events'])==240
    assert value['days'][0]['samples']==250
    assert value['days'][0]['first_at']==NOW.isoformat()
