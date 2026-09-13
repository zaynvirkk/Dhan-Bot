from dhan_cas_bot.feeds import chunked, SocketProtocol

def test_cp03_positive(): assert len(chunked([str(i) for i in range(101)]))==2
def test_cp03_negative(): assert SocketProtocol("capture").epoch.connected is False
def test_cp03_recovery():
    p=SocketProtocol("capture"); p.on_connect(); p.on_disconnect(); assert p.epoch.connected is False
