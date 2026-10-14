import json,tomllib
from decimal import Decimal as D
import pytest


def test_profit_activation_changes_only_its_two_explicit_config_fields():
    from dhan_cas_bot.profit_activation import amend_config
    original='live_order_authority=true\naccount_id="fixture"\nstrategies=["CAS_LAG_V1"]\n[other]\nkeep="same"\n'
    result=amend_config(original,D('.5'));parsed=tomllib.loads(result)
    assert parsed.pop('profit_exit_policy')=='NET_PROFIT_RATCHET_V1'
    assert parsed.pop('profit_exit_retain')=='0.5'
    assert parsed==tomllib.loads(original)
    assert amend_config(result,D('.5'))==result


@pytest.mark.parametrize('case',['pending','unmanaged','mismatch','unresolved','cas'])
def test_exposed_handoff_rejects_any_unverified_obligation(case):
    from dhan_cas_bot.profit_activation import require_managed
    active={'security_id':'123','payload':json.dumps({'strategy':'ORDINARY_PUBLISHED_PCR_TRAIL'})}
    positions=[{'securityId':'123','netQty':65,'productType':'MARGIN','exchangeSegment':'NSE_FNO'}]
    totals={'quantity':65,'unresolved':False}
    if case=='unmanaged':positions.append({'securityId':'other','netQty':65})
    if case=='mismatch':totals['quantity']=130
    if case=='unresolved':totals['unresolved']=True
    if case=='cas':active['payload']=json.dumps({'strategy':'CAS_LAG_V1'})
    with pytest.raises(ValueError):require_managed(active,totals,positions,case=='pending')


def test_exposed_handoff_accepts_only_the_existing_reconciled_long():
    from dhan_cas_bot.profit_activation import require_managed
    active={'security_id':'123','payload':json.dumps({'strategy':'ORDINARY_PUBLISHED_PCR_TRAIL'})}
    require_managed(active,{'quantity':65,'unresolved':False},[{'securityId':'123','netQty':65,'productType':'MARGIN','exchangeSegment':'NSE_FNO'}],False)
    require_managed(None,None,[],False)
