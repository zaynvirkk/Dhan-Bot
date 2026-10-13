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
        values=records.setdefault(owner,[])
        if len(values)<30:values.append(value)
    return {owner:{'filled_closed':len(rows),'mean_estimated_net_return':str(sum(rows,D(0))/len(rows)),
                   'ranking_available':len(rows)>=3,'source':'CLOSED_LIVE_EXECUTIONS_ESTIMATED_CHARGES'}
            for owner,rows in records.items()}


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
