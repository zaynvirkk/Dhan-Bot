from dhan_cas_bot.cli import selftest

def test_cp16_positive(): assert selftest()=={"software_verified":True,"writes":False,"live":False}
def test_cp16_negative(): assert selftest()["live"] is False
def test_cp16_recovery(): assert selftest()["writes"] is False
