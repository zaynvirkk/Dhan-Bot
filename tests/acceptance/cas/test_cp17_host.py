from dhan_cas_bot.feeds import SocketProtocol


def test_cp17_positive():
    first, other = SocketProtocol("host"), SocketProtocol("host")
    assert first.on_connect().startswith("host:")
    assert first.epoch.number == 1
    assert first.epoch.id != other.on_connect()  # a process restart cannot reuse proof


def test_cp17_negative():
    p = SocketProtocol("host")
    assert not p.accept("unconnected")


def test_cp17_recovery():
    p = SocketProtocol("host")
    old = p.on_connect()
    assert p.accept("event")
    p.on_disconnect()
    assert not p.epoch.connected and not p.epoch.seen
    assert p.on_connect() != old and p.epoch.number == 2
    assert p.accept("event")
