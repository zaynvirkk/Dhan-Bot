import json
from datetime import timedelta

from dhan_cas_bot.dashboard.collect import write_report
from dhan_cas_bot.dashboard.app import view_snapshot
from tests.test_dashboard_history import report as historical_report, NOW


def report(now=NOW):
    return {'schema':1,'collector_observed_at':now.isoformat(),**historical_report(now)}


def test_live_snapshot_does_not_copy_journal_into_every_quote_update(tmp_path):
    output=tmp_path/'snapshot.json'
    result=write_report(output,report(),embed_history=False)
    raw=json.loads(output.read_text())
    assert 'history' not in raw
    assert raw['history_external'] is True
    assert view_snapshot(output,NOW)['history']==result['history']
    assert 'history' not in view_snapshot(output,NOW,include_history=False)


def test_quote_only_update_preserves_journal_and_current_runtime(tmp_path):
    output=tmp_path/'snapshot.json'
    first=write_report(output,report(),embed_history=False)
    journal=tmp_path/'history.json';before=journal.read_bytes()
    second=write_report(output,report(NOW+timedelta(seconds=1)),embed_history=False,
                        history_cache=first['history'],update_history=False)
    assert journal.read_bytes()==before
    assert second['collector_observed_at']!=first['collector_observed_at']
    assert view_snapshot(output,NOW+timedelta(seconds=1),include_history=False)['runtime']['fresh']


def test_corrupt_external_journal_cannot_break_current_status_or_be_overwritten(tmp_path):
    output=tmp_path/'snapshot.json';journal=tmp_path/'history.json'
    journal.write_text('private invalid payload')
    write_report(output,report(),embed_history=False)
    assert journal.read_text()=='private invalid payload'
    current=view_snapshot(output,NOW,include_history=False)
    assert current['runtime']['fresh']
    assert 'history' not in current
    assert view_snapshot(output,NOW)['history']['status']=='UNAVAILABLE'
    assert 'private invalid payload' not in str(current)
