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


@pytest.mark.parametrize('fault',['position','broker_pending','foreign_intent','sell','fill','unattempted'])
def test_route_recovery_cutover_cannot_adopt_other_or_unverified_exposure(tmp_path,fault):
    from tests.test_directional_engine import setup
    from dhan_cas_bot.domain import Intent,Fill
    from dhan_cas_bot.profit_activation import require_owned_route_recovery
    e,b,l,c,i=setup(tmp_path);inst=e.books['101'].instrument
    lifecycle='foreign' if fault=='foreign_intent' else 'route-probe'
    intent=Intent('r','SELL' if fault=='sell' else 'BUY',inst,65,D('.05'),'r',c[0],lifecycle)
    l.create_intent(intent,D(30))
    if fault!='unattempted':l.record_attempt('a','r','UNKNOWN',{'error':'HTTPStatusError'})
    if fault=='fill':l.record_fill_once(Fill('t','o','101',65,D('.05'),D(0),c[0]),'r',{})
    positions=[{'netQty':65}] if fault=='position' else []
    orders=[{'orderStatus':'PENDING'}] if fault=='broker_pending' else []
    with pytest.raises(ValueError):require_owned_route_recovery(l,positions,orders)


def test_route_recovery_preserves_unknown_liability_and_all_money_counters(tmp_path):
    from tests.test_directional_engine import setup
    from dhan_cas_bot.domain import Intent
    from dhan_cas_bot.profit_activation import require_owned_route_recovery,owned_route_digest
    e,b,l,c,i=setup(tmp_path);inst=e.books['101'].instrument
    l.create_intent(Intent('r','BUY',inst,65,D('.05'),'r',c[0],'route-probe'),D(30))
    l.record_attempt('a','r','UNKNOWN',{'error':'HTTPStatusError'})
    l.set_counter('probe.attempts:fixture',1)
    before=owned_route_digest(l)
    assert require_owned_route_recovery(l,[],[])==before
    assert l.pending_intents()[0]['state']=='SEND_UNKNOWN'
    assert l.counter('probe.attempts:fixture')==1 and owned_route_digest(l)==before
