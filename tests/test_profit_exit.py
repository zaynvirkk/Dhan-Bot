from decimal import Decimal as D
import pytest


def test_net_profit_floor_ratchets_and_cannot_allow_the_normal_giveback():
    from dhan_cas_bot.profit_exit import observe
    costs=D('60');state=None
    state=observe(D('950'),costs,state,retain=D('.5'))
    assert D(state['floor'])==D('475') and not state['triggered']
    state=observe(D('650'),costs,state,retain=D('.5'))
    assert D(state['floor'])==D('475') and not state['triggered']
    state=observe(D('470'),costs,state,retain=D('.5'))
    assert state['triggered']
    assert observe(D('700'),costs,state,retain=D('.5'))['triggered']


def test_loss_and_tiny_after_cost_profit_do_not_manufacture_a_profit_floor():
    from dhan_cas_bot.profit_exit import observe
    state=observe(D('-2500'),D('60'),None,retain=D('.5'))
    assert state['floor'] is None and not state['triggered']
    state=observe(D('80'),D('60'),state,retain=D('.5'))
    assert state['floor'] is None


def test_a_gap_below_profit_floor_can_still_realise_a_loss():
    from dhan_cas_bot.profit_exit import observe
    state=observe(D('1000'),D('60'),None,retain=D('.5'))
    state=observe(D('-2000'),D('60'),state,retain=D('.5'))
    assert state['triggered'] and state['net_pnl']=='-2000'


@pytest.mark.parametrize('bad',[D('NaN'),D('Infinity'),D('0'),D('1'),D('-0.1')])
def test_invalid_retention_cannot_change_money_policy(bad):
    from dhan_cas_bot.profit_exit import observe
    with pytest.raises(ValueError):observe(D('1000'),D('60'),None,retain=bad)


def test_candle_replay_cannot_use_its_own_future_peak_to_sell_earlier():
    from research.profit_exits import protected_liquidate
    from tests.test_expiry_research import bar,order,fill,stamp,DAY
    entry=bar('14:46',o='20',h='20',l='20',c='20')
    jump=bar('14:47',o='20',h='43',l='12',c='42')
    after=bar('14:48',o='42',h='43',l='24',c='25')
    out=protected_liquidate(order(),fill(entry),[entry,jump,after],'NET50',stamp(DAY,'15:30'))
    assert out['reason']=='NET_PROFIT_FLOOR'
    assert out['at']==after.available.isoformat()
    assert out['price']==D('23.75')


def test_production_profit_protection_uses_fresh_bids_and_exits_without_a_clock_trigger(tmp_path):
    import asyncio
    from dataclasses import replace
    from datetime import timedelta
    from dhan_cas_bot.domain import Level
    from dhan_cas_bot.directional import DirectionalEngine
    from tests.test_directional_engine import setup
    async def run():
        engine,broker,ledger,clock,inputs=setup(tmp_path)
        engine.directional=DirectionalEngine(engine,engine.directional.enabled,profit_retain=D('.5'))
        engine.directional.update(inputs)
        assert await engine.cycle()
        clock[0]+=timedelta(seconds=1)
        book=engine.books['101']
        def quote(bid,stamp=None,quantity=650):
            engine.on_book(replace(book,bids=(Level(D(bid),quantity),),asks=(Level(D(bid)+D('.2'),650),),received_ns=stamp or int(clock[0].timestamp()*1e9)))
        quote('100',int((clock[0]-timedelta(seconds=4)).timestamp()*1e9))
        assert not await engine.cycle()
        key='profit-exit:'+engine.active['lifecycle_id']
        assert ledger.metadata(key) is None,'Stale high quote cannot ratchet the floor'
        quote('100',quantity=1)
        assert not await engine.cycle()
        assert ledger.metadata(key) is None,'One unit cannot value an entire lot'
        quote('15')
        assert not await engine.cycle()
        saved=ledger.metadata(key)
        assert D(saved['floor'])>0
        quote('12')
        assert await engine.cycle()
        assert broker.requests[-1]['transactionType']=='SELL'
        assert ledger.metadata('directional-exit:'+engine.active['lifecycle_id'])['reason']=='NET_PROFIT_FLOOR'
        assert len(broker.requests)==2
    asyncio.run(run())


@pytest.mark.parametrize('fields',[{'profit_exit_retain':'.5'},
    {'profit_exit_policy':'UNKNOWN','profit_exit_retain':'.5'},
    {'profit_exit_policy':'NET_PROFIT_RATCHET_V1','profit_exit_retain':'1'},
    {'profit_exit_policy':'NET_PROFIT_RATCHET_V1','profit_exit_retain':'NaN'}])
def test_configuration_cannot_silently_enable_an_invalid_exit_policy(tmp_path,fields):
    import json
    from dhan_cas_bot.config import load_config
    from dhan_cas_bot.domain import ContractError
    path=tmp_path/'config.toml'
    path.write_text('state_dir="state"\nlive_order_authority=false\naccount_id="fixture"\ndhan_api_base="https://example.invalid"\nexpected_egress_ip="127.0.0.1"\n'+''.join(k+'='+json.dumps(v)+'\n' for k,v in fields.items()))
    with pytest.raises(ContractError):load_config(path)
