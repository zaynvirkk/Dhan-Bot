import json
from dhan_cas_bot.cli import selftest


def test_selftest_is_write_free():
    assert selftest() == {"software_verified": True, "writes": False, "live": False}
