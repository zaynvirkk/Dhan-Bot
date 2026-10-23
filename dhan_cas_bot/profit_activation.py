"""Narrow validation for an explicitly authorised managed-position upgrade."""
import json,re,tomllib
from hashlib import sha256
from decimal import Decimal
from .session_strategies import STRATEGIES,CAS


def owned_route_digest(ledger):
    """Fingerprint the unresolved obligation and its accounting; never resolve it."""
    intents=[dict(row) for row in ledger.pending_intents()]
    evidence={'intents':intents,'attempts':[],'orders':[],'fills':[],
              'route_probe':ledger.metadata('route_probe'),
              'extra_attempts':[dict(row) for row in ledger.db.execute(
                  "SELECT * FROM metadata WHERE key LIKE 'probe.extra_attempt:%' ORDER BY key")],
              'counters':[dict(row) for row in ledger.db.execute(
                  "SELECT * FROM counters WHERE name LIKE 'probe.%' ORDER BY name")]}
    for row in intents:
        for table,key in (('attempts','attempt_id'),('orders','order_id'),('fills','trade_id')):
            evidence[table].extend(dict(r) for r in ledger.db.execute(
                f'SELECT * FROM {table} WHERE intent_id=? ORDER BY {key}',(row['intent_id'],)))
    return sha256(json.dumps(evidence,sort_keys=True).encode()).hexdigest()


def require_owned_route_recovery(ledger,positions,orders):
    """Allow source repairs while a sole unknown probe stays entry-blocking."""
    if any(int(p.get('netQty',p.get('netQuantity',0))) for p in positions) or orders:
        raise ValueError('broker exposure prevents route recovery upgrade')
    if ledger.db.execute("SELECT 1 FROM lifecycles WHERE state!='CLOSED' LIMIT 1").fetchone():
        raise ValueError('active lifecycle prevents route recovery upgrade')
    pending=ledger.pending_intents()
    if len(pending)!=1:raise ValueError('exactly one unknown owned probe required')
    row=pending[0]
    if (row['lifecycle_id'],row['side'],row['state'])!=('route-probe','BUY','SEND_UNKNOWN'):
        raise ValueError('unrecognized pending obligation')
    for table in ('fills','orders'):
        if ledger.db.execute(f'SELECT 1 FROM {table} WHERE intent_id=? LIMIT 1',(row['intent_id'],)).fetchone():
            raise ValueError('known broker obligation requires normal reconciliation')
    attempts=list(ledger.db.execute('SELECT response_state FROM attempts WHERE intent_id=?',(row['intent_id'],)))
    if not attempts or any(a['response_state']!='UNKNOWN' for a in attempts):
        raise ValueError('unknown completed request evidence required')
    return owned_route_digest(ledger)


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
