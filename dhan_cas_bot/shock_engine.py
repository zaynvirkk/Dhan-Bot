"""VOLATILITY_SHOCK_V1 owner; one existing OMS, durable episodes and cash exits."""
from dataclasses import asdict, replace
from datetime import datetime, timedelta
from decimal import Decimal as D
import json
import uuid
from math import ceil

from .domain import Intent, json_safe, digest
from .risk import reserve_cash, FeeSchedule
from .volatility_shock import SHOCK, RULE, EXIT, ALLOCATION, episode_id, shock_allocation, select_shock_candidate, shock_exit
from .session_strategies import IST


def rejection_reason(checks):
    """Report the furthest observed entry gate, never imply missing cash."""
    reasons={c.get('reason') for c in checks}
    if 'SHOCK_SCENARIO_BELOW_FLOOR' in reasons:return 'SHOCK_SCENARIO_BELOW_FLOOR'
    if len(reasons)==1:return next(iter(reasons)) or 'NO_AFFORDABLE_LIQUID_CONTRACT'
    return 'NO_AFFORDABLE_LIQUID_CONTRACT'


class ShockEngine:
    def __init__(self,directional):
        self.directional=directional
        self.engine=directional.engine
        self.sample=None
        self.selected=None
        self.last_checks=[]
        self.last_reason='INPUTS_NOT_RECEIVED'
        self.assessed_at=None
        self.candidate_signal_at=None
        # Restore diagnostics only. A historic signal never restores sample,
        # permission, or a dispatchable order after restart.
        prefix=f'directional-signal:{self.engine.now().astimezone(IST).date()}:{SHOCK}:'
        ledger=self.engine.runtime.ledger
        latest=None
        for row in ledger.db.execute('SELECT key,value FROM metadata WHERE key>=? AND key<?',(prefix,prefix+'~')):
            if row['key'].endswith((':assessment',':consumed')):continue
            raw=json.loads(row['value'])
            assessment=ledger.metadata(row['key']+':assessment',{})
            stamp=raw.get('evaluated_at')
            if stamp and assessment and (latest is None or stamp>latest[0]):latest=(stamp,assessment)
        if latest:
            self.candidate_signal_at,assessment=latest
            self.last_checks=assessment.get('candidate_checks',[])
            self.last_reason=assessment.get('reason','INPUTS_NOT_RECEIVED')
            if self.last_reason=='NO_AFFORDABLE_LIQUID_CONTRACT':self.last_reason=rejection_reason(self.last_checks)
            self.assessed_at=assessment.get('assessed_at')

    def update(self,sample):
        """Only a completed, usable new bar can rearm an episode; retries cannot."""
        if not sample:return None
        ledger=self.engine.runtime.ledger
        key='shock-episode:'+sample.evaluated_at.astimezone(IST).date().isoformat()
        old=ledger.metadata(key,{})
        if sample.state in ('INPUT_UNAVAILABLE','WAITING'):return sample
        at=sample.evaluated_at.isoformat()
        if old.get('bar_at') and at<old['bar_at']:return None
        direction=sample.side
        new=sample.state=='SIGNAL'
        feature_digest=digest({k:v for k,v in sample.details.items() if k not in ('source_received_at','source','episode')})
        if old.get('bar_at')==at:
            if old.get('conflicted') or old.get('feature_digest')!=feature_digest or old.get('qualifying')!=new or old.get('side')!=direction:
                self.last_reason='SHOCK_BAR_CONFLICT'
                self.invalidate()
                ledger.put_metadata(key,{**old,'conflicted':True})
                return replace(sample,state='INPUT_UNAVAILABLE',reason=self.last_reason,side=None)
            episode=old.get('episode')
        else:
            episode=old.get('episode') if new and old.get('qualifying') and direction==old.get('side') else None
            if new and not episode:episode=episode_id(sample.evaluated_at.astimezone(IST).date(),direction,sample.evaluated_at)
            ledger.put_metadata(key,{'bar_at':at,'qualifying':new,'side':direction,'episode':episode,'feature_digest':feature_digest})
        if new:
            sample=replace(sample,details={**sample.details,'episode':episode})
            # Preserve FIRST observation; later qualifying bars cannot renew it.
            previous=ledger.metadata('shock-first:'+episode)
            if previous:sample=replace(sample,evaluated_at=datetime.fromisoformat(previous['bar_at']),details={**sample.details,'source_received_at':previous['received_at']})
            else:ledger.put_metadata('shock-first:'+episode,{'bar_at':at,'received_at':sample.details['source_received_at']})
            self.sample=sample
        else:self.sample=None
        return sample

    def future_ready(self):
        channel=getattr(self.engine.runtime,'future_input',None)
        return bool(channel and channel.health(self.engine.now()).get('current'))

    def invalidate(self):
        if self.sample:
            ledger=self.engine.runtime.ledger
            key=self.directional.signal_key(self.sample)+':consumed'
            if not ledger.metadata(key):ledger.put_metadata(key,{'reason':'SHOCK_RECONNECT_INVALIDATED'})
        self.sample=None

    def valid(self,signal):
        data=self.directional.inputs;now=self.engine.now()
        if not data or data.error or not data.calendar or not data.calendar.is_open(now):return False
        if not 0<=(now-signal.evaluated_at).total_seconds()<=30:return False
        if not self.future_ready() or not self.sample or self.sample.details.get('episode')!=signal.details.get('episode'):return False
        base=data.future_bars.get(signal.evaluated_at-timedelta(minutes=5))
        tape=self.engine.runtime.future_input.tape
        if not base or not tape.future:return False
        direction=1 if signal.side=='CE' else -1
        if direction*(tape.future[-1][1]/base.close-1)<D('.001'):return False
        live=getattr(self.engine,'shock_spot',None)
        if live:
            value,received_ns=live
            if not 0<=int(now.timestamp()*1e9)-received_ns<=2_000_000_000:return False
            if direction*(value-D(signal.details['breakout_boundary']))<=0:return False
        # A newer completed observation that failed the rule invalidates entry.
        current=data.evaluations.get(SHOCK)
        return bool(current and current.state=='SIGNAL' and current.side==signal.side)

    async def enter_locked(self,snapshot):
        d=self.directional;e=self.engine;r=e.runtime;ledger=r.ledger;now=e.now()
        if SHOCK not in d.enabled or SHOCK not in r.enabled_strategies:return False
        signal=self.sample
        if not signal:return False
        key=d.signal_key(signal)+':consumed'
        if ledger.metadata(key):return False
        if now>signal.evaluated_at+timedelta(seconds=30):
            ledger.put_metadata(key,{'reason':'ENTRY_DEADLINE_MISSED'});self.last_reason='ENTRY_DEADLINE_MISSED';return False
        if e.active or snapshot['unresolved'] or ledger.pending_intents():return False
        if any(int(p.get('netQty',p.get('netQuantity',0))) for p in snapshot['positions']):return False
        last=ledger.metadata('shock-last-closed')
        if last and now-datetime.fromisoformat(last)<timedelta(minutes=15):
            self.last_reason='SHOCK_COOLDOWN';d.record_assessment(signal,self.last_reason);return False
        if not r.permit_entry(strategy=SHOCK) or not self.valid(signal):
            self.last_reason='ENTRY_NOT_PERMITTED' if not r.permit_entry(strategy=SHOCK) else 'FUTURES_FEED_UNAVAILABLE'
            d.record_assessment(signal,self.last_reason);return False
        funds=await r.broker.funds()
        if funds.broker_account!=r.mandate.account_id or not self.valid(signal) or not r.permit_entry(strategy=SHOCK):return False
        allocation=shock_allocation(e._allocation(funds))
        budget=min(allocation.remaining,allocation.spendable_cash)
        if allocation.selected_cap_remaining is not None:budget=min(budget,allocation.selected_cap_remaining)
        chosen,checks=select_shock_candidate(signal,e.instruments.values(),e.books,budget,e.now(),d.inputs.calendar)
        self.last_checks=checks;self.selected=chosen
        self.assessed_at=e.now().isoformat()
        self.candidate_signal_at=signal.evaluated_at.isoformat()
        if not chosen:
            self.last_reason=rejection_reason(checks);d.record_assessment(signal,self.last_reason,checks);return False
        d.record_assessment(signal,'READY',checks)
        self.last_reason='READY'
        selection={'evaluated_at':e.now().isoformat(),'mode':'DECLARED_CONTINUATION_SCENARIO',
            'reason':'SCENARIO_ONLY_NOT_EXPECTED_RETURN','selected':SHOCK,'candidates':[],
            'scenario':chosen.assumptions,'entry_cash':str(chosen.entry_cash),
            'scenario_multiple':str(chosen.scenario_multiple),'budget':str(budget)}
        d.selection=selection
        ledger.put_metadata('strategy-selection:'+now.astimezone(IST).date().isoformat(),selection)
        inst=chosen.instrument;lid='l'+uuid.uuid4().hex
        payload={'strategy':SHOCK,'instrument':asdict(inst),'signal':asdict(signal),'exit_at':signal.exit_at,
            'shock':{'rule':RULE,'exit_policy':EXIT,'allocation_policy':ALLOCATION,'episode':signal.details['episode'],
                     'planned_entry_cash':str(chosen.entry_cash),'fee_reserve':str(chosen.exit_reserve),
                     'scenario_multiple':str(chosen.scenario_multiple),'scenario':chosen.assumptions},'selection':selection}
        intent=Intent('i'+uuid.uuid4().hex,'BUY',inst,chosen.quantity,chosen.limit,'e'+uuid.uuid4().hex[:28],e.now(),lid)
        with ledger.transaction() as db:
            db.execute('INSERT INTO lifecycles VALUES(?,?,?,?,?,?)',(lid,e.session_id,inst.security_id,str(allocation.bankroll),'OPEN',json.dumps(json_safe(payload))))
            db.execute('INSERT INTO metadata VALUES(?,?)',(key,json.dumps({'lifecycle':lid,'reason':'DECISION_COMMITTED'})))
            db.execute('INSERT INTO metadata VALUES(?,?)',(d.family_key(signal),json.dumps({'lifecycle':lid,'strategy':SHOCK})))
        ledger.observe('decision:'+intent.intent_id,'ENTRY_DECISION',{'strategy':SHOCK,'signal':asdict(signal),
            'book':asdict(chosen.book),'allocation':asdict(allocation),'quantity':chosen.quantity,'limit':chosen.limit,
            'selection':selection,'candidate_checks':checks})
        def current():
            return (r.permit_entry(strategy=SHOCK) and self.valid(signal) and e.books.get(inst.security_id) is chosen.book
                    and d.book_current(chosen.book) and chosen.entry_cash+chosen.exit_reserve<=budget)
        await r.orders.submit(intent,reserved_cash=reserve_cash(chosen.entry_cash+chosen.exit_reserve),pre_dispatch=current)
        r.status.state='ENTRY_PENDING';r.status.reason=SHOCK+':ENTRY_SUBMITTED'
        return True

    async def manage(self,active,snapshot,inst,totals,quantity):
        d=self.directional;e=self.engine;r=e.runtime;ledger=r.ledger;now=e.now()
        payload=json.loads(active['payload']);signal=payload['signal'];details=signal['details']
        if payload.get('shock',{}).get('exit_policy')!=EXIT:raise ValueError('unknown shock exit policy')
        fills=list(ledger.db.execute("SELECT f.order_id,f.quantity,f.price,f.occurred_at FROM fills f JOIN intents i ON f.intent_id=i.intent_id WHERE i.lifecycle_id=? AND i.side='BUY' ORDER BY f.occurred_at",(active['lifecycle_id'],)))
        turnover=sum((D(f['price'])*f['quantity'] for f in fills),D(0))
        entry_cash=max(totals['entry_debit'],turnover+FeeSchedule().buy(turnover,len({f['order_id'] for f in fills})))
        first=datetime.fromisoformat(fills[0]['occurred_at']);minutes=(now-first).total_seconds()/60
        invalid=False;data=d.inputs
        if data:
            spot=data.spot_bars;post=sorted(t for t in spot if first<t<=now)
            direction=1 if signal['side']=='CE' else -1
            boundary=D(details['breakout_boundary'])
            if len(post)>=2 and post[-1]-post[-2]==timedelta(minutes=1):
                invalid=all(direction*(spot[t].close-boundary)<0 for t in post[-2:])
            if post:
                t=post[-1]
                if t-timedelta(minutes=5) in spot:
                    invalid|=direction*(spot[t].close/spot[t-timedelta(minutes=5)].close-1)<=D('-.002')
        net=None;book=e.books.get(inst.security_id)
        if d.book_current(book) and book.top_bid:
            from .exits import executable_sale_units, sell_limit
            exit_limit=sell_limit(book)
            # Match the price reach of the actual existing OMS exit. Deeper
            # displayed bids cannot establish a fully liquidatable cash peak.
            reachable=replace(book,bids=tuple(l for l in book.bids if l.price>=exit_limit))
            slices=executable_sale_units(reachable,quantity)
            if sum(q for q,p in slices)==quantity:
                proceeds=sum((q*max(exit_limit,p-2*inst.tick_size) for q,p in slices),D(0))
                net=totals['sale_credit']+proceeds-FeeSchedule().sell(proceeds,ceil(quantity/inst.freeze_qty))-entry_cash
        key='shock-exit:'+active['lifecycle_id'];old=ledger.metadata(key)
        guard,reason=shock_exit(entry_cash,net,minutes,old,invalid,deadline=now>=datetime.fromisoformat(payload['exit_at']))
        guard.update(entry_cash=str(entry_cash),actual_average_entry=str(turnover/sum(f['quantity'] for f in fills)),
                     first_fill_at=first.isoformat(),observed_at=now.isoformat(),held_quantity=quantity,
                     quote_executable=net is not None)
        # Persist new high water, triggers, and at most one unchanged telemetry
        # sample per second rather than rewriting SQLite on every book frame.
        if old is None or any(guard.get(k)!=old.get(k) for k in ('peak_net_profit','minimum_net_profit','floor','triggered_reason','held_quantity')) or (now-datetime.fromisoformat(old['observed_at'])).total_seconds()>=1:
            ledger.put_metadata(key,guard)
        r.status.state='POSITION_OPEN';r.status.reason=SHOCK+':'+(reason or 'HOLDING')
        if not reason:return False
        ledger.put_metadata('directional-exit:'+active['lifecycle_id'],{'reason':reason,'due':now.isoformat()})
        if not data or not data.calendar or not data.calendar.is_open(now):
            r.status.reason='EXIT_LATCHED_WAITING_EXCHANGE_SESSION';return False
        if not d.book_current(book) or not book.top_bid:
            r.status.reason='EXIT_LATCHED_WAITING_CURRENT_BOOK';return False
        await e.exit_manager.reduce(inst,quantity,book,active['lifecycle_id'])
        r.status.state='EXIT_PENDING'
        return True
