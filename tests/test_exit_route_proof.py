import json
from datetime import datetime,timedelta,timezone
import pytest
from dhan_cas_bot.ledger import Ledger


@pytest.mark.parametrize('case',['old_epoch','old_submission','foreign_account','buy','no_fill','unresolved','wrong_security','wrong_quantity'])
def test_only_a_current_confirmed_managed_sell_can_establish_route(tmp_path,case):
    from dhan_cas_bot.route import managed_exit_route
    now=datetime.now(timezone.utc);ledger=Ledger(tmp_path/'ledger')
    submitted=now-timedelta(seconds=1) if case=='old_submission' else now+timedelta(seconds=1)
    side='BUY' if case=='buy' else 'SELL';account='foreign' if case=='foreign_account' else 'fixture'
    ledger.db.execute('INSERT INTO lifecycles VALUES(?,?,?,?,?,?)',('l','s','123','9411','OPEN','{}'))
    ledger.db.execute('INSERT INTO intents VALUES(?,?,?,?,?,?,?,?,?,?,?)',('i','c','l',side,'123',65,'10','SENT' if case=='unresolved' else 'FILLED','0','{}',submitted.isoformat()))
    ledger.db.execute('INSERT INTO orders VALUES(?,?,?,?,?)',('o','i',account,'TRADED','{}'))
    if case!='no_fill':
        ledger.db.execute('INSERT INTO fills VALUES(?,?,?,?,?,?,?,?,?)',('t','o','i','456' if case=='wrong_security' else '123',130 if case=='wrong_quantity' else 65,'10','20',submitted.isoformat(),'{}'))
    echoed={'o':('old' if case=='old_epoch' else 'current','TRADED')}
    assert managed_exit_route(ledger,'fixture','current',now,echoed) is None
    ledger.close()


def test_real_sell_fill_after_socket_connection_can_qualify_without_probe_debit(tmp_path):
    from dhan_cas_bot.route import managed_exit_route
    now=datetime.now(timezone.utc);ledger=Ledger(tmp_path/'ledger');submitted=now+timedelta(seconds=1)
    ledger.db.execute('INSERT INTO lifecycles VALUES(?,?,?,?,?,?)',('l','s','123','9411','OPEN','{}'))
    ledger.db.execute('INSERT INTO intents VALUES(?,?,?,?,?,?,?,?,?,?,?)',('i','c','l','SELL','123',65,'10','FILLED','0','{}',submitted.isoformat()))
    ledger.db.execute('INSERT INTO orders VALUES(?,?,?,?,?)',('o','i','fixture','TRADED','{}'))
    ledger.db.execute('INSERT INTO fills VALUES(?,?,?,?,?,?,?,?,?)',('t','o','i','123',65,'10','20',submitted.isoformat(),'{}'))
    assert managed_exit_route(ledger,'fixture','current',now,{'o':('current','TRADED')})=='o'
    assert ledger.counter('probe.spent')==0
    ledger.close()
