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
from .session_strategies import CAS, GAP, REBOUND, IST, Calendar, Evaluation

D = Decimal


@dataclass(frozen=True)
class Inputs:
    calendar: Calendar | None
    evaluations: dict
    option_bars: dict
    received_at: datetime
    error: str = ""


class DirectionalEngine:
    def __init__(self, engine, enabled):
        self.engine = engine
        self.enabled = tuple(s for s in (GAP, REBOUND) if s in enabled)
        self.inputs = None
        self.signals = {}
        self.last_reason = "INPUTS_NOT_RECEIVED"

    def update(self, inputs):
        self.inputs = inputs
        # Persist first signal rather than repeatedly retrying a missed trade.
        # Recovery never reconstitutes an order from a stale signal.
        for strategy in self.enabled:
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
        return f"directional-signal:{sample.evaluated_at.astimezone(IST).date()}:{sample.strategy}"

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
        data, engine = self.inputs, self.engine
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
            try:
                bars = [data.option_bars[inst.security_id][signal.evaluated_at-timedelta(minutes=i)] for i in range(3)]
            except KeyError:
                self.last_reason = "OPTION_MINUTES_UNAVAILABLE"
                return None
            if min(b.volume for b in bars)<inst.lot_size*20 or bars[0].oi<inst.lot_size*10:
                continue
            limit = (bars[0].close*D("1.05")/inst.tick_size).to_integral_value(rounding=ROUND_CEILING)*inst.tick_size
            if limit<=0 or (inst.lower_limit and limit<inst.lower_limit) or (inst.upper_limit and limit>inst.upper_limit):
                continue
            book = engine.books.get(inst.security_id)
            if not self.book_ready(book):
                self.last_reason = "OPTION_BOOK_UNAVAILABLE_OR_STALE"
                return None
            capacity = min(inst.freeze_qty, int(D(min(b.volume for b in bars))*D(".05")),
                           sum(level.quantity for level in book.asks if level.price<=limit))
            budget = min(allocation.remaining, allocation.spendable_cash, allocation.bankroll*D(".95"))
            if allocation.selected_cap_remaining is not None:
                budget = min(budget, allocation.selected_cap_remaining)
            quantity = 0
            for q in range(inst.lot_size, capacity+1, inst.lot_size):
                debit = worst_case_entry_cash(q,limit)
                exit_reserve = FeeSchedule().sell(q*limit*2,3)
                if debit+exit_reserve<=budget:
                    quantity=q
                else:
                    break
            if quantity:
                return inst, quantity, limit, book
            # Affordability may select a farther OTM contract. A fixed limit
            # already below the market is a missed fill, not strike hopping.
            if book.top_ask.price>limit:
                self.last_reason = "FIXED_LIMIT_ALREADY_MISSED"
                return None
        self.last_reason = "NO_AFFORDABLE_LIQUID_CONTRACT"
        return None

    async def enter_locked(self, snapshot):
        engine, runtime = self.engine, self.engine.runtime
        ledger, now = runtime.ledger, engine.now()
        if engine.active or snapshot["unresolved"] or ledger.pending_intents() or not self.input_ready():
            return False
        if any(int(r.get("netQty",r.get("netQuantity",0))) for r in snapshot["positions"]):
            self.last_reason="UNMANAGED_ACCOUNT_POSITION"
            return False
        for signal in sorted(self.signals.values(), key=lambda s:(s.evaluated_at,s.strategy)):
            if signal.strategy not in self.enabled:
                continue
            key = self.signal_key(signal)+":consumed"
            if ledger.metadata(key) or signal.evaluated_at.astimezone(IST).date() != now.astimezone(IST).date():
                continue
            due = signal.evaluated_at+timedelta(minutes=1)
            if now < due:
                continue
            if now >= due+timedelta(seconds=30):
                ledger.put_metadata(key,{"reason":"ENTRY_DEADLINE_MISSED"})
                self.last_reason="ENTRY_DEADLINE_MISSED"
                continue
            if signal.strategy == REBOUND and ledger.metadata("rebound-exited:"+now.astimezone(IST).date().isoformat()):
                ledger.put_metadata(key,{"reason":"PRIOR_REBOUND_EXITED_TODAY"})
                continue
            if not runtime.permit_entry(strategy=signal.strategy):
                self.last_reason="ENTRY_NOT_PERMITTED"
                return False
            funds = await runtime.broker.funds()
            if funds.broker_account != runtime.mandate.account_id or not self.input_ready() or not runtime.permit_entry(strategy=signal.strategy):
                return False
            allocation = engine._allocation(funds)
            candidate = self.candidate(signal,allocation)
            if candidate is None:
                return False  # bounded retry for data arrival, never after send
            inst, quantity, limit, book = candidate
            lifecycle = "l"+uuid.uuid4().hex
            payload = {"strategy":signal.strategy,"instrument":asdict(inst),"signal":asdict(signal),"exit_at":signal.exit_at}
            intent = Intent("i"+uuid.uuid4().hex,"BUY",inst,quantity,limit,"e"+uuid.uuid4().hex[:28],engine.now(),lifecycle)
            with ledger.transaction() as db:
                db.execute("INSERT INTO lifecycles VALUES(?,?,?,?,?,?)",(lifecycle,engine.session_id,inst.security_id,str(allocation.bankroll),"OPEN",json.dumps(json_safe(payload))))
                db.execute("INSERT INTO metadata VALUES(?,?)",(key,json.dumps({"lifecycle":lifecycle,"reason":"DECISION_COMMITTED"})))
            ledger.observe("decision:"+intent.intent_id,"ENTRY_DECISION",{"strategy":signal.strategy,"signal":asdict(signal),"book":asdict(book),"allocation":asdict(allocation),"quantity":quantity,"limit":limit})
            def current():
                return (runtime.permit_entry(strategy=signal.strategy) and self.input_ready()
                        and self.book_ready(engine.books.get(inst.security_id))
                        and engine.books.get(inst.security_id) is book
                        and due <= engine.now() < due+timedelta(seconds=30))
            await runtime.orders.submit(intent,reserved_cash=reserve_cash(worst_case_entry_cash(quantity,limit)),pre_dispatch=current)
            runtime.status.state="ENTRY_PENDING"
            runtime.status.reason=self.last_reason=signal.strategy+":ENTRY_SUBMITTED"
            return True
        return False

    async def manage_locked(self, active, snapshot):
        engine, runtime = self.engine, self.engine.runtime
        ledger, now = runtime.ledger, engine.now()
        payload = json.loads(active["payload"])
        owner = payload.get("strategy")
        if owner not in (GAP, REBOUND):
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
        entry_time=datetime.fromisoformat(payload["signal"]["evaluated_at"])+timedelta(minutes=1)
        # Recovered bars can establish a missed exit, but never invent a fill
        # during the outage. The latch remains until a real reconciled sale.
        if entry and exit_state is None:
            for t,bar in sorted(rows.items()):
                if not entry_time < t <= now:
                    continue
                if bar.close>=entry*2 or bar.close<=entry/2:
                    exit_state={"reason":"DOUBLE_TARGET" if bar.close>=entry*2 else "HALF_PREMIUM_STOP", "due":(t+timedelta(minutes=1)).isoformat()}
                    break
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
        now=self.engine.now()
        result=[]
        for strategy in (GAP, REBOUND):
            sample=self.inputs.evaluations.get(strategy) if self.inputs else None
            row=json_safe(asdict(sample)) if sample else {"strategy":strategy,"state":"UNKNOWN","reason":"INPUTS_NOT_RECEIVED"}
            row["enabled"]=strategy in self.enabled
            if strategy not in self.enabled:
                row.update(state="DISABLED",reason="NOT_CONFIGURED")
            elif not self.inputs or not 0 <= (now-self.inputs.received_at).total_seconds()<=90:
                row.update(state="UNKNOWN",reason="STRATEGY_INPUTS_STALE")
            elif self.inputs.error:
                row.update(state="UNKNOWN",reason=self.inputs.error)
            row["last_execution_reason"]=self.last_reason
            result.append(row)
        return result
