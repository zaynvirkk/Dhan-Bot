"""Directional lifecycle owner using the existing durable OMS and cash limits.

Entry hypotheses remain unqualified for profitability. Configuration selects
engines; it does not bypass route, account, release or operator gates.
"""
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_CEILING
import json
import uuid

from .domain import Intent, json_safe
from .engine import restore_instrument
from .risk import FeeSchedule, reserve_cash, worst_case_entry_cash
from .session_strategies import CAS, GAP, REBOUND, STRATEGIES, IST, Calendar, Evaluation
from .seconds_strategies import NAMES as SECONDS_NAMES, RULES as SECONDS_RULES

D = Decimal


@dataclass(frozen=True)
class Inputs:
    calendar: Calendar | None
    evaluations: dict
    option_bars: dict
    received_at: datetime
    error: str = ""


class DirectionalEngine:
    def __init__(self, engine, enabled, *, profit_retain=None):
        if profit_retain is not None and (not isinstance(profit_retain,D) or not profit_retain.is_finite() or not 0<profit_retain<1):
            raise ValueError('invalid explicit profit-retention policy')
        self.profit_retain=profit_retain
        self.engine = engine
        self.enabled = tuple(s for s in STRATEGIES if s != CAS and s in enabled)
        from .seconds_engine import SecondsEngine
        self.seconds = SecondsEngine(self)
        self.inputs = None
        self.signals = {}
        self.last_reason = "INPUTS_NOT_RECEIVED"
        self.candidate_checks = []
        self.ranking={}
        self.ranked_at=None
        self.selection_blocked=False
        self.selection=engine.runtime.ledger.metadata("strategy-selection:"+engine.now().astimezone(IST).date().isoformat(),
            {"reason":"NO_EXECUTABLE_SIGNAL","mode":"WAITING","candidates":[]})

    def update(self, inputs):
        self.inputs = inputs
        # Persist first signal rather than repeatedly retrying a missed trade.
        # Recovery never reconstitutes an order from a stale signal.
        for strategy in self.enabled:
            if strategy in SECONDS_NAMES:
                continue  # Minute/cached samples cannot manufacture tick signals.
            sample = inputs.evaluations.get(strategy)
            if not sample or sample.state != "SIGNAL":
                continue
            key = self.signal_key(sample)
            if key in self.signals:
                continue
            ledger = self.engine.runtime.ledger
            previous = ledger.metadata(key)
            if previous and previous["evaluated_at"] != sample.evaluated_at.isoformat():
                continue
            if previous is None:
                ledger.put_metadata(key, asdict(sample))
            self.signals[key] = sample

    @staticmethod
    def signal_key(sample):
        if sample.strategy in SECONDS_NAMES:
            return f"directional-signal:{sample.evaluated_at.astimezone(IST).date()}:{sample.strategy}:{sample.details['episode']}"
        return f"directional-signal:{sample.evaluated_at.astimezone(IST).date()}:{sample.strategy}"

    @staticmethod
    def family_key(sample):
        if sample.strategy in SECONDS_NAMES:
            return f"directional-family:{sample.evaluated_at.astimezone(IST).date()}:{sample.strategy}:{sample.details['episode']}:consumed"
        from .expanded_strategies import SPECS
        family=SPECS.get(sample.strategy,(sample.strategy,))[0]
        return f"directional-family:{sample.evaluated_at.astimezone(IST).date()}:{family}:consumed"

    def input_ready(self):
        now, data = self.engine.now(), self.inputs
        return bool(data and not data.error and 0 <= (now-data.received_at).total_seconds() <= 90
                    and data.calendar and data.calendar.is_open(now))

    def book_current(self, book):
        return bool(book and self.engine.market_connected
                    and 0 <= self.engine.now().timestamp()*1e9-book.received_ns <= 2_000_000_000)

    def book_ready(self, book):
        return bool(self.book_current(book)
                    and book.top_ask and book.top_bid
                    and book.top_ask.price >= book.top_bid.price
                    and (book.top_ask.price-book.top_bid.price)/((book.top_ask.price+book.top_bid.price)/2) <= D(".08"))

    def candidate(self, signal, allocation):
        if signal.strategy in SECONDS_NAMES:
            return self.seconds.candidate(signal,allocation)
        data, engine = self.inputs, self.engine
        self.candidate_checks = []
        budget = min(allocation.remaining, allocation.spendable_cash, allocation.bankroll*D(".95"))
        if allocation.selected_cap_remaining is not None:
            budget = min(budget, allocation.selected_cap_remaining)
        # Determine ATM from the full known contract set, not only whichever
        # quotes happened to arrive. Missing nearby history cannot be skipped.
        instruments = getattr(engine, "instruments", {}) or {k:b.instrument for k,b in engine.books.items()}
        eligible = [i for i in instruments.values() if i.option_type.value == signal.side and i.expiry >= signal.minimum_expiry]
        if not eligible:
            return None
        expiry = min(i.expiry for i in eligible)
        eligible = sorted((i for i in eligible if i.expiry == expiry), key=lambda i:(abs(i.strike-signal.spot),i.strike,i.security_id))
        atm = eligible[0].strike
        side = 1 if signal.side == "CE" else -1
        eligible = sorted((i for i in eligible if side*(i.strike-atm)>=0), key=lambda i:(side*(i.strike-atm),i.security_id))[:4]
        for inst in eligible:
            check = {"security_id": inst.security_id, "strike": str(inst.strike), "budget": str(budget)}
            self.candidate_checks.append(check)
            try:
                bars = [data.option_bars[inst.security_id][signal.evaluated_at-timedelta(minutes=i)] for i in range(3)]
            except KeyError:
                self.last_reason = "OPTION_MINUTES_UNAVAILABLE"
                check["reason"] = self.last_reason
                return None
            check.update(minute_volume=min(b.volume for b in bars), open_interest=bars[0].oi, lot_size=inst.lot_size)
            if min(b.volume for b in bars)<inst.lot_size*20 or bars[0].oi<inst.lot_size*10:
                check["reason"] = "OPTION_LIQUIDITY_BELOW_POLICY"
                continue
            limit = (bars[0].close*D("1.05")/inst.tick_size).to_integral_value(rounding=ROUND_CEILING)*inst.tick_size
            if limit<=0 or (inst.lower_limit and limit<inst.lower_limit) or (inst.upper_limit and limit>inst.upper_limit):
                check["reason"] = "OPTION_LIMIT_OUTSIDE_BAND"
                continue
            minimum_cash = worst_case_entry_cash(inst.lot_size,limit) + FeeSchedule().sell(inst.lot_size*limit*2,3)
            check.update(limit=str(limit), one_lot_cash=str(minimum_cash))
            # Known unaffordability does not require a live book. An unusable
            # quote on a contract we cannot buy must not block a cheaper strike.
            if minimum_cash > budget:
                check["reason"] = "ONE_LOT_UNAFFORDABLE"
                continue
            book = engine.books.get(inst.security_id)
            if not self.book_ready(book):
                self.last_reason = "OPTION_BOOK_UNAVAILABLE_OR_STALE"
                check["reason"] = self.last_reason
                return None
            capacity = min(inst.freeze_qty, int(D(min(b.volume for b in bars))*D(".05")),
                           sum(level.quantity for level in book.asks if level.price<=limit))
            quantity = 0
            for q in range(inst.lot_size, capacity+1, inst.lot_size):
                debit = worst_case_entry_cash(q,limit)
                exit_reserve = FeeSchedule().sell(q*limit*2,3)
                if debit+exit_reserve<=budget:
                    quantity=q
                else:
                    break
            if quantity:
                check.update(reason="READY", quantity=quantity)
                return inst, quantity, limit, book
            # Affordability may select a farther OTM contract. A fixed limit
            # already below the market is a missed fill, not strike hopping.
            if book.top_ask.price>limit:
                self.last_reason = "FIXED_LIMIT_ALREADY_MISSED"
                check["reason"] = self.last_reason
                return None
            check["reason"] = "OPTION_DEPTH_BELOW_ONE_LOT"
        self.last_reason = "NO_AFFORDABLE_LIQUID_CONTRACT"
        return None

    def record_assessment(self, signal, reason, checks=None):
        ledger = self.engine.runtime.ledger
        key = self.signal_key(signal) + ":assessment"
        value = {"reason": reason, "candidate_checks": checks or []}
        # Store changes to the binding result, not every incoming quote.
        if ledger.metadata(key) != value:
            ledger.put_metadata(key, value)

    def refresh_ranking(self):
        from .strategy_arbiter import scores
        now=self.engine.now()
        if self.ranked_at is None or (now-self.ranked_at).total_seconds()>=5:
            self.ranking=scores(self.engine.runtime.ledger,now);self.ranked_at=now

    async def enter_locked(self, snapshot):
        engine, runtime = self.engine, self.engine.runtime
        ledger, now = runtime.ledger, engine.now()
        if self.selection_blocked or engine.active or snapshot["unresolved"] or ledger.pending_intents() or not (self.input_ready() or self.seconds.ready()):
            return False
        if any(int(r.get("netQty",r.get("netQuantity",0))) for r in snapshot["positions"]):
            self.last_reason="UNMANAGED_ACCOUNT_POSITION"
            return False
        from .strategy_arbiter import rank_signals, execution_score, select_executable
        self.refresh_ranking()
        allocation=None
        feasible=[]
        choices={}
        micro=self.seconds.signals() if any(n in SECONDS_NAMES for n in self.enabled) else []
        for signal in rank_signals([*self.signals.values(),*micro],ledger,now,ranking=self.ranking):
            if signal.strategy not in self.enabled:
                continue
            is_seconds=signal.strategy in SECONDS_NAMES
            if not (self.seconds.ready() if is_seconds else self.input_ready()):continue
            if signal.strategy not in runtime.enabled_strategies:
                self.last_reason='FUNDED_STRATEGY_DISABLED'
                self.record_assessment(signal,self.last_reason)
                continue
            key = self.signal_key(signal)+":consumed"
            if ledger.metadata(key) or ledger.metadata(self.family_key(signal)) or signal.evaluated_at.astimezone(IST).date() != now.astimezone(IST).date():
                continue
            due = signal.evaluated_at if is_seconds else signal.evaluated_at+timedelta(minutes=1)
            if now < due:
                continue
            if now >= due+timedelta(seconds=5 if is_seconds else 30):
                assessment = ledger.metadata(self.signal_key(signal)+":assessment", {})
                ledger.put_metadata(key,{"reason":"ENTRY_DEADLINE_MISSED",
                    "blocking_reason":assessment.get("reason", "UNKNOWN"),
                    "candidate_checks":assessment.get("candidate_checks", [])})
                self.last_reason="ENTRY_DEADLINE_MISSED"
                continue
            if signal.strategy == REBOUND and ledger.metadata("rebound-exited:"+now.astimezone(IST).date().isoformat()):
                ledger.put_metadata(key,{"reason":"PRIOR_REBOUND_EXITED_TODAY"})
                continue
            if not runtime.permit_entry(strategy=signal.strategy):
                self.last_reason="ENTRY_NOT_PERMITTED"
                self.record_assessment(signal, self.last_reason)
                return False
            if allocation is None:
                funds = await runtime.broker.funds()
                if funds.broker_account != runtime.mandate.account_id or not (self.seconds.ready() if is_seconds else self.input_ready()) or not runtime.permit_entry(strategy=signal.strategy):
                    return False
                allocation = engine._allocation(funds)
            candidate = self.candidate(signal,allocation)
            if candidate is None:
                self.record_assessment(signal, self.last_reason, self.candidate_checks)
                continue  # An unfillable engine cannot starve other valid signals.
            # Compare equal deadlines against the same decision clock. Sampling
            # after each candidate makes the last one look artificially faster.
            row=execution_score(signal,candidate,self.ranking,now)
            feasible.append(row)
            choices[signal.strategy]=(signal,candidate)
            self.record_assessment(signal,"READY",self.candidate_checks)
        if not feasible:
            # Preserve the last actual comparison for the session log/UI.
            return False
        chosen,mode,reason=select_executable(feasible)
        self.selection={"evaluated_at":engine.now().isoformat(),"mode":mode,"reason":reason,
                        "selected":chosen['strategy'] if chosen else None,"candidates":feasible}
        ledger.put_metadata("strategy-selection:"+now.astimezone(IST).date().isoformat(),self.selection)
        if chosen is None:
            self.last_reason=reason
            for row in feasible:self.record_assessment(choices[row['strategy']][0],reason)
            return False
        signal,candidate=choices[chosen['strategy']]
        inst, quantity, limit, book = candidate
        is_seconds=signal.strategy in SECONDS_NAMES
        due=signal.evaluated_at if is_seconds else signal.evaluated_at+timedelta(minutes=1)
        key=self.signal_key(signal)+":consumed"
        lifecycle = "l"+uuid.uuid4().hex
        payload = {"strategy":signal.strategy,"instrument":asdict(inst),"signal":asdict(signal),"exit_at":signal.exit_at,"selection":self.selection}
        if self.profit_retain is not None:
            payload['profit_exit']={'version':'NET_PROFIT_RATCHET_V1','retain':str(self.profit_retain)}
        intent = Intent("i"+uuid.uuid4().hex,"BUY",inst,quantity,limit,"e"+uuid.uuid4().hex[:28],engine.now(),lifecycle)
        with ledger.transaction() as db:
            db.execute("INSERT INTO lifecycles VALUES(?,?,?,?,?,?)",(lifecycle,engine.session_id,inst.security_id,str(allocation.bankroll),"OPEN",json.dumps(json_safe(payload))))
            db.execute("INSERT INTO metadata VALUES(?,?)",(key,json.dumps({"lifecycle":lifecycle,"reason":"DECISION_COMMITTED"})))
            db.execute("INSERT INTO metadata VALUES(?,?)",(self.family_key(signal),json.dumps({'lifecycle':lifecycle,'strategy':signal.strategy})))
        ledger.observe("decision:"+intent.intent_id,"ENTRY_DECISION",{"strategy":signal.strategy,"signal":asdict(signal),"book":asdict(book),"allocation":asdict(allocation),"quantity":quantity,"limit":limit,"selection":self.selection})
        def current():
            return (runtime.permit_entry(strategy=signal.strategy) and (self.seconds.valid(signal) if is_seconds else self.input_ready())
                    and self.book_ready(engine.books.get(inst.security_id))
                    and engine.books.get(inst.security_id) is book
                    and due <= engine.now() < due+timedelta(seconds=5 if is_seconds else 30))
        await runtime.orders.submit(intent,reserved_cash=reserve_cash(worst_case_entry_cash(quantity,limit)),pre_dispatch=current)
        runtime.status.state="ENTRY_PENDING"
        runtime.status.reason=self.last_reason=signal.strategy+":ENTRY_SUBMITTED"
        return True

    def compare_auction(self,candidate,quantity,allocation):
        """Auction and minute opportunities compete before either creates an intent."""
        from .strategy_arbiter import execution_score,select_executable
        engine=self.engine;now=engine.now();ledger=engine.runtime.ledger
        self.refresh_ranking()
        book=engine.books[candidate.instrument.security_id]
        signal=Evaluation(CAS,'SIGNAL','QUALIFIED_AUCTION',now,candidate.instrument.option_type.value,
            candidate.instrument.strike,candidate.instrument.expiry,now+timedelta(minutes=1))
        rows=[execution_score(signal,(candidate.instrument,quantity,candidate.limit_price,book),self.ranking,now)]
        if self.input_ready():
            for other in self.signals.values():
                due=other.evaluated_at+timedelta(minutes=1)
                if (other.strategy not in self.enabled or not due<=now<due+timedelta(seconds=30)
                        or ledger.metadata(self.signal_key(other)+':consumed') or ledger.metadata(self.family_key(other))
                        or not engine.runtime.permit_entry(strategy=other.strategy)):continue
                ready=self.candidate(other,allocation)
                if ready:rows.append(execution_score(other,ready,self.ranking,now))
        # A standalone auction continues using its separately qualified pricing
        # discrepancy. Historical mean outcomes are not its intrinsic-value gate.
        if len(rows)==1:
            chosen=rows[0];mode='QUALIFIED_AUCTION';reason='SELECTED'
        else:chosen,mode,reason=select_executable(rows)
        self.selection={'evaluated_at':now.isoformat(),'mode':mode,'reason':reason,
            'selected':chosen['strategy'] if chosen else None,'candidates':rows}
        ledger.put_metadata('strategy-selection:'+now.astimezone(IST).date().isoformat(),self.selection)
        self.selection_blocked=chosen is None
        return chosen is not None and chosen['strategy']==CAS

    async def manage_locked(self, active, snapshot):
        engine, runtime = self.engine, self.engine.runtime
        ledger, now = runtime.ledger, engine.now()
        payload = json.loads(active["payload"])
        owner = payload.get("strategy")
        if owner not in STRATEGIES or owner == CAS:
            runtime.status.state="RECOVERING"
            runtime.status.reason="UNKNOWN_POSITION_STRATEGY"
            return False
        inst = restore_instrument(payload["instrument"])
        totals = ledger.lifecycle_totals(active["lifecycle_id"])
        qty = sum(int(r.get("netQty",r.get("netQuantity",0))) for r in snapshot["positions"]
                  if str(r.get("securityId"))==inst.security_id and r.get("exchangeSegment","NSE_FNO")=="NSE_FNO" and r.get("productType","MARGIN")=="MARGIN")
        if snapshot["unresolved"] or totals["unresolved"] or ledger.pending_intents():
            runtime.status.state="RECONCILING_DIRECTIONAL_POSITION"
            return False
        if qty != totals["quantity"]:
            runtime.status.state="RECOVERING"
            runtime.status.reason="POSITION_RECONCILIATION_MISMATCH"
            return False
        if qty==0:
            await runtime.broker.funds()
            pnl=totals["sale_credit"]-totals["entry_debit"]
            with ledger.transaction() as db:
                db.execute("INSERT OR IGNORE INTO cash_postings VALUES(?,?,?,?,?)",(active["lifecycle_id"],active["lifecycle_id"],str(pnl),"CLOSED_PNL","{}"))
                db.execute("UPDATE lifecycles SET state='CLOSED' WHERE lifecycle_id=?",(active["lifecycle_id"],))
            if owner==REBOUND:
                ledger.put_metadata("rebound-exited:"+now.astimezone(IST).date().isoformat(),True)
            runtime.status.state="ARMED_WAITING_SIGNAL"
            runtime.status.reason=owner+(":POSITION_CLOSED" if totals['entry_debit'] else ":ENTRY_CANCELLED_NO_FILL")
            return False
        if now.astimezone(IST).date() > inst.expiry:
            runtime.status.state="SETTLEMENT_PENDING"
            runtime.status.reason="EXPIRED_POSITION_AWAITING_BROKER_CLEARING"
            return False
        key="directional-exit:"+active["lifecycle_id"]
        exit_state=ledger.metadata(key)
        exit_at=datetime.fromisoformat(payload["exit_at"])
        if now>=exit_at and exit_state is None:
            exit_state={"reason":"TIME_EXIT","due":exit_at.isoformat()}
        rows=(self.inputs.option_bars.get(inst.security_id,{}) if self.inputs else {})
        fills=list(ledger.db.execute("SELECT f.quantity,f.price FROM fills f JOIN intents i ON i.intent_id=f.intent_id WHERE i.lifecycle_id=? AND i.side='BUY'",(active["lifecycle_id"],)))
        units=sum(f["quantity"] for f in fills)
        entry=sum((D(f["price"])*f["quantity"] for f in fills),D(0))/units if units else None
        if owner in SECONDS_NAMES and exit_state is None and entry:
            book=engine.books.get(inst.security_id)
            if self.book_current(book):
                reason=self.seconds.exit_reason(payload,book,entry,now)
                if reason:
                    exit_state={'reason':reason,'due':now.isoformat()}
                    if reason=='SECONDS_INPUT_LOST':exit_state['input_health']=self.seconds.input_diagnostics(now)
        entry_time=datetime.fromisoformat(payload["signal"]["evaluated_at"])+timedelta(minutes=1)
        policy=payload["signal"].get("details",{})
        target=D(policy.get("exit_target") or '2') if policy.get("exit_target",'2') is not None else None
        stop=D(policy.get("exit_stop",'.5'))
        trailing=policy.get("exit_trail") is True
        peak=entry
        protection=payload.get('profit_exit')
        if exit_state is None and entry and protection:
            from .profit_exit import observe
            from .exits import executable_sale_units
            from math import ceil
            if protection.get('version')!='NET_PROFIT_RATCHET_V1':
                raise ValueError('unknown recorded profit-exit policy')
            book=engine.books.get(inst.security_id)
            if self.book_current(book) and book.top_bid:
                slices=executable_sale_units(book,qty)
                if sum(q for q,_ in slices)==qty:
                    # Finite depth, adverse two-tick allowance and conservative
                    # exit fees; never use LTP or multiply the top bid by all units.
                    proceeds=sum((q*max(inst.tick_size,p-2*inst.tick_size) for q,p in slices),D(0))
                    # Cash reserves cover failed/retried exits separately.
                    # A zero-fill IOC incurs no executed-order brokerage.
                    # Completed partial sales are already in sale_credit.
                    fees=FeeSchedule().sell(proceeds,ceil(qty/inst.freeze_qty))
                    net=totals['sale_credit']+proceeds-fees-totals['entry_debit']
                    cost=max(D(0),totals['entry_debit']-entry*units)+fees
                    guard_key='profit-exit:'+active['lifecycle_id']
                    old=ledger.metadata(guard_key)
                    guard=observe(net,cost,old,retain=D(protection['retain']))
                    # Persist a ratchet/trigger, not every declining quote.
                    if old is None or any(guard[k]!=old.get(k) for k in ('peak','floor','triggered')):
                        ledger.put_metadata(guard_key,guard)
                    if guard['triggered']:
                        exit_state={'reason':'NET_PROFIT_FLOOR','due':now.isoformat()}
        # Recovered bars can establish a missed exit, but never invent a fill
        # during the outage. The latch remains until a real reconciled sale.
        if entry and exit_state is None and owner not in SECONDS_NAMES:
            for t,bar in sorted(rows.items()):
                if not entry_time < t <= now:
                    continue
                if (target is not None and bar.close>=entry*target) or bar.close<=peak*stop:
                    exit_state={"reason":"PREMIUM_TARGET" if target is not None and bar.close>=entry*target else "TRAILING_STOP" if trailing else "PREMIUM_STOP", "due":(t+timedelta(minutes=1)).isoformat()}
                    break
                if trailing:peak=max(peak,bar.close)
        if exit_state:
            ledger.put_metadata(key,exit_state)
        runtime.status.state="POSITION_OPEN"
        runtime.status.reason=owner+":"+(exit_state["reason"] if exit_state else "HOLDING")
        if not exit_state or now < datetime.fromisoformat(exit_state["due"]):
            return False
        # Never send into a closed/unknown session or reuse a stale order book.
        if not self.inputs or not self.inputs.calendar or not self.inputs.calendar.is_open(now):
            runtime.status.reason="EXIT_LATCHED_WAITING_EXCHANGE_SESSION"
            return False
        book=engine.books.get(inst.security_id)
        if not self.book_current(book) or not book.top_bid:
            runtime.status.reason="EXIT_LATCHED_WAITING_CURRENT_BOOK"
            return False
        await engine.exit_manager.reduce(inst,qty,book,active["lifecycle_id"])
        runtime.status.state="EXIT_PENDING"
        return True

    def view(self):
        self.refresh_ranking()
        now=self.engine.now()
        result=[]
        for strategy in self.enabled or (GAP, REBOUND):
            is_seconds=strategy in SECONDS_NAMES
            if is_seconds:self.seconds.refresh()
            sample=self.seconds.evaluations.get(strategy) if is_seconds else self.inputs.evaluations.get(strategy) if self.inputs else None
            row=json_safe(asdict(sample)) if sample else {"strategy":strategy,"state":"UNKNOWN","reason":"INPUTS_NOT_RECEIVED"}
            row["enabled"]=strategy in self.enabled
            row['funded_enabled']=strategy in self.engine.runtime.enabled_strategies
            if strategy not in self.enabled:
                row.update(state="DISABLED",reason="NOT_CONFIGURED")
            elif not is_seconds and (not self.inputs or not 0 <= (now-self.inputs.received_at).total_seconds()<=90):
                row.update(state="UNKNOWN",reason="STRATEGY_INPUTS_STALE")
            elif not is_seconds and self.inputs.error:
                row.update(state="UNKNOWN",reason=self.inputs.error)
            key=f"directional-signal:{now.astimezone(IST).date()}:{strategy}"
            consumed=self.engine.runtime.ledger.metadata(key+':consumed',{})
            assessment=self.engine.runtime.ledger.metadata(key+':assessment',{})
            row['last_execution_reason']=consumed.get('reason') or assessment.get('reason')
            row['execution_blocking_reason']=consumed.get('blocking_reason') or assessment.get('reason')
            from .expanded_strategies import SPECS
            spec=SPECS.get(strategy)
            row['family']=spec[0] if spec else 'GAP_FADE' if strategy==GAP else 'NIFTY_SELLOFF_REBOUND'
            if is_seconds:row['family']=strategy;row['entry_rule']=SECONDS_RULES[strategy]
            row['exit_policy']=spec[1] if spec else 'DOUBLE'
            if is_seconds:row['exit_policy']='SECONDS_V1'
            row['scope']=spec[2] if spec else 'ORDINARY' if strategy==GAP else 'ANY'
            score=self.ranking.get(strategy,{})
            row['filled_closed']=score.get('filled_closed',0)
            row['ranking_available']=score.get('ranking_available',False)
            row['mean_estimated_net_return']=score.get('mean_estimated_net_return')
            result.append(row)
        return result
