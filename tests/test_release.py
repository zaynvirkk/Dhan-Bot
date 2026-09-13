from dhan_cas_bot.release import current_verification, write_verification


def test_verification_marker_is_digest_bound(tmp_path):
    root = tmp_path / "root"; (root / "dhan_cas_bot").mkdir(parents=True)
    (root / "dhan_cas_bot" / "x.py").write_text("x=1\n")
    (root / "pyproject.toml").write_text("x\n"); (root / "requirements.lock").write_text("x\n"); (root / "MANIFEST.json").write_text("{}\n")
    state = tmp_path / "state"
    assert not current_verification(root, state)
    write_verification(root, state, case_count=60)
    assert current_verification(root, state)
    (root / "dhan_cas_bot" / "x.py").write_text("x=2\n")
    assert not current_verification(root, state)
