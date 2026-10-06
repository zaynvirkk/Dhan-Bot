from datetime import datetime, timezone
import json

from dhan_cas_bot.dashboard.data import runtime_view


def test_strategy_rows_are_allowlisted_not_raw_provider_errors():
    now=datetime(2026,10,6,4,0,tzinfo=timezone.utc)
    raw={"observed_at":now.isoformat(),"strategies":["GAP_FADE_DOUBLE","secret"],
         "strategy_evaluations":[{"strategy":"GAP_FADE_DOUBLE","state":"SIGNAL","enabled":True,
            "reason":"GAP_FADE_CONFIRMED","evaluated_at":now.isoformat(),"side":"CE",
            "details":{"gap":"-.008", "access_token":"sensitive"},"password":"private"},
            {"strategy":"NIFTY_SELLOFF_REBOUND_1510","state":"UNKNOWN","reason":"provider token secret"}]}
    result=runtime_view(raw,now)
    assert result["strategies"]==["GAP_FADE_DOUBLE"]
    assert result["strategy_evaluations"][0]["details"]["gap"]=="-0.008"
    assert "sensitive" not in json.dumps(result) and "private" not in json.dumps(result) and "secret" not in json.dumps(result)
    assert result["strategy_evaluations"][1]["reason"]=="UNKNOWN"
