from dhan_cas_bot.auth import totp_code


def test_totp_rfc6238_vector():
    # RFC 6238 SHA-1 test secret, timestamp 59.
    assert totp_code("GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ", timestamp=59) == "287082"
