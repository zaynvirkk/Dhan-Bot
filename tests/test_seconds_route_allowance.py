from datetime import datetime,timezone
from decimal import Decimal as D
import pytest
from dhan_cas_bot.ledger import Ledger
from dhan_cas_bot.route import extra_attempts, grant_extra_attempt

NOW=datetime(2026,10,15,8,tzinfo=timezone.utc)

def test_operator_extra_attempt_is_date_bound_idempotent_and_never_resets_usage(tmp_path):
    ledger=Ledger(tmp_path/'ledger.sqlite3');ledger.set_counter('probe.attempts:2026-10-15',2)
    assert extra_attempts(ledger,'2026-10-15',2,NOW)==0
    grant_extra_attempt(ledger,'2026-10-15',2,NOW)
    grant_extra_attempt(ledger,'2026-10-15',2,NOW)
    assert extra_attempts(ledger,'2026-10-15',2,NOW)==1
    assert ledger.counter('probe.attempts:2026-10-15')==D(2)
    assert extra_attempts(ledger,'2026-10-16',2,NOW)==0
    assert extra_attempts(ledger,'2026-10-15',1,NOW)==0
    with pytest.raises(ValueError):grant_extra_attempt(ledger,'2026-10-16',2,NOW)
    assert ledger.counter('probe.attempts:2026-10-15')==D(2)


def test_malformed_extra_permission_cannot_raise_attempt_limit(tmp_path):
    ledger=Ledger(tmp_path/'ledger.sqlite3')
    for value in ({'extra':999},{'extra':True},{'extra':1,'normal_limit':2,'operator_requested':True,'recorded_at':'2099-01-01T00:00:00Z'}):
        ledger.put_metadata('probe.extra_attempt:2026-10-15',value)
        assert extra_attempts(ledger,'2026-10-15',2,NOW)==0
