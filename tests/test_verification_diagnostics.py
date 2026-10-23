import json
from types import SimpleNamespace

import pytest


def test_failed_release_names_the_case_without_echoing_child_output(tmp_path,monkeypatch):
    from dhan_cas_bot import release
    def failed(command,**kwargs):
        from pathlib import Path
        target=Path(next(x.split('=',1)[1] for x in command if x.startswith('--junitxml=')))
        target.write_text('<testsuites><testsuite><testcase classname="tests.test_fixture" name="test_guard[TOPSECRET]"><failure>PRIVATE</failure></testcase></testsuite></testsuites>')
        return SimpleNamespace(returncode=1,stdout='PRIVATE',stderr='TOPSECRET')
    monkeypatch.setattr(release.subprocess,'run',failed)
    with pytest.raises(release.ContractError) as error:release.run_verification(tmp_path,tmp_path/'state')
    receipt=error.value.verification_failure
    assert receipt['stage']=='pytest' and receipt['failed_cases']==['tests.test_fixture::test_guard']
    assert 'TOPSECRET' not in json.dumps(receipt) and 'PRIVATE' not in json.dumps(receipt)
    assert not (tmp_path/'state/software_verified.json').exists()
