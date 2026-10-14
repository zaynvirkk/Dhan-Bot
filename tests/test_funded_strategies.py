import asyncio
from dataclasses import replace
import pytest
from dhan_cas_bot.config import funded_strategies
from dhan_cas_bot.funded_activation import amend_funded
from tests.test_directional_engine import setup


def test_funded_allowlist_cannot_expand_scanned_strategies():
    with pytest.raises(ValueError):
        funded_strategies({'funded_strategies':['CAS_LAG_V1']},('OPEN_DRIVE_FAST',))


@pytest.mark.parametrize('value',[None,True,'CAS_LAG_V1',['CAS_LAG_V1','CAS_LAG_V1'],['MADE_UP']])
def test_invalid_explicit_funded_configuration_fails(value):
    with pytest.raises(ValueError):funded_strategies({'funded_strategies':value},('CAS_LAG_V1',))


def test_legacy_configuration_and_explicit_empty_are_distinct():
    names=('CAS_LAG_V1','OPEN_DRIVE_FAST')
    assert funded_strategies({},names)==names
    assert funded_strategies({'funded_strategies':[]},names)==()
    assert funded_strategies({'funded_strategies':['CAS_LAG_V1']},names)==('CAS_LAG_V1',)


def test_observed_signal_cannot_send_an_unfunded_buy(tmp_path):
    async def run():
        engine,broker,ledger,clock,inputs=setup(tmp_path,'OPEN_DRIVE_FAST')
        engine.runtime.enabled_strategies=frozenset({'CAS_LAG_V1'})
        assert engine.directional.view()[0]['state']=='SIGNAL'
        assert engine.directional.view()[0]['funded_enabled'] is False
        assert not await engine.cycle()
        assert broker.requests==[]
        assert engine.directional.last_reason=='FUNDED_STRATEGY_DISABLED'
    asyncio.run(run())


def test_unfunded_first_signal_does_not_starve_funded_signal(tmp_path):
    async def run():
        engine,broker,ledger,clock,inputs=setup(tmp_path,'OPEN_DRIVE_FAST')
        base=inputs.evaluations['OPEN_DRIVE_FAST'];other=replace(base,strategy='TREND_PULLBACK_FAST')
        engine.directional.enabled=(base.strategy,other.strategy)
        engine.runtime.enabled_strategies=frozenset({other.strategy})
        engine.directional.update(replace(inputs,evaluations={base.strategy:base,other.strategy:other}))
        assert await engine.cycle()
        assert len(broker.requests)==1
        assert engine.directional.selection['selected']==other.strategy
    asyncio.run(run())


def test_funded_change_preserves_all_other_configuration_and_is_idempotent():
    source='strategies = ["CAS_LAG_V1", "OPEN_DRIVE_FAST"]\nlive_order_authority = true\nprofit_exit_retain = "0.50"\n[limits]\nprobe = 2\n'
    import tomllib
    result=amend_funded(source,['CAS_LAG_V1'])
    before=tomllib.loads(source);after=tomllib.loads(result)
    assert after.pop('funded_strategies')==['CAS_LAG_V1']
    assert before==after
    assert amend_funded(result,['CAS_LAG_V1'])==result

