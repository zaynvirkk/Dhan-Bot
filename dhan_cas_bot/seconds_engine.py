"""Quote-rule adapter for the existing shared, reconciled order manager.

Importing/constructing this adapter never enables money permission. The normal
funded allowlist, route proof, cash limits and broker pre-dispatch checks apply.
"""
from dataclasses import asdict
from datetime import timedelta
from decimal import Decimal as D

from .seconds_strategies import NAMES, LABELS, RULES, SecondsTape, entry_candidate
from .session_strategies import Evaluation


class SecondsEngine:
    def __init__(self, parent):
        self.parent=parent;self.tape=SecondsTape();self.evaluations={}
        self.last_refresh=None;self.last_recorded=None
        self.last_budget=None
        self.discovery_budget=None
        self.event=None;self.event_health={'state':'UNAVAILABLE','reason':'EVENT_FEED_UNAVAILABLE'}

    def reset(self):
        self.tape.reset();self.last_refresh=None;self.evaluations={};self.discovery_budget=None

    def ready(self):
        now=self.parent.engine.now();data=self.parent.inputs
        return bool(data and data.calendar and data.calendar.is_open(now) and self.tape.future_current(now))

    def refresh(self, *, budget=None, force=False):
        parent=self.parent;engine=parent.engine;now=engine.now()
        if budget is not None:self.last_budget=budget
        if not force and self.last_refresh and 0<=(now-self.last_refresh).total_seconds()<.25:return
        data=parent.inputs
        self.evaluations=self.tape.evaluate(now,engine.books,(),data.calendar if data else None,
                                          budget=self.last_budget,event=self.event)
        if self.evaluations[NAMES[4]].reason=='EVENT_FEED_UNAVAILABLE' and self.event_health['state']=='CONNECTED':
            from dataclasses import replace
            self.evaluations[NAMES[4]]=replace(self.evaluations[NAMES[4]],state='WAITING',reason='NO_FRESH_EVENT')
        self.last_refresh=now
        if self.last_recorded is None or (now-self.last_recorded).total_seconds()>=1:
            for name,sample in self.evaluations.items():
                if name in parent.enabled:
                    engine.runtime.ledger.observe(f'strategy-evaluation:{name}:{now.isoformat()}:{sample.state}',
                                                  'STRATEGY_EVALUATION',asdict(sample))
            self.last_recorded=now

    def signals(self):
        # Discovery must follow reconciled bankroll changes too. Otherwise an
        # old small budget can suppress every newly affordable setup before
        # candidate() ever gets a chance to read current cash. This cached
        # observation is only a discovery filter; dispatch still reads funds
        # and rechecks every money/input prerequisite as before.
        engine=self.parent.engine;account=engine.runtime.account_refresh
        funds=getattr(account,'funds',None)
        budget=None
        if account is not None and account.fresh and funds is not None:
            now=engine.now();revision=getattr(engine.runtime.ledger,'account_revision',None)
            cached=self.discovery_budget
            if (cached is not None and cached[0] is funds and cached[1]==revision
                    and 0<=(now-cached[2]).total_seconds()<.25):
                budget=cached[3]
            else:
                allocation=engine._allocation(funds)
                budget=min(allocation.remaining,allocation.spendable_cash,allocation.bankroll*D('.95'))
                if allocation.selected_cap_remaining is not None:budget=min(budget,allocation.selected_cap_remaining)
                self.discovery_budget=(funds,revision,now,budget)
        self.refresh(budget=budget,force=budget is not None and budget!=self.last_budget)
        return [sample for name,sample in self.evaluations.items() if name in self.parent.enabled and sample.state=='SIGNAL']

    def candidate(self, signal, allocation):
        p=self.parent;engine=p.engine
        budget=min(allocation.remaining,allocation.spendable_cash,allocation.bankroll*D('.95'))
        if allocation.selected_cap_remaining is not None:budget=min(budget,allocation.selected_cap_remaining)
        # Re-evaluate the full quote rule with current cash, so a known
        # unaffordable ATM contract cannot hide an eligible farther strike.
        self.refresh(budget=budget,force=True)
        current=self.evaluations.get(signal.strategy)
        if not current or current.state!='SIGNAL' or current.details['episode']!=signal.details['episode']:
            p.last_reason='SECONDS_SIGNAL_CHANGED';return None
        result=entry_candidate(signal,engine.books,budget,engine.now())
        p.candidate_checks=[{'security_id':signal.details.get('security_id'),
            'reason':'READY' if result else 'NO_AFFORDABLE_LIQUID_CONTRACT','budget':str(budget)}]
        if result is None:p.last_reason='NO_AFFORDABLE_LIQUID_CONTRACT'
        return result

    def valid(self, signal):
        if not self.ready():return False
        self.refresh(force=True)
        sample=self.evaluations.get(signal.strategy)
        return bool(sample and sample.state=='SIGNAL' and sample.details.get('episode')==signal.details.get('episode'))

    def exit_reason(self, payload, book, entry, now):
        if not book or not book.top_bid:return None
        policy=payload['signal']['details'];bid=book.top_bid.price
        if bid<=entry*D('.95'):return 'SECONDS_PREMIUM_STOP'
        if bid>=D(policy['target_price']):return 'SECONDS_TARGET_REPRICED'
        if not self.ready():return 'SECONDS_INPUT_LOST'
        value=self.tape.future[-1][1];anchor=D(policy['anchor_future']);side=D(policy['direction'])
        if side*(value-anchor)<-anchor*D('.0001'):return 'SECONDS_DIRECTION_FAILED'
        return None
