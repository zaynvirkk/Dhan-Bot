from datetime import datetime, timezone
import hashlib
import json
import sqlite3

from dhan_cas_bot.dashboard.data import ledger_view
from dhan_cas_bot.ledger import SCHEMA

NOW = datetime(2026, 10, 15, 6, 32, tzinfo=timezone.utc)
NAME = 'TREND_PULLBACK_FAST'


def test_recorded_checks_survive_reload_without_secrets_future_or_other_strategies(tmp_path):
    path = tmp_path / 'ledger.sqlite3'
    db = sqlite3.connect(path)
    db.executescript(SCHEMA)
    def add(at, state, *, name=NAME, received=None, suffix=''):
        payload = dict(strategy=name, evaluated_at=at, state=state,
                       reason='EXPANDED_RULE_NOT_MET' if state == 'NO_SIGNAL' else 'MISSING_COMPLETED_BAR',
                       details={'trend_30m': '.003', 'pullback_10m': '.001', 'token': 'PRIVATE'},
                       token='PRIVATE')
        db.execute('INSERT INTO observations VALUES (?,?,?,?)',
                   (f'strategy-evaluation:{name}:{at}:{state}{suffix}', 'STRATEGY_EVALUATION',
                    received or at, json.dumps(payload)))
    add('2026-10-15T11:55:00+05:30', 'NO_SIGNAL')
    add('2026-10-15T11:55:00+05:30', 'UNKNOWN', received='2026-10-15T06:25:05+00:00')
    add('2026-10-15T11:56:00+05:30', 'WAITING')
    add('2026-10-15T12:30:00+05:30', 'NO_SIGNAL')  # future decision
    add('2026-10-15T12:00:00+05:30', 'NO_SIGNAL', received='2026-10-15T08:00:00+00:00')
    add('2026-10-15T11:50:00+05:30', 'NO_SIGNAL', name='OPEN_DRIVE_FAST')
    add('2026-10-14T11:55:00+05:30', 'NO_SIGNAL')
    db.commit(); db.close()
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    out = ledger_view(path, strategies=[NAME, 'PRIVATE'], now=NOW)['decision_history']
    assert out['status'] == 'AVAILABLE' and out['date'] == '2026-10-15'
    assert len(out['strategies']) == 1
    row = out['strategies'][0]
    assert row['strategy'] == NAME and row['truncated'] is False
    assert [r['state'] for r in row['records']] == ['NO_SIGNAL', 'UNKNOWN']
    assert row['records'][0]['details'] == {'trend_30m': '0.003', 'pullback_10m': '0.001'}
    assert not any(x in json.dumps(out) for x in ('PRIVATE', '12:30', '2026-10-14', 'OPEN_DRIVE'))
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


def test_missing_ledger_does_not_claim_zero_checks(tmp_path):
    out = ledger_view(tmp_path/'missing', strategies=[NAME], now=NOW)
    assert out['decision_history']['status'] == 'UNAVAILABLE'


def test_recorded_checks_are_bounded_and_marked_partial(tmp_path):
    path = tmp_path/'ledger.sqlite3'; db = sqlite3.connect(path); db.executescript(SCHEMA)
    at = '2026-10-15T11:55:00+05:30'
    payload = json.dumps(dict(strategy=NAME, evaluated_at=at, state='NO_SIGNAL', reason='EXPANDED_RULE_NOT_MET'))
    db.executemany('INSERT INTO observations VALUES (?,?,?,?)',
                  [(f'strategy-evaluation:{NAME}:{at}:NO_SIGNAL:{i:04}', 'STRATEGY_EVALUATION', at, payload) for i in range(300)])
    db.commit(); db.close()
    out = ledger_view(path, strategies=[NAME], now=NOW)['decision_history']
    assert out['strategies'][0]['truncated'] is True
    assert len(out['strategies'][0]['records']) <= 256
