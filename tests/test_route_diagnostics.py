import json
from datetime import datetime,timezone,timedelta
from dhan_cas_bot.ledger import Ledger
from dhan_cas_bot.dashboard.data import ledger_view

NOW=datetime(2026,10,15,9,tzinfo=timezone.utc)


def test_probe_rejection_is_dated_and_categorised_without_private_broker_payload(tmp_path):
    path=tmp_path/'ledger.sqlite3';ledger=Ledger(path)
    ledger.db.execute('INSERT INTO intents VALUES(?,?,?,?,?,?,?,?,?,?,?)',
        ('i','c','route-probe','BUY','1',65,'.05','REJECTED','0','{}',NOW.isoformat()))
    ledger.db.execute('INSERT INTO orders VALUES(?,?,?,?,?)',
        ('o','i','PRIVATE','REJECTED',json.dumps({'omsErrorDescription':'PRIVATE order rejected: open interest below defined limits','token':'PRIVATE'})))
    view=ledger_view(path,now=NOW)
    from dhan_cas_bot.route import rejected_probe_contracts
    assert rejected_probe_contracts(ledger,NOW)=={'1'}
    assert view['available'] and view['route_check']['reason']=='LOW_OPEN_INTEREST'
    assert view['route_check']['state']=='REJECTED'
    assert 'PRIVATE' not in json.dumps(view)
    ledger.db.execute('UPDATE intents SET created_at=?',((NOW-timedelta(days=1)).isoformat(),))
    assert ledger_view(path,now=NOW)['route_check'] is None
    assert rejected_probe_contracts(ledger,NOW)==set()
    ledger.db.execute('UPDATE intents SET created_at=?',((NOW+timedelta(seconds=1)).isoformat(),))
    assert ledger_view(path,now=NOW)['route_check'] is None
    assert rejected_probe_contracts(ledger,NOW)==set()
    ledger.close()
