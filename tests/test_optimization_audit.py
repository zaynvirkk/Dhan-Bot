"""Exact audit counterexamples; local ledgers and synthetic quotes only."""
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal as D
import json
from types import SimpleNamespace

import pytest

from dhan_cas_bot.seconds_engine import SecondsEngine
from dhan_cas_bot.seconds_strategies import NAMES
from dhan_cas_bot.ledger import Ledger
from tests.test_seconds_strategies import seeded_tape, NOW
from tests.test_seconds_oms import prepared


def test_five_seconds_observations_commit_once_and_retain_each_receipt(tmp_path):
    tape,books,cal=seeded_tape();ledger=Ledger(tmp_path/'audit.sqlite3')
    engine=SimpleNamespace(now=lambda:NOW,books=books,runtime=SimpleNamespace(ledger=ledger))
    seconds=SecondsEngine(SimpleNamespace(engine=engine,inputs=SimpleNamespace(calendar=cal),enabled=NAMES))
    seconds.tape=tape;trace=[];ledger.db.set_trace_callback(trace.append)
    try:
        seconds.refresh(force=True)
        records=list(ledger.db.execute("SELECT payload FROM observations WHERE kind='STRATEGY_EVALUATION'"))
        assert {json.loads(r[0])['strategy'] for r in records}==set(NAMES)
        assert sum(q=='BEGIN IMMEDIATE' for q in trace)==1
        assert sum(q=='COMMIT' for q in trace)==1
        assert ledger.db.execute('SELECT COUNT(*) FROM intents').fetchone()[0]==0
    finally:ledger.close()


@pytest.mark.parametrize('stage',['candidate','dispatch'])
def test_worse_same_episode_projection_cannot_reuse_an_old_target(tmp_path,monkeypatch,stage):
    engine,broker,ledger,clock=prepared(tmp_path,monkeypatch)
    seconds=engine.directional.seconds;sample=seconds.evaluations[NAMES[0]]
    try:
        seconds.evaluations[sample.strategy]=replace(sample,details={**sample.details,'target_price':'12'})
        if stage=='dispatch':assert seconds.valid(sample) is False
        else:
            from dhan_cas_bot.risk import Allocation
            assert seconds.candidate(sample,Allocation.start(D(7805),D(7805))) is None
            assert engine.directional.last_reason=='SECONDS_SIGNAL_CHANGED'
        assert broker.requests==[] and not ledger.pending_intents()
    finally:ledger.close()


def test_history_evaluation_timestamps_alone_are_not_state_changes():
    from dhan_cas_bot.dashboard.collect import history_signature
    from dhan_cas_bot.dashboard.history import advance_history
    from tests.test_dashboard_history import report
    def sample(at,state='NO_SIGNAL',reason='SECONDS_RULE_NOT_MET'):
        r=report(at,'ARMED_WAITING_SIGNAL')
        r['runtime']['strategy_evaluations']=[{'strategy':NAMES[0],'family':NAMES[0],
            'state':state,'reason':reason,'evaluated_at':at.isoformat(),'enabled':True}]
        return r
    first=sample(NOW);later=sample(NOW+timedelta(seconds=6))
    assert history_signature(first)==history_signature(later)
    history=advance_history(None,first,NOW)
    assert advance_history(history,later,NOW+timedelta(seconds=6))==history
    # Real changes and periodic observations must still survive.
    changed=sample(NOW+timedelta(seconds=6),'UNKNOWN','FUTURES_FEED_UNAVAILABLE')
    assert history_signature(first)!=history_signature(changed)
    assert len(advance_history(history,changed,NOW+timedelta(seconds=6))['events'])==2
    periodic=sample(NOW+timedelta(seconds=60))
    assert len(advance_history(history,periodic,NOW+timedelta(seconds=60))['events'])==2
    signal=sample(NOW+timedelta(seconds=6),'SIGNAL','SECONDS_SETUP_DETECTED')
    another=sample(NOW+timedelta(seconds=12),'SIGNAL','SECONDS_SETUP_DETECTED')
    assert history_signature(signal)!=history_signature(another)


def test_unchanged_or_better_projection_keeps_original_conservative_target(tmp_path,monkeypatch):
    engine,broker,ledger,clock=prepared(tmp_path,monkeypatch)
    seconds=engine.directional.seconds;signal=seconds.evaluations[NAMES[0]]
    try:
        assert seconds.valid(signal)
        seconds.evaluations[signal.strategy]=replace(signal,details={**signal.details,'target_price':'16'})
        assert seconds.valid(signal)
        from dhan_cas_bot.risk import Allocation
        assert seconds.candidate(signal,Allocation.start(D(7805),D(7805))) is not None
        assert signal.details['target_price']=='15'
        seconds.evaluations[signal.strategy]=replace(signal,details={**signal.details,'target_price':'NaN'})
        assert not seconds.valid(signal)
        assert broker.requests==[]
    finally:ledger.close()


def test_failed_observation_batch_cannot_mark_partial_history_complete(tmp_path,monkeypatch):
    tape,books,cal=seeded_tape();ledger=Ledger(tmp_path/'batch-failure.sqlite3')
    engine=SimpleNamespace(now=lambda:NOW,books=books,runtime=SimpleNamespace(ledger=ledger))
    seconds=SecondsEngine(SimpleNamespace(engine=engine,inputs=SimpleNamespace(calendar=cal),enabled=NAMES))
    seconds.tape=tape
    def fail(*args):raise OSError('fixture disk failure')
    monkeypatch.setattr(ledger,'observe_batch',fail)
    try:
        with pytest.raises(OSError):seconds.refresh(force=True)
        assert seconds.last_recorded is None
        assert ledger.db.execute('SELECT COUNT(*) FROM observations').fetchone()[0]==0
        assert ledger.db.execute('SELECT COUNT(*) FROM intents').fetchone()[0]==0
    finally:ledger.close()
