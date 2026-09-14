from __future__ import annotations

import asyncio
from dataclasses import asdict, replace
from datetime import datetime, time, timezone
from decimal import Decimal
import json
import uuid
from zoneinfo import ZoneInfo

from .domain import CasPhase, CasStatus, ContractError, IndexObservation, Instrument, Level, OptionBook, OptionType, Segment, Intent, json_safe
from .exit_manager import ExitManager
from .risk import Allocation, FeeSchedule, reserve_cash, worst_case_entry_cash
from .runtime import AutoLive
from .strategy import Reference, find_opportunity, find_final_opportunity, select_reference, intrinsic

IST = ZoneInfo("Asia/Kolkata")
ZERO = Decimal("0")


def restore_instrument(value: dict) -> Instrument:
    from datetime import date
    return Instrument(value["security_id"], value["underlying"], Segment(value["segment"]), date.fromisoformat(value["expiry"]), OptionType(value["option_type"]), Decimal(value["strike"]), int(value["lot_size"]), Decimal(value["tick_size"]), int(value["freeze_qty"]), Decimal(value["lower_limit"]) if value.get("lower_limit") else None, Decimal(value["upper_limit"]) if value.get("upper_limit") else None)


class SessionEngine:
    """One serialized position lifecycle; feed callbacks only update its inputs."""
    def __init__(self, runtime: AutoLive, books: dict[str, OptionBook], *, now_fn=None):
        self.runtime, self.books = runtime, books
        self.now = now_fn or (lambda: datetime.now(timezone.utc))
        self.lock = asyncio.Lock()
        self.reference = None
        self.status = None
        self.observations = []
        self.reference_observations = []
        self.streaks = {}
        self.identities = set()
        self.signal_epoch = None
        self.market_epoch = None
        self.signal_connected = True
        self.market_connected = True
        self.exit_reason = ""
        self.peak_intrinsic = ZERO
        self.peak_bid = ZERO
        self.final_value = None
        self.last_signal_timestamp = -1
        self.exit_manager = ExitManager(runtime.ledger, runtime.broker)
        self.session_id = self.now().astimezone(IST).date().isoformat()
        row = runtime.ledger.db.execute("SELECT payload FROM references_frozen WHERE session_id=?", (self.session_id,)).fetchone()
        if row:
            raw = json.loads(row[0])
            self.reference = Reference(Decimal(raw["value"]), raw["boundary_ms"], tuple(raw["event_ids"]), raw["epoch"])
        active = self.active
        final = runtime.ledger.metadata("final:"+(active["session_id"] if active else self.session_id))
        if final:
            from .settlement import FinalValue
            final["value"]=Decimal(final["value"])
            self.final_value=FinalValue(**final)
            self.final_value.validate()
            runtime.status.final_value_source_verified=True

    def on_final(self, final):
        final.validate()
        active = self.active
        historical = active and final.trading_date == active["session_id"] and final.trading_date < self.session_id
        if final.trading_date != self.session_id and not historical:
            raise ContractError("final value is for another session")
        if not historical and (not self.status or self.status.phase != CasPhase.CAS_STOP):
            raise ContractError("final input cannot precede collection stop")
        published = datetime.fromisoformat(final.published_at.replace("Z","+00:00"))
        received = datetime.fromisoformat(final.received_at.replace("Z","+00:00"))
        if (not historical and published.timestamp()*1000 < self.status.updated_time_ms) or received > self.now():
            raise ContractError("final input time is inconsistent with session")
        if self.final_value and self.final_value.value != final.value:
            self.runtime.status.auto_live_armed = False
            self.exit_reason = "FINAL_VALUE_REVISED"
            self.runtime.ledger.put_metadata("disarmed", True)
        self.final_value = final
        self.runtime.status.final_value_source_verified = True
        self.runtime.ledger.put_metadata("final:"+final.trading_date,asdict(final))

    @property
    def active(self):
        rows = list(self.runtime.ledger.db.execute("SELECT * FROM lifecycles WHERE state!='CLOSED'"))
        if len(rows) > 1:
            raise ContractError("multiple unresolved lifecycles")
        return rows[0] if rows else None

    def signal_reconnect(self, epoch: str | None) -> None:
        self.signal_epoch = epoch
        self.signal_connected = epoch is not None
        self.status = None
        self.observations.clear()
        self.streaks.clear()
        self.identities.clear()
        self.reference_observations.clear()
        self.last_signal_timestamp = -1
        self.runtime.status.official_cas_signal_seen = False

    def market_reconnect(self, epoch: str | None) -> None:
        self.market_epoch = epoch
        self.market_connected = epoch is not None
        self.books.clear()

    def on_status(self, status: CasStatus, *, clock_uncertainty_ms: int = 0) -> None:
        if self.status and status.epoch == self.status.epoch and status.updated_time_ms < self.status.updated_time_ms:
            return
        self.status = status
        self.signal_epoch = status.epoch
        if status.phase is CasPhase.CTS_CLOSE and self.reference is None:
            self.reference = select_reference(self.reference_observations, status, clock_uncertainty_ms)
            self.runtime.ledger.freeze_reference(status.trading_date.isoformat(), self.reference)
        self.runtime.status.official_cas_signal_seen = status.phase is not CasPhase.UNKNOWN

    def on_ltp(self, observation: IndexObservation) -> None:
        if self.reference is None:
            self.reference_observations.append(observation)
            self.reference_observations = self.reference_observations[-2000:]

    async def on_iep(self, observation: IndexObservation, *, dispatch: bool = True) -> bool:
        if self.reference is None or self.status is None or observation.epoch != self.status.epoch or not observation.wrapper_present:
            return False
        if observation.provider_ts_ms < max(self.last_signal_timestamp, self.status.updated_time_ms):
            return False
        self.last_signal_timestamp = observation.provider_ts_ms
        identity = observation.raw_identity or f"{observation.epoch}:{observation.provider_ts_ms}:{observation.value}"
        if identity in self.identities:
            return False
        self.identities.add(identity)
        if len(self.identities) > 10000:
            self.identities = {key for _, key in self.observations}
            self.identities.add(identity)
        self.observations.append((observation.value, identity))
        self.observations = self.observations[-24:]
        direction = OptionType.CE if observation.value > self.reference.value else OptionType.PE if observation.value < self.reference.value else None
        qualifying = {}
        for security, book in self.books.items():
            inst = book.instrument
            bid, ask = book.top_bid, book.top_ask
            value = intrinsic(inst.option_type, inst.strike, observation.value)
            if inst.option_type == direction and bid and ask and min(bid.quantity, ask.quantity) >= inst.lot_size and ask.price + inst.tick_size <= value:
                qualifying[security] = (self.streaks.get(security, []) + [(observation.value, identity)])[-24:]
        self.streaks = qualifying
        self.runtime.ledger.observe(identity, "IEP", asdict(observation))
        return await self.cycle() if dispatch else False

    def on_book(self, book: OptionBook) -> None:
        if self.market_epoch is not None and book.epoch != self.market_epoch:
            return
        self.books[book.instrument.security_id] = book

    def _allocation(self, funds, active=None):
        ledger, mandate = self.runtime.ledger, self.runtime.mandate
        totals = ledger.lifecycle_totals(active["lifecycle_id"]) if active else {"entry_debit": ZERO, "reserved": ZERO}
        # Later fee corrections must reduce reusable profit, even after close.
        pnl = ZERO
        for row in ledger.db.execute("SELECT lifecycle_id FROM lifecycles WHERE state='CLOSED'"):
            closed = ledger.lifecycle_totals(row[0])
            pnl += closed["sale_credit"] - closed["entry_debit"]
        allocation = mandate.allocated_capital + (pnl if mandate.reinvest_realized_profit else min(ZERO, pnl))
        probe_debit = ledger.lifecycle_totals("route-probe")["entry_debit"] - ledger.lifecycle_totals("route-probe")["sale_credit"]
        bankroll = Decimal(active["bankroll"]) if active else max(ZERO, min(allocation-probe_debit, funds.spendable_cash))
        cap_remaining = None
        if mandate.cumulative_entry_debit_cap is not None:
            debit = ZERO
            for row in ledger.db.execute("SELECT * FROM lifecycles"):
                if mandate.debit_cap_scope == "mandate" or row["session_id"] == self.session_id:
                    spent = ledger.lifecycle_totals(row["lifecycle_id"])
                    debit += spent["entry_debit"] + spent["reserved"]
            cap_remaining = max(ZERO, mandate.cumulative_entry_debit_cap-debit)
        return Allocation.start(bankroll, funds.spendable_cash, totals["entry_debit"], totals["reserved"], cap_remaining)

    async def cycle(self, *, reconcile: bool = True) -> bool:
        async with self.lock:
            ledger, runtime = self.runtime.ledger, self.runtime
            if reconcile:
                runtime.reconciled = await runtime.orders.reconcile()
            snapshot = getattr(runtime, "reconciled", None)
            if snapshot is None:
                return False
            active = self.active
            local_now = self.now().astimezone(IST)
            positions = snapshot["positions"]
            if active:
                inst = restore_instrument(json.loads(active["payload"])["instrument"])
                totals = ledger.lifecycle_totals(active["lifecycle_id"])
                broker_qty = sum(int(row.get("netQty", row.get("netQuantity", 0))) for row in positions if str(row.get("securityId")) == inst.security_id and row.get("exchangeSegment", "NSE_FNO") == "NSE_FNO" and row.get("productType", "MARGIN") == "MARGIN")
                if snapshot["unresolved"] or totals["unresolved"] or ledger.pending_intents():
                    runtime.status.state = "EXIT_PENDING" if self.exit_reason else "ENTRY_PENDING"
                    return False
                expired = local_now.date() > inst.expiry or (local_now.date()==inst.expiry and local_now.time()>=time(15,40))
                if broker_qty==0 and totals["quantity"] and expired:
                    runtime.status.state="SETTLEMENT_PENDING"
                    runtime.status.reason="SETTLEMENT_CASH_NOT_YET_MATCHED"
                    if self.final_value and self.final_value.trading_date==active["session_id"]:
                        gross=intrinsic(inst.option_type,inst.strike,self.final_value.value)*totals["quantity"]
                        receipt = None
                        if gross==0:
                            receipt=("OTM:"+active["lifecycle_id"],ZERO,{"final":asdict(self.final_value),"broker_positions":positions})
                        elif hasattr(runtime.broker,"ledger_report"):
                            from .settlement_cash import match_settlement
                            rows=await runtime.broker.ledger_report(inst.expiry,local_now.date())
                            receipt=match_settlement(rows,account=runtime.mandate.account_id,instrument=inst,final=self.final_value,quantity=totals["quantity"])
                        if receipt:
                            await runtime.broker.funds()
                            with ledger.transaction() as db:
                                db.execute("INSERT OR IGNORE INTO settlements VALUES(?,?,?,?,?)",(receipt[0],active["lifecycle_id"],totals["quantity"],str(receipt[1]),json.dumps(json_safe(receipt[2]))))
                            totals=ledger.lifecycle_totals(active["lifecycle_id"])
                    if totals["quantity"]:
                        return False
                if broker_qty != totals["quantity"]:
                    runtime.status.reason = "POSITION_RECONCILIATION_MISMATCH"
                    runtime.status.state = "RECOVERING"
                    return False
                if totals["quantity"] == 0:
                    await runtime.broker.funds()  # cash snapshot follows terminal position reconciliation
                    pnl = totals["sale_credit"] - totals["entry_debit"]
                    with ledger.transaction() as db:
                        db.execute("INSERT OR IGNORE INTO cash_postings VALUES(?,?,?,?,?)", (active["lifecycle_id"], active["lifecycle_id"], str(pnl), "CLOSED_PNL", "{}"))
                        db.execute("UPDATE lifecycles SET state='CLOSED' WHERE lifecycle_id=?", (active["lifecycle_id"],))
                    self.exit_reason = ""
                    self.peak_intrinsic = self.peak_bid = ZERO
                    runtime.status.state = "ARMED_WAITING_SIGNAL"
                    active = None
                else:
                    book = self.books.get(inst.security_id)
                    if self.final_value and self.final_value.trading_date == active["session_id"]:
                        target = intrinsic(inst.option_type,inst.strike,self.final_value.value)
                        from .exits import executable_sale_units
                        ladder = executable_sale_units(book,totals["quantity"]) if book else []
                        child = inst.freeze_qty//inst.lot_size*inst.lot_size
                        # Compare each supported sale slice to exercise of the
                        # same quantity, not to exercise of the entire holding.
                        sale_units = 0
                        supported = 0
                        sale_cash = ZERO
                        for level_qty, level_price in ladder:
                            supported += level_qty
                            sale_cash += level_qty*level_price
                            units = supported//inst.lot_size*inst.lot_size
                            if not units:
                                continue
                            finite_cash = sale_cash - (supported-units)*level_price
                            children = (units+child-1)//child
                            net_sale = finite_cash - FeeSchedule().sell(finite_cash,children)
                            same_exercise = target*units - FeeSchedule().sell(target*units,children)
                            if net_sale >= same_exercise:
                                sale_units = units
                        exercise_cash = target*totals["quantity"] - FeeSchedule().sell(target*totals["quantity"],(totals["quantity"]+child-1)//child)
                        if exercise_cash > ZERO and not sale_units and not self.exit_reason:
                            runtime.status.state = "SETTLEMENT_PENDING"
                            runtime.status.reason = "CONFIRMED_FINAL_EXERCISE_VALUE_EXCEEDS_FINITE_SALE"
                            ledger.put_metadata("settlement_pending:"+active["lifecycle_id"],{"quantity":totals["quantity"],"expected_credit":str(exercise_cash),"final":asdict(self.final_value)})
                            return await self._enter(snapshot, active, positions, local_now, settlement_add=True)
                        if book and sale_units and not self.exit_reason:
                            await self.exit_manager.reduce(inst,min(sale_units,totals["quantity"]),book,active["lifecycle_id"])
                            runtime.status.state = "EXIT_PENDING"
                            return True
                    reason = self.exit_reason
                    stored = ledger.metadata("peaks:"+active["lifecycle_id"], {})
                    self.peak_bid = max(self.peak_bid, Decimal(stored.get("bid","0")))
                    self.peak_intrinsic = max(self.peak_intrinsic, Decimal(stored.get("intrinsic","0")))
                    reason = reason or stored.get("exit", "")
                    if book is None:
                        reason = reason or "OPTION_BOOK_UNAVAILABLE"
                    if active["session_id"] != self.session_id or not self.signal_connected or not self.market_connected or not self.reference:
                        reason = reason or "RECOVERY_OR_SIGNAL_UNAVAILABLE"
                    if local_now.time() >= time(15, 39):
                        reason = reason or "TIME_EXIT"
                    if self.status and self.status.phase is CasPhase.CAS_STOP and not self.final_value:
                        reason = reason or "COLLECTION_STOPPED_NO_FINAL_INPUT"
                    if self.status is None or self.status.phase is CasPhase.UNKNOWN:
                        reason = reason or "SIGNAL_UNAVAILABLE"
                    if self.observations and self.reference and book:
                        index = self.observations[-1][0]
                        current = intrinsic(inst.option_type, inst.strike, index)
                        bid = book.top_bid.price if book.top_bid else ZERO
                        self.peak_intrinsic = max(self.peak_intrinsic, current)
                        self.peak_bid = max(self.peak_bid, bid)
                        cost_floor = max(inst.tick_size, FeeSchedule().sell(bid * inst.lot_size, 1) / inst.lot_size)
                        direction = OptionType.CE if index > self.reference.value else OptionType.PE if index < self.reference.value else None
                        if direction != inst.option_type:
                            reason = reason or "DIRECTION_REVERSAL"
                        elif len(self.streaks.get(inst.security_id, [])) < 2:
                            reason = reason or "CONTRACT_LAG_INVALIDATED"
                        elif book.top_ask is None or current - book.top_ask.price <= cost_floor:
                            reason = reason or "LAG_CONVERGED"
                        elif current + inst.tick_size < self.peak_intrinsic and bid + inst.tick_size < self.peak_bid:
                            reason = reason or "JOINT_REVERSAL"
                    peak_state = {"bid":str(self.peak_bid),"intrinsic":str(self.peak_intrinsic),"exit":reason}
                    if peak_state != stored:
                        ledger.put_metadata("peaks:"+active["lifecycle_id"],peak_state)
                    if reason:
                        self.exit_reason = reason
                        runtime.status.reason = reason
                        if book is None:
                            book = OptionBook(inst, (), (), self.market_epoch or "recovery", int(self.now().timestamp()*1e9))
                        await self.exit_manager.reduce(inst, totals["quantity"], book, active["lifecycle_id"], emergency=reason in {"TIME_EXIT", "RECOVERY_OR_SIGNAL_UNAVAILABLE", "SIGNAL_UNAVAILABLE", "OPTION_BOOK_UNAVAILABLE"} or book.top_bid is None)
                        runtime.status.state = "EXIT_PENDING"
                        return True
                    runtime.status.state = "POSITION_OPEN"
            return await self._enter(snapshot, active, positions, local_now)

    async def _enter(self, snapshot, active, positions, local_now, *, settlement_add=False):
        ledger, runtime = self.runtime.ledger, self.runtime
        if snapshot["unresolved"] or ledger.pending_intents() or not runtime.permit_entry(settlement_add=settlement_add):
            return False
        if any(int(row.get("netQty", row.get("netQuantity", 0))) and (active is None or str(row.get("securityId")) != active["security_id"]) for row in positions):
            runtime.status.reason = "UNMANAGED_ACCOUNT_POSITION"
            return False
        final_entry = self.final_value is not None and self.status is not None and self.status.phase is CasPhase.CAS_STOP
        if local_now.date().isoformat() != self.session_id or not time(15, 20) <= local_now.time() < (time(15,38,30) if final_entry else time(15,30)):
            return False
        if not self.market_connected or not self.status or self.status.trading_date != local_now.date() or (not final_entry and (not self.signal_connected or self.status.phase not in {CasPhase.CAS_LM_START, CasPhase.CAS_M_STOP})):
            return False
        funds = await runtime.broker.funds()
        runtime.status.current_account_funded = funds.spendable_cash > 0 and funds.broker_account == runtime.mandate.account_id
        allocation = self._allocation(funds, active)
        choices = []
        for security in (self.books if final_entry else self.streaks):
            history = self.streaks.get(security,[])
            book = self.books.get(security)
            if book is None or book.instrument.expiry != local_now.date() or (active and security != active["security_id"]):
                continue
            book_id = f"{book.epoch}:{security}:{book.received_ns}"
            used = ledger.db.execute("SELECT COALESCE(SUM(quantity),0) FROM depth_debits WHERE identity=?", (book_id,)).fetchone()[0]
            asks = []
            for level in book.asks:
                taken = min(used, level.quantity)
                used -= taken
                if level.quantity > taken:
                    asks.append(Level(level.price,level.quantity-taken))
            book = replace(book,asks=tuple(asks))
            candidate = find_final_opportunity(self.final_value,[book],allocation) if final_entry else find_opportunity(self.reference, history, [book], allocation)
            if candidate:
                choices.append((candidate, book_id))
        if not choices:
            runtime.status.reason = "NO_EXECUTABLE_LAG_OR_REMAINING_ALLOWANCE"
            return False
        candidate, book_id = max(choices, key=lambda item: (item[0].score, -int(item[0].instrument.security_id), -item[0].limit_price))
        if not runtime.permit_entry(settlement_add=settlement_add):
            return False
        lifecycle_id = active["lifecycle_id"] if active else "l"+uuid.uuid4().hex
        quantity = min(candidate.quantity, candidate.instrument.freeze_qty // candidate.instrument.lot_size * candidate.instrument.lot_size)
        intent = Intent("i"+uuid.uuid4().hex, "BUY", candidate.instrument, quantity, candidate.limit_price, "e"+uuid.uuid4().hex[:28], self.now(), lifecycle_id)
        ledger.observe("decision:"+intent.intent_id,"ENTRY_DECISION", {"reference":asdict(self.reference) if self.reference else None,"final":asdict(self.final_value) if final_entry else None,"history":self.streaks.get(candidate.instrument.security_id,[]),"book":asdict(self.books[candidate.instrument.security_id]),"allocation":asdict(allocation),"quantity":quantity,"limit":candidate.limit_price})
        with ledger.transaction() as db:
            if active is None:
                db.execute("INSERT INTO lifecycles VALUES(?,?,?,?,?,?)", (lifecycle_id, self.session_id, candidate.instrument.security_id, str(allocation.bankroll), "OPEN", json.dumps(json_safe({"instrument": asdict(candidate.instrument)}))))
            db.execute("INSERT OR IGNORE INTO consumed_books VALUES(?,?)", (book_id, lifecycle_id))
            db.execute("INSERT INTO depth_debits VALUES(?,?,?)", (book_id,intent.intent_id,quantity))
        signal_identity = self.observations[-1] if self.observations else None
        status_identity = self.status
        def current_inputs():
            current_book = self.books.get(candidate.instrument.security_id)
            return (runtime.permit_entry(settlement_add=settlement_add) and self.market_connected and self.status == status_identity
                    and (self.observations[-1] if self.observations else None) == signal_identity
                    and current_book is not None and f"{current_book.epoch}:{candidate.instrument.security_id}:{current_book.received_ns}" == book_id
                    and self.now().astimezone(IST).time() < (time(15,38,30) if final_entry else time(15,30)))
        await runtime.orders.submit(intent, reserved_cash=reserve_cash(worst_case_entry_cash(quantity, candidate.limit_price)), pre_dispatch=current_inputs)
        runtime.status.state = "ENTRY_PENDING"
        runtime.status.reason = candidate.reason
        return True
