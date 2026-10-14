"""Narrow validation for an explicitly authorised managed-position upgrade."""
import json,re,tomllib
from decimal import Decimal
from .session_strategies import STRATEGIES,CAS


def amend_config(text,retain):
    if not retain.is_finite() or not 0<retain<1:raise ValueError('invalid retention')
    before=tomllib.loads(text);head,sep,tail=text.partition('\n[')
    for key,value in (('profit_exit_policy','NET_PROFIT_RATCHET_V1'),('profit_exit_retain',str(retain))):
        line=key+' = '+json.dumps(value)
        if key in before:
            pattern=r'(?m)^'+key+r'\s*=\s*[^\n]*$'
            if len(re.findall(pattern,head))!=1:raise ValueError('ambiguous profit configuration')
            head=re.sub(pattern,lambda _:line,head)
        else:head=line+'\n'+head
    updated=head+sep+tail;after=tomllib.loads(updated);keys={'profit_exit_policy','profit_exit_retain'}
    if {k:v for k,v in before.items() if k not in keys}!={k:v for k,v in after.items() if k not in keys}:
        raise ValueError('unrelated configuration would change')
    return updated


def require_managed(active,totals,positions,pending):
    if pending or (totals and totals['unresolved']):raise ValueError('pending obligations prevent handoff')
    open_positions=[p for p in positions if int(p.get('netQty',p.get('netQuantity',0)))]
    if active is None:
        if open_positions:raise ValueError('unmanaged position prevents handoff')
        return
    owner=json.loads(active['payload']).get('strategy')
    if owner not in STRATEGIES or owner==CAS:raise ValueError('active strategy not supported for this migration')
    if any(str(p.get('securityId'))!=active['security_id'] or p.get('productType')!='MARGIN'
           or p.get('exchangeSegment')!='NSE_FNO' for p in open_positions):
        raise ValueError('foreign exposure prevents handoff')
    quantity=sum(int(p.get('netQty',p.get('netQuantity',0))) for p in open_positions)
    if quantity<0 or quantity!=totals['quantity']:raise ValueError('position reconciliation mismatch')
