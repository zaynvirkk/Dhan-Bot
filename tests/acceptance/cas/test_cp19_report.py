from dhan_cas_bot.runtime import RuntimeStatus

def test_cp19_positive():
    keys={"software_verified","current_account_funded","broker_route_verified","official_cas_signal_seen","final_value_source_verified","auto_live_armed","profitability_status"}; assert keys <= RuntimeStatus().as_dict().keys()
def test_cp19_negative(): assert RuntimeStatus().profitability_status=="UNKNOWN"
def test_cp19_recovery(): assert RuntimeStatus().as_dict()["state"]=="DISARMED"
