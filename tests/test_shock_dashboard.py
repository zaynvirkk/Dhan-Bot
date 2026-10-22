import json
from dataclasses import asdict
from dhan_cas_bot.domain import json_safe
from dhan_cas_bot.dashboard.data import strategy_projection, last_signal_views, active_trade_views
from tests.test_volatility_shock import signal
from tests.test_shock_engine import setup
from dhan_cas_bot.volatility_shock import SHOCK


def test_shock_fields_are_visible_without_private_payloads():
    raw=json_safe(asdict(signal()));raw['details']['token']='PRIVATE'
    raw['shock_candidates']=[{'security_id':'123','reason':'SHOCK_SPREAD_TOO_WIDE',
        'budget':'7772.25','token':'PRIVATE','raw_payload':'PRIVATE'}]
    row=strategy_projection([raw])[0]
    assert row['exit_policy']=='SHOCK_EXIT_V1' and len(row['conditions'])==6
    assert row['details']['spot_5m'] and row['bar_at'] and row['source_received_at']
    assert row['shock_candidates'][0]['reason']=='SHOCK_SPREAD_TOO_WIDE'
    assert 'PRIVATE' not in json.dumps(row)


def test_episode_keyed_signal_is_in_history(tmp_path):
    e,b,l,c,i=setup(tmp_path)
    rows=last_signal_views(l.db)
    assert rows and rows[0]['strategy']==SHOCK


def test_shock_has_actual_fill_risk_projection_and_no_generic_double(tmp_path):
    import asyncio
    async def run():
        e,b,l,c,i=setup(tmp_path)
        assert await e.cycle();await e.cycle()
        row=active_trade_views(l.db)[0]
        assert row['strategy']==SHOCK and row['shock']['entry_cash']
        assert not row['target_known'] and row['net_protection'] is None
    asyncio.run(run())
