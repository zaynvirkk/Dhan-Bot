from dataclasses import replace
from datetime import datetime,timezone,timedelta
from decimal import Decimal as D
from types import SimpleNamespace
import json
import pytest
from dhan_cas_bot.domain import Level
from dhan_cas_bot.ledger import Ledger

from tests.test_feed_route_settlement import book

NOW=datetime(2026,10,15,9,tzinfo=timezone.utc)


def liquid(sid='1',oi=650000,volume=65000):
    b=book()
    return replace(b,instrument=replace(b.instrument,security_id=sid,expiry=NOW.date()),
                   asks=(Level(D('9.05'),195),),
                   received_ns=int(NOW.timestamp()*1e9),
                   statistics=SimpleNamespace(open_interest=oi,volume=volume))


def test_probe_selection_rejects_low_unknown_stale_foreign_and_previously_rejected_contracts():
    from dhan_cas_bot.route import probe_candidates
    good=liquid()
    for bad in [liquid(oi=0),liquid(oi=65),liquid(volume=0),replace(good,statistics=None),
                replace(good,received_ns=good.received_ns-3_000_000_000),
                replace(good,received_ns=good.received_ns+1),replace(good,epoch='old'),
                replace(good,instrument=replace(good.instrument,expiry=NOW.date()-timedelta(days=1))),
                replace(good,asks=())]:
        assert probe_candidates([bad],NOW,'dhan:1')==[]
    assert probe_candidates([good],NOW,'dhan:1',rejected={'1'})==[]
    assert probe_candidates([good],NOW,'dhan:1')==[good]


def test_probe_selection_prefers_observed_open_interest_over_security_id_and_checks_cash_caps():
    from dhan_cas_bot.route import probe_candidates
    lower=liquid('1',65000);higher=liquid('999',650000)
    assert probe_candidates([lower,higher],NOW,'dhan:1')[0]==higher
    assert probe_candidates([higher],NOW,'dhan:1',remaining_debit=D('1'))==[]


@pytest.mark.parametrize('case',['resolved','unresolved','wrong_epoch','foreign','filled','old_day','future','newer_unknown'])
def test_only_a_current_reconciled_zero_fill_rejection_allows_bounded_retry(tmp_path,case):
    from dhan_cas_bot.route import rejected_probe_resolved
    ledger=Ledger(tmp_path/'ledger')
    stamp=NOW-timedelta(days=1) if case=='old_day' else NOW+timedelta(seconds=1) if case=='future' else NOW
    ledger.db.execute('INSERT INTO intents VALUES(?,?,?,?,?,?,?,?,?,?,?)',
        ('i','c','route-probe','BUY','1',65,'.05','SENT' if case=='unresolved' else 'REJECTED','0','{}',stamp.isoformat()))
    ledger.db.execute('INSERT INTO orders VALUES(?,?,?,?,?)',
        ('o','i','OTHER' if case=='foreign' else 'TEST','REJECTED','{}'))
    ledger.put_metadata('route_probe',{'epoch':'other' if case=='wrong_epoch' else 'epoch','intent_id':'i'})
    if case=='filled':
        ledger.db.execute('INSERT INTO fills VALUES(?,?,?,?,?,?,?,?,?)',('t','o','i','1',1,'.05','0',NOW.isoformat(),'{}'))
    if case=='newer_unknown':
        ledger.db.execute('INSERT INTO intents VALUES(?,?,?,?,?,?,?,?,?,?,?)',
            ('new','newc','route-probe','BUY','2',65,'.05','SEND_UNKNOWN','42','{}',NOW.isoformat()))
        ledger.put_metadata('route_probe',{'epoch':'epoch','intent_id':'new'})
    assert rejected_probe_resolved(ledger,'TEST','epoch',NOW) is (case=='resolved')
    assert ledger.counter('probe.attempts:'+NOW.date().isoformat())==0
    ledger.close()
