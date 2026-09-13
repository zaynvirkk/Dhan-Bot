import json
from types import SimpleNamespace

import pytest

from dhan_cas_bot import session_refresh
from dhan_cas_bot.domain import ContractError


@pytest.mark.parametrize("config_live,mandate_live,interlock,fixed_token", [
    (True, False, "1", ""), (False, True, "1", ""),
    (False, False, "0", ""), (False, False, "1", "fixed-token"),
])
def test_session_refresh_cannot_restart_live_or_unrefreshable_engine(monkeypatch, config_live, mandate_live, interlock, fixed_token):
    calls = []
    monkeypatch.setattr(session_refresh, "load_config", lambda _: {"live_order_authority": config_live, "state_dir": "unused"})
    monkeypatch.setattr(session_refresh, "load_mandate", lambda _: SimpleNamespace(live_order_authority=mandate_live))
    monkeypatch.setenv("DHAN_PIN", "test-pin")
    monkeypatch.setenv("DHAN_TOTP_SECRET", "test-seed")
    monkeypatch.setenv("DHAN_ACCESS_TOKEN", fixed_token)
    def run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(stdout=f"DHAN_BROKER_READ_ONLY={interlock}")
    monkeypatch.setattr(session_refresh.subprocess, "run", run)
    with pytest.raises(ContractError):
        session_refresh.refresh_read_only("unused")
    assert not any("restart" in call for call in calls)


def test_session_refresh_restarts_only_configured_readonly_daemon(monkeypatch, tmp_path):
    from dhan_cas_bot.config import write_examples
    write_examples(tmp_path)
    config = tmp_path / "production.example.toml"
    config.write_text(config.read_text().replace('state_dir = "state"', f'state_dir = {json.dumps(str(tmp_path))}'))
    (tmp_path / "mandate.json").write_text((tmp_path / "mandate.example.json").read_text())
    monkeypatch.setenv("DHAN_PIN", "test-pin")
    monkeypatch.setenv("DHAN_TOTP_SECRET", "test-seed")
    monkeypatch.delenv("DHAN_ACCESS_TOKEN", raising=False)
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(stdout="DHAN_BROKER_READ_ONLY=1 PYTHONUNBUFFERED=1")
    monkeypatch.setattr(session_refresh.subprocess, "run", run)
    session_refresh.refresh_read_only(str(config))
    assert calls[-1] == ["systemctl", "restart", "dhan-cas.service"]
