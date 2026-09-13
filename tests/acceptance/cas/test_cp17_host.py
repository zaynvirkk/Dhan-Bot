from dhan_cas_bot.feeds import SocketProtocol

def test_cp17_positive(): assert SocketProtocol("host").on_connect()=="host:1"
def test_cp17_negative(): assert SocketProtocol("host").epoch.connected is False
def test_cp17_recovery():
    p=SocketProtocol("host"); p.on_connect(); p.on_disconnect(); p.on_connect(); assert p.epoch.id=="host:2"
