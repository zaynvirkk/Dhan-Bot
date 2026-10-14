"""Allowlisted actual strategy executions; absent final charges stay absent."""
import json
from datetime import datetime
from decimal import Decimal as D
from dhan_cas_bot.session_strategies import STRATEGIES


def currency(value):
    """Display rupees without discarding sub-paise input before aggregation."""
    if value.as_tuple().exponent < -2:value=value.quantize(D('.01'))
    return format(value,'f')


def strategy_performance(db):
    result={}
    has_charges=db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='order_charges'").fetchone() is not None
    for row in db.execute("SELECT lifecycle_id,payload FROM lifecycles WHERE state='CLOSED' ORDER BY rowid DESC LIMIT 5000"):
        payload=json.loads(row['payload']);owner=payload.get('strategy','CAS_LAG_V1')
        if owner not in STRATEGIES:continue
        fills=list(db.execute('SELECT f.quantity,f.price,f.occurred_at,i.side FROM fills f JOIN intents i ON i.intent_id=f.intent_id WHERE i.lifecycle_id=? ORDER BY f.occurred_at',(row['lifecycle_id'],)))
        buys=[f for f in fills if f['side']=='BUY'];sells=[f for f in fills if f['side']=='SELL']
        if not buys or not sells:continue
        quantity=sum(f['quantity'] for f in buys)
        if quantity<=0 or quantity!=sum(f['quantity'] for f in sells):continue
        debit=sum((D(f['price'])*f['quantity'] for f in buys),D(0));credit=sum((D(f['price'])*f['quantity'] for f in sells),D(0))
        if any(not x.is_finite() or x<0 for x in (debit,credit)):continue
        charges=list(db.execute('SELECT c.fees,c.complete FROM order_charges c JOIN intents i ON i.intent_id=c.intent_id WHERE i.lifecycle_id=?',(row['lifecycle_id'],))) if has_charges else []
        count=db.execute('SELECT count(DISTINCT f.order_id) FROM fills f JOIN intents i ON i.intent_id=f.intent_id WHERE i.lifecycle_id=?',(row['lifecycle_id'],)).fetchone()[0]
        complete=len(charges)==count and all(c['complete'] for c in charges)
        fees=sum((D(c['fees']) for c in charges),D(0))
        if not fees.is_finite() or fees<0:continue
        gross=credit-debit;net=gross-fees if complete else None
        value=result.setdefault(owner,{'strategy':owner,'filled_closed':0,'gross':D(0),'fees':D(0),'complete':True,'wins':0,'losses':0,'trades':[]})
        value['filled_closed']+=1;value['gross']+=gross;value['fees']+=fees;value['complete']&=complete
        value['wins']+=net is not None and net>0;value['losses']+=net is not None and net<0
        if len(value['trades'])<20:
            value['trades'].append({'entry_at':buys[0]['occurred_at'],'exit_at':sells[-1]['occurred_at'],
                'quantity':quantity,'entry_price':currency(debit/quantity),'exit_price':currency(credit/quantity),
                'gross_pnl':currency(gross),'reported_charges':currency(fees) if charges else None,
                'net_pnl':currency(net) if net is not None else None,'charges_complete':complete,
                'holding_seconds':str((datetime.fromisoformat(sells[-1]['occurred_at'])-datetime.fromisoformat(buys[0]['occurred_at'])).total_seconds())})
    return [{'strategy':r['strategy'],'filled_closed':r['filled_closed'],'gross_pnl':currency(r['gross']),
        'reported_charges':currency(r['fees']) if r['complete'] else None,
        'charges_complete':r['complete'],'net_pnl':currency(r['gross']-r['fees']) if r['complete'] else None,
        'net_wins':r['wins'] if r['complete'] else None,'net_losses':r['losses'] if r['complete'] else None,
        'trades':r['trades']} for r in result.values()]
