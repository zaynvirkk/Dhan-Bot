import io
import json
from urllib.error import HTTPError

import pytest


def test_deploy_check_recovers_socket_timeouts_before_and_after_authentication():
    from dhan_cas_bot.dashboard.deploy import verify_local_dashboard
    calls=[];waits=[]
    report={'available':True,'writes_to_broker':False,'account_read_ok':True,'collector':{'fresh':True}}
    def open_url(request,timeout):
        calls.append(request)
        if len(calls) in (1,3):raise TimeoutError()
        if len(calls)==2:raise HTTPError('http://localhost',401,'Unauthorized',{},None)
        return io.BytesIO(json.dumps(report).encode())
    assert verify_local_dashboard({'Authorization':'Basic fixture'},open_url=open_url,pause=waits.append)==report
    assert len(calls)==4 and len(waits)==2


def test_deploy_check_never_accepts_an_unprotected_dashboard():
    from dhan_cas_bot.dashboard.deploy import verify_local_dashboard
    def open_url(*args,**kwargs):return io.BytesIO(b'{}')
    with pytest.raises(RuntimeError,match='authentication'):
        verify_local_dashboard({},open_url=open_url,pause=lambda _:None)


def test_deploy_check_timeout_retries_are_bounded():
    from dhan_cas_bot.dashboard.deploy import verify_local_dashboard
    calls=[]
    def open_url(*args,**kwargs):calls.append(1);raise TimeoutError()
    with pytest.raises(RuntimeError,match='did not become ready'):
        verify_local_dashboard({},open_url=open_url,pause=lambda _:None,attempts=3)
    assert len(calls)==3
