"""Rank eligible signals using already closed executions, never future prices.

Shared capital permits one lifecycle. Fallback order is deterministic, not a
claim that the best future trade is known. At least three filled closed
lifecycles are needed to rank an engine by its estimated charge-adjusted return.
Cancelled attempts and open/unreconciled positions cannot improve its rank.
"""
import json
from datetime import datetime
from decimal import Decimal as D


def scores(ledger,now):
    records={}
    for row in ledger.db.execute("SELECT * FROM lifecycles WHERE state='CLOSED' ORDER BY rowid DESC LIMIT 256"):
        payload=json.loads(row['payload']);owner=payload.get('strategy','CAS_LAG_V1')
        last=ledger.db.execute('SELECT max(f.occurred_at) AS stamp FROM fills f JOIN intents i ON i.intent_id=f.intent_id WHERE i.lifecycle_id=?',(row['lifecycle_id'],)).fetchone()['stamp']
        if not last or datetime.fromisoformat(last)>now:continue
        totals=ledger.lifecycle_totals(row['lifecycle_id'])
        if totals['unresolved'] or totals['quantity'] or totals['entry_debit']<=0:continue
        value=(totals['sale_credit']-totals['entry_debit'])/totals['entry_debit']
        fills=list(ledger.db.execute('SELECT f.quantity,f.price,f.occurred_at,i.side FROM fills f JOIN intents i ON i.intent_id=f.intent_id WHERE i.lifecycle_id=?',(row['lifecycle_id'],)))
        buys=[f for f in fills if f['side']=='BUY']; sells=[f for f in fills if f['side']=='SELL']
        if not buys or not sells:continue  # settlement cannot establish executable exit speed
        cost=sum((D(f['price'])*f['quantity'] for f in buys),D(0))
        proceeds=sum((D(f['price'])*f['quantity'] for f in sells),D(0))
        if cost<=0:continue
        minutes=max(D(1)/60,D(str((datetime.fromisoformat(last)-min(datetime.fromisoformat(f['occurred_at']) for f in buys)).total_seconds()))/60)
        values=records.setdefault(owner,[])
        if len(values)<30:values.append((value,(proceeds-cost)/cost,minutes,datetime.fromisoformat(last).date()))
    result={}
    for owner,rows in records.items():
        n=len(rows);mean=sum((r[0] for r in rows),D(0))/n
        variance=sum(((r[0]-mean)**2 for r in rows),D(0))/(n-1) if n>1 else D(0)
        result[owner]={'filled_closed':n,'mean_estimated_net_return':str(mean),
            'mean_gross_return':str(sum((r[1] for r in rows),D(0))/n),
            'mean_holding_minutes':str(sum((r[2] for r in rows),D(0))/n),
            'return_standard_error':str((variance/n).sqrt()) if n>1 else None,
            'sessions':len({r[3] for r in rows}),'ranking_available':n>=3,
            'source':'CLOSED_LIVE_EXECUTIONS_ESTIMATED_CHARGES'}
    return result


def execution_score(signal,candidate,ranking,now):
    """Cash utility of an executable candidate; targets are not forecasts.

    Use the worst permitted entry and immediate bid as the friction reserve.
    These are noisy estimates from prior live outcomes, not predictions or
    confidence that a fill/profit will occur. Unmeasured engines stay unknown.
    """
    from .risk import FeeSchedule
    inst,quantity,limit,book=candidate
    exposure=quantity*limit
    friction=quantity*max(D(0),limit-book.top_bid.price)
    history=ranking.get(signal.strategy,{})
    measured=history.get('ranking_available',False)
    gross=history.get('mean_gross_return')
    duration=history.get('mean_holding_minutes')
    expected=None; rate=None
    if measured and gross is not None and duration is not None:
        sale=exposure*max(D(0),1+D(gross))
        expected=exposure*D(gross)-FeeSchedule().buy(exposure,1)-FeeSchedule().sell(sale,3)-friction
        rate=expected/max(D(1)/60,D(duration))
    horizon=max(D(1)/60,D(str((signal.exit_at-now).total_seconds()))/60)
    return {'strategy':signal.strategy,'side':signal.side,'security_id':inst.security_id,
        'quantity':quantity,'limit':str(limit),'friction_cash':str(friction),
        'filled_closed':history.get('filled_closed',0),'sessions':history.get('sessions',0),
        'return_standard_error':history.get('return_standard_error'),
        'estimated_net_profit':str(expected) if expected is not None else None,
        'estimated_profit_per_minute':str(rate) if rate is not None else None,
        'holding_minutes':str(D(duration)) if duration is not None else str(horizon),
        'friction_fraction':str(friction/exposure),'reason':'EXECUTABLE'}


def select_executable(rows):
    """Prefer measured cash/time. Abstain on contradictory unknown sides.

    No arbitrary side choice, no extra votes from alternate exits of a family.
    When all same-side opportunities lack outcomes, execution quality is an
    explicitly experimental fallback, never a claimed profitable forecast.
    """
    positive=[r for r in rows if r['estimated_profit_per_minute'] is not None and D(r['estimated_profit_per_minute'])>0]
    if positive:
        return max(positive,key=lambda r:(D(r['estimated_profit_per_minute']),-D(r['friction_fraction']))),'MEASURED_CASH_PER_MINUTE','SELECTED'
    unknown=[r for r in rows if r['estimated_profit_per_minute'] is None]
    if len({r['side'] for r in unknown})>1:
        return None,'EXPERIMENTAL_EXECUTION_QUALITY','CONFLICTING_UNRANKED_SIGNALS'
    if unknown:
        return min(unknown,key=lambda r:(D(r['friction_fraction']),D(r['holding_minutes']))),'EXPERIMENTAL_EXECUTION_QUALITY','SELECTED'
    return None,'MEASURED_CASH_PER_MINUTE','NO_POSITIVE_ESTIMATED_EDGE'


def rank_signals(signals,ledger,now,*,ranking=None):
    ranking=scores(ledger,now) if ranking is None else ranking
    def key(signal):
        row=ranking.get(signal.strategy,{})
        valid=row.get('ranking_available',False)
        value=D(row['mean_estimated_net_return']) if valid else D(0)
        # Positive measured engines first, unknown next, measured losing
        # engines last. Missing history is never labelled a profitable score.
        priority=2 if valid and value>0 else 0 if valid else 1
        return (-priority,-value,signal.evaluated_at,signal.strategy)
    return sorted(signals,key=key)
