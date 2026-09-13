from dhan_cas_bot.runtime import RuntimeStatus

def test_cp14_positive(): assert RuntimeStatus().state=="DISARMED"
def test_cp14_negative(): assert RuntimeStatus().auto_live_armed is False
def test_cp14_recovery(): assert RuntimeStatus().profitability_status=="UNKNOWN"
