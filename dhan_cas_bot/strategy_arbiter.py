"""Rank eligible signals using already closed executions, never future prices.

Shared capital permits one lifecycle. Fallback order is deterministic, not a
claim that the best future trade is known. At least three filled closed
lifecycles are needed to rank an engine by its estimated charge-adjusted return.
Cancelled attempts and open/unreconciled positions cannot improve its rank.
"""
import json
from datetime import datetime
from decimal import Decimal as D, ROUND_CEILING, InvalidOperation


def scores(ledger,now):
    records={};execution={}
    for row in ledger.db.execute("SELECT * FROM lifecycles WHERE state='CLOSED' ORDER BY rowid DESC LIMIT 256"):
        payload=json.loads(row['payload']);owner=payload.get('strategy','CAS_LAG_V1')
        totals=ledger.lifecycle_totals(row['lifecycle_id'])
        if totals['unresolved'] or totals['quantity']:continue
        # Only reconciled, dispatched entry opportunities belong in the fill
        # denominator. Prepared/aborted intents are not exchange misses.
        entries=list(ledger.db.execute("SELECT i.* FROM intents i WHERE i.lifecycle_id=? AND i.side='BUY' AND i.state IN ('FILLED','CANCELLED','REJECTED','EXPIRED') AND EXISTS(SELECT 1 FROM attempts a WHERE a.intent_id=i.intent_id)",(row['lifecycle_id'],)))
        stamps=list(ledger.db.execute('SELECT a.sent_at FROM attempts a JOIN intents i ON i.intent_id=a.intent_id WHERE i.lifecycle_id=?',(row['lifecycle_id'],)))
        fill_rows=list(ledger.db.execute('SELECT f.quantity,f.price,f.fees,f.order_id,f.intent_id,f.occurred_at,i.side FROM fills f JOIN intents i ON i.intent_id=f.intent_id WHERE i.lifecycle_id=?',(row['lifecycle_id'],)))
        if any(datetime.fromisoformat(r['sent_at'])>now for r in stamps) or any(datetime.fromisoformat(r['occurred_at'])>now for r in fill_rows):continue
        if entries:
            sent_ids={i['intent_id'] for i in entries}
            quantity=sum(ledger.db.execute('SELECT coalesce(sum(quantity),0) FROM fills WHERE intent_id=?',(ident,)).fetchone()[0] for ident in sent_ids)
            requested=sum(i['quantity'] for i in entries)
            fractions=execution.setdefault(owner,[])
            if len(fractions)<30 and 0<=quantity<=requested and requested>0:fractions.append(D(quantity)/requested)
        last=ledger.db.execute('SELECT max(f.occurred_at) AS stamp FROM fills f JOIN intents i ON i.intent_id=f.intent_id WHERE i.lifecycle_id=?',(row['lifecycle_id'],)).fetchone()['stamp']
        if not last or datetime.fromisoformat(last)>now:continue
        if totals['unresolved'] or totals['quantity'] or totals['entry_debit']<=0:continue
        fills=fill_rows
        buys=[f for f in fills if f['side']=='BUY']; sells=[f for f in fills if f['side']=='SELL']
        if not buys or not sells:continue  # settlement cannot establish executable exit speed
        cost=sum((D(f['price'])*f['quantity'] for f in buys),D(0))
        proceeds=sum((D(f['price'])*f['quantity'] for f in sells),D(0))
        if cost<=0:continue
        # Fees published later cannot leak into an earlier strategy ranking.
        # Count executed orders, never zero-fill IOC retries as paid orders.
        from .risk import FeeSchedule, ceil_paise
        paid={'BUY':D(0),'SELL':D(0)};counts={'BUY':0,'SELL':0}
        order_groups={}
        for fill in fills:order_groups.setdefault((fill['side'],fill['order_id'],fill['intent_id']),[]).append(fill)
        for (side,order_id,intent_id),group in order_groups.items():
            turnover=sum((D(f['price'])*f['quantity'] for f in group),D(0))
            modeled=(FeeSchedule().buy if side=='BUY' else FeeSchedule().sell)(turnover,1)
            reported=sum((D(f['fees']) for f in group),D(0))
            charge=ledger.db.execute('SELECT fees,observed_at FROM order_charges WHERE order_id=? AND intent_id=?',(order_id,intent_id)).fetchone()
            if charge and datetime.fromisoformat(charge['observed_at'])<=now:reported=max(reported,D(charge['fees']))
            paid[side]+=max(reported,ceil_paise(modeled));counts[side]+=1
        value=(proceeds-paid['SELL']-cost-paid['BUY'])/(cost+paid['BUY'])
        frictions=[]
        for intent in entries:
            if not any(f['intent_id']==intent['intent_id'] for f in buys):continue
            decision=ledger.db.execute("SELECT payload,received_at FROM observations WHERE identity=? AND kind='ENTRY_DECISION'",('decision:'+intent['intent_id'],)).fetchone()
            if not decision or datetime.fromisoformat(decision['received_at'])>now:continue
            try:
                detail=json.loads(decision['payload']);bid=D(detail['book']['bids'][0]['price']);limit=D(detail['limit'])
                if limit.is_finite() and bid.is_finite() and limit>0 and 0<bid<=limit:
                    frictions.append((limit-bid)/limit)
            except (KeyError,IndexError,TypeError,ValueError,InvalidOperation):continue
        friction=sum(frictions,D(0))/len(frictions) if frictions else None
        minutes=max(D(1)/60,D(str((datetime.fromisoformat(last)-min(datetime.fromisoformat(f['occurred_at']) for f in buys)).total_seconds()))/60)
        started=min((datetime.fromisoformat(r['sent_at']) for r in stamps),default=min(datetime.fromisoformat(f['occurred_at']) for f in buys))
        dispatch_minutes=max(minutes,D(str((datetime.fromisoformat(last)-started).total_seconds()))/60)
        values=records.setdefault(owner,[])
        if len(values)<30:values.append((value,(proceeds-cost)/cost,minutes,datetime.fromisoformat(last).date(),counts['BUY'],counts['SELL'],friction,(paid['BUY']+paid['SELL'])/cost,dispatch_minutes))
    result={}
    for owner,rows in records.items():
        n=len(rows);mean=sum((r[0] for r in rows),D(0))/n
        variance=sum(((r[0]-mean)**2 for r in rows),D(0))/(n-1) if n>1 else D(0)
        result[owner]={'filled_closed':n,'mean_estimated_net_return':str(mean),
            'mean_gross_return':str(sum((r[1] for r in rows),D(0))/n),
            'mean_holding_minutes':str(sum((r[2] for r in rows),D(0))/n),
            'mean_dispatch_to_exit_minutes':str(sum((r[8] for r in rows),D(0))/n),
            'mean_filled_buy_orders':str(sum((D(r[4]) for r in rows),D(0))/n),
            'mean_filled_sell_orders':str(sum((D(r[5]) for r in rows),D(0))/n),
            'mean_entry_friction_fraction':str(sum((r[6] for r in rows),D(0))/n) if all(r[6] is not None for r in rows) else None,
            'mean_cost_fraction':str(sum((r[7] for r in rows),D(0))/n),
            'return_standard_error':str((variance/n).sqrt()) if n>1 else None,
            'sessions':len({r[3] for r in rows}),'ranking_available':n>=3,
            'source':'CLOSED_LIVE_EXECUTIONS_ESTIMATED_CHARGES'}
    for owner,fractions in execution.items():
        if not fractions:continue
        history=result.setdefault(owner,{'filled_closed':0,'ranking_available':False,
            'source':'CLOSED_ENTRY_EXECUTION_RECEIPTS'})
        history.update({'closed_entry_opportunities':len(fractions),
            'filled_entry_opportunities':sum(f>0 for f in fractions),
            'entry_fill_rate':str(D(sum(f>0 for f in fractions))/len(fractions)),
            'mean_entry_fill_fraction':str(sum(fractions,D(0))/len(fractions))})
    return result


def execution_score(signal,candidate,ranking,now):
    """Cash utility of an executable candidate; targets are not forecasts.

    Use worst permitted entry. With measured executed-order counts, charge
    only spread deterioration beyond the previously paid entry friction;
    gross realized returns already contain historical crossing/slippage.
    Missing comparable observations retain the conservative full reserve.
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
    comparison=history.get('mean_dispatch_to_exit_minutes') or duration
    fraction=history.get('mean_entry_fill_fraction')
    expected=None; rate=None;incremental=friction;cost_basis='CONSERVATIVE_FALLBACK'
    buy_children=1;sell_children=3
    if measured and gross is not None and duration is not None:
        buy_count=history.get('mean_filled_buy_orders');sell_count=history.get('mean_filled_sell_orders')
        if buy_count is not None and sell_count is not None:
            minimum=(quantity+inst.freeze_qty-1)//inst.freeze_qty
            buy_children=max(minimum,int(D(buy_count).to_integral_value(rounding=ROUND_CEILING)))
            sell_children=max(minimum,int(D(sell_count).to_integral_value(rounding=ROUND_CEILING)))
            cost_basis='PRIOR_FILLED_ORDERS'
            baseline=history.get('mean_entry_friction_fraction')
            if baseline is not None:incremental=max(D(0),friction-exposure*D(baseline))
        sale=exposure*max(D(0),1+D(gross))
        costs=FeeSchedule().buy(exposure,buy_children)+FeeSchedule().sell(sale,sell_children)
        observed=history.get('mean_cost_fraction')
        if observed is not None:costs=max(costs,exposure*D(observed))
        expected=exposure*D(gross)-costs-incremental
        # A conditional winner with poor IOC completion must not look like a
        # reliably deployed full-size trade. Keep the conditional amount visible.
        if fraction is not None and 0<=D(fraction)<=1:
            rate=expected*D(fraction)/max(D(1)/60,D(duration),D(comparison))
        elif expected<=0:
            rate=expected/max(D(1)/60,D(duration),D(comparison))
    horizon=max(D(1)/60,D(str((signal.exit_at-now).total_seconds()))/60)
    return {'strategy':signal.strategy,'side':signal.side,'security_id':inst.security_id,
        'quantity':quantity,'limit':str(limit),'friction_cash':str(friction),
        'incremental_friction_cash':str(incremental),'cost_basis':cost_basis,
        'estimated_buy_orders':buy_children,'estimated_sell_orders':sell_children,
        'filled_closed':history.get('filled_closed',0),'sessions':history.get('sessions',0),
        'return_standard_error':history.get('return_standard_error'),
        'entry_fill_rate':history.get('entry_fill_rate'),
        'mean_entry_fill_fraction':fraction,
        'closed_entry_opportunities':history.get('closed_entry_opportunities',0),
        'filled_entry_opportunities':history.get('filled_entry_opportunities',0),
        'estimated_net_profit':str(expected) if expected is not None else None,
        'estimated_profit_per_minute':str(rate) if rate is not None else None,
        'holding_minutes':str(D(duration)) if duration is not None else str(horizon),
        'scoring_minutes':str(max(D(duration),D(comparison))) if duration is not None else None,
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
