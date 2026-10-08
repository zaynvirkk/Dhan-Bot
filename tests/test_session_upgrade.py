"""Operator upgrade must preserve funds, authority, and existing private state."""
import importlib.util
from pathlib import Path
import tomllib

import pytest

spec=importlib.util.spec_from_file_location('session_upgrade',Path('ops/upgrade-session-strategies.py'))
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_strategy_patch_changes_only_strategy_list_and_preserves_tables():
    source='live_order_authority = true\naccount_id = "private"\n[other]\nstrategies = ["keep"]\n'
    updated=module.amend_strategies(source)
    before,after=tomllib.loads(source),tomllib.loads(updated)
    assert after.pop('strategies')==list(module.STRATEGIES)
    assert before==after
    assert module.amend_strategies(updated)==updated


def test_ambiguous_strategy_assignment_fails_without_changes():
    with pytest.raises(ValueError):
        module.amend_strategies('strategies = [\n"CAS_LAG_V1"\n]\n')


def test_upgrade_requires_explicit_apply_and_does_not_first_activate():
    args=module.arguments([])
    assert not args.apply
    assert module.arguments(['--apply']).apply
    with pytest.raises(ValueError): module.require_existing_authority({'live_order_authority':False},False)
    with pytest.raises(ValueError): module.require_existing_authority({'live_order_authority':True},False)
    module.require_existing_authority({'live_order_authority':True},True)


def test_upgrade_never_overwrites_mandate_or_ledger():
    source=Path('ops/upgrade-session-strategies.py').read_text()
    assert 'activate-live.py' not in source
    assert 'put_mandate' not in source and 'sqlite3' not in source
    assert 'allocated_capital=' not in source


def test_atomic_replacement_preserves_original_on_failed_install(tmp_path,monkeypatch):
    target=tmp_path/'production.toml'
    target.write_bytes(b'private original')
    def fail(*args): raise OSError('fixture')
    monkeypatch.setattr(module.os,'replace',fail)
    monkeypatch.setattr(module.os,'chown',lambda *args:None)
    with pytest.raises(OSError): module.atomic(target,b'new',0o640,(0,0))
    assert target.read_bytes()==b'private original'
    assert list(tmp_path.iterdir())==[target]


def test_failed_preflight_rollback_cannot_overwrite_concurrent_config(tmp_path):
    path=tmp_path/'config'
    path.write_bytes(b'operator update')
    module.restore_files([(path,b'stale config',0o600,(0,0))],changed=False)
    assert path.read_bytes()==b'operator update'
