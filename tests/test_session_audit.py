import json
from datetime import datetime,timedelta,timezone
from dhan_cas_bot.dashboard.session_audit import append_session_audit


NOW=datetime(2026,10,15,4,tzinfo=timezone.utc)


def report(now):
    return {'runtime':{'observed_at':now.isoformat(),'fresh':True,'state':'ARMED_WAITING_SIGNAL',
            'authority':'ENABLED','broker_route_verified':False,'account_snapshot_fresh':True,
            'funded_strategies':['CAS_LAG_V1'],'feed_health':{'market':{'connected':True,'reconnects':0,
                'last_error':'PRIVATE','transport_events':[{'kind':'ERROR','error_type':'ConnectionClosedError',
                'at':now.isoformat(),'private':'PRIVATE'}]}}},'token':'PRIVATE'}


def test_full_session_audit_survives_ring_eviction_restart_and_private_fields(tmp_path):
    output=tmp_path/'snapshot.json'
    for i in range(500):
        at=NOW+timedelta(minutes=i)
        assert append_session_audit(output,report(at),at)=='AVAILABLE'
    files=list(tmp_path.glob('session-audit-*.jsonl'));assert len(files)==1
    lines=files[0].read_text().splitlines()
    assert len(lines)==500
    assert json.loads(lines[0])['at']==NOW.isoformat()
    assert 'PRIVATE' not in files[0].read_text()
    assert append_session_audit(output,report(at),at)=='AVAILABLE'
    assert len(files[0].read_text().splitlines())==500


def test_audit_cap_or_broken_tail_is_visible_and_preserves_existing_bytes(tmp_path):
    path=tmp_path/'session-audit-2026-10-15.jsonl';path.write_text('broken evidence\n')
    assert append_session_audit(tmp_path/'snapshot.json',report(NOW),NOW)=='UNAVAILABLE'
    assert path.read_text()=='broken evidence\n'
    path.unlink()
    assert append_session_audit(tmp_path/'snapshot.json',report(NOW),NOW,max_bytes=1)=='CAP_REACHED'
    assert not path.exists()
