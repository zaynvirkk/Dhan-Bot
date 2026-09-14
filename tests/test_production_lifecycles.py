"""Connected strategy -> production OMS -> fills/positions/cash -> next lifecycle."""
import asyncio
from dataclasses import replace
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from dhan_cas_bot.domain import CasPhase, CasStatus, ContractError, FundsSnapshot, IndexObservation, Instrument, Level, OptionBook, OptionType, Segment
from dhan_cas_bot.engine import SessionEngine
from dhan_cas_bot.ledger import Ledger
from dhan_cas_bot.risk import FeeSchedule, ceil_paise, lifecycle_ceiling
from dhan_cas_bot.runtime import AutoLive
from dhan_cas_bot.strategy import Reference
from tests.acceptance.cas.support import mandate

D = Decimal
DAY = date(2026, 9, 15)
NOW = datetime(2026,9,15,9,51,tzinfo=timezone.utc)


class MatchingBroker:
    account_id = "TEST"
    def __init__(self, ledger):
        self.ledger = ledger
        self.cash = D("9411.18")
        self.requests, self.order_rows, self.trade_rows = [], [], []
        self.quantities = {}
        self.next_fill = None
        self.lose_response = False
        self.accepted = None

    async def submit_order(self, request):
        # Assert durability at the actual transport boundary, before acceptance.
        saved = self.ledger.db.execute("SELECT * FROM intents WHERE client_order_id=?", (request["correlationId"],)).fetchone()
        assert saved is not None and saved["state"] == "SEND_UNKNOWN"
        assert self.ledger.db.execute("SELECT response_state FROM attempts WHERE intent_id=?", (saved["intent_id"],)).fetchone()[0] == "STARTED"
        assert len(request["correlationId"]) <= 30
        assert (request["orderType"], request["validity"], request["productType"], request["exchangeSegment"]) == ("LIMIT","IOC","MARGIN","NSE_FNO")
        self.requests.append(dict(request))
        quantity = request["quantity"] if self.next_fill is None else min(self.next_fill, request["quantity"])
        self.next_fill = None
        order_id = f"O{len(self.requests)}"
        row = {**request, "orderId": order_id, "orderStatus": "TRADED" if quantity == request["quantity"] else "CANCELLED", "filledQty": quantity}
        self.order_rows.append(row)
        if quantity:
            price = D(request["price"])
            fees = ceil_paise((FeeSchedule().buy if request["transactionType"] == "BUY" else FeeSchedule().sell)(price*quantity,1))
            signed = quantity if request["transactionType"] == "BUY" else -quantity
            self.quantities[request["securityId"]] = self.quantities.get(request["securityId"],0) + signed
            assert self.quantities[request["securityId"]] >= 0
            self.cash -= signed*price + fees
            self.trade_rows.append({**request,"orderId":order_id,"exchangeTradeId":f"T{len(self.trade_rows)}","tradedQuantity":quantity,"tradedPrice":str(price),"fees":str(fees)})
        if self.accepted:
            await self.accepted(row)
        if self.lose_response:
            self.lose_response = False
            raise TimeoutError("accepted but response lost")
        return {"orderId":order_id,"orderStatus":row["orderStatus"]}
    async def orders(self): return list(self.order_rows)
    async def trades(self): return list(self.trade_rows)
    async def positions(self): return [{"securityId":security,"netQty":qty,"exchangeSegment":"NSE_FNO","productType":"MARGIN"} for security,qty in self.quantities.items() if qty]
    async def funds(self): return FundsSnapshot(NOW,self.cash,self.cash,self.cash,D(0),self.account_id)
    async def order(self, identity): return next((row for row in self.order_rows if row["orderId"]==identity),None)


def setup(tmp_path):
    ledger = Ledger(tmp_path / "ledger.sqlite3")
    broker = MatchingBroker(ledger)
    runtime = AutoLive(ledger,broker,mandate(live=True),software_verified=True)
    runtime.status.current_account_funded = runtime.status.broker_route_verified = runtime.status.official_cas_signal_seen = True
    clock = [NOW]
    engine = SessionEngine(runtime,{},now_fn=lambda:clock[0])
    engine.reference = Reference(D("25000"),int(NOW.timestamp()*1000)-360000,("a","b","c","d","e"),"u1")
    ledger.freeze_reference(DAY.isoformat(),engine.reference)
    engine.on_status(CasStatus(CasPhase.CAS_LM_START,int(NOW.timestamp()*1000)-60000,DAY,"u1"))
    return engine, broker, ledger, clock


def book(side, seq, ask="10", bid="9", quantity=195):
    inst = Instrument("100" if side=="CE" else "200","NIFTY",Segment.NSE_FNO,DAY,OptionType(side),D("25000"),65,D("0.05"),1800)
    return OptionBook(inst,(Level(D(bid),quantity),) if D(bid)>0 else (), (Level(D(ask),quantity),),"d1",int(NOW.timestamp()*1e9)+seq)


def obs(value,seq,epoch="u1"):
    return IndexObservation(D(value),int(NOW.timestamp()*1000)+seq,int(NOW.timestamp()*1e9)+seq,epoch,seq,raw_identity=f"{epoch}-{seq}")


def test_up_down_up_executes_real_buy_sell_lifecycles_and_compounds(tmp_path):
    async def run():
        engine, broker, ledger, _ = setup(tmp_path)
        engine.on_book(book("CE",1))
        engine.on_book(book("PE",1))
        assert not await engine.on_iep(obs("25100",1))
        assert await engine.on_iep(obs("25100",2))  # distinct events, same numeric IEP
        assert [r["transactionType"] for r in broker.requests] == ["BUY"]
        assert not await engine.cycle()  # same book cannot buy again
        engine.on_book(book("CE",2,bid="50"))
        assert await engine.on_iep(obs("24900",3))  # sell first, despite opposite lag
        engine.on_book(book("PE",2))
        assert await engine.on_iep(obs("24900",4))  # reconcile flat, then new PE
        engine.on_book(book("PE",3,bid="50"))
        assert await engine.on_iep(obs("25100",5))
        engine.on_book(book("CE",3))
        assert await engine.on_iep(obs("25100",6))
        assert [(r["securityId"],r["transactionType"]) for r in broker.requests] == [("100","BUY"),("100","SELL"),("200","BUY"),("200","SELL"),("100","BUY")]
        rows = list(ledger.db.execute("SELECT * FROM lifecycles"))
        assert len(rows)==3 and sum(row["state"]=="CLOSED" for row in rows)==2
        assert D(rows[1]["bankroll"]) > D(rows[0]["bankroll"])
        for row in rows:
            totals = ledger.lifecycle_totals(row["lifecycle_id"])
            assert totals["entry_debit"] + totals["reserved"] <= lifecycle_ceiling(D(row["bankroll"]))
    asyncio.run(run())


def test_partial_entry_and_partial_exit_never_replenish_budget(tmp_path):
    async def run():
        engine, broker, ledger, _ = setup(tmp_path)
        engine.on_book(book("CE",1,quantity=845))
        await engine.on_iep(obs("25100",1))
        broker.next_fill = 195
        assert await engine.on_iep(obs("25100",2))
        await engine.cycle()
        active = engine.active
        before = engine._allocation(await broker.funds(),active)
        await engine.exit_manager.reduce(book("CE",1).instrument,65,book("CE",2,bid="50"),active["lifecycle_id"])
        await engine.runtime.orders.reconcile()
        after = engine._allocation(await broker.funds(),active)
        assert before.remaining == after.remaining and before.bankroll == after.bankroll
        assert after.spendable_cash > before.spendable_cash
        assert ledger.lifecycle_totals(active["lifecycle_id"])["quantity"] == 130
    asyncio.run(run())


def test_accepted_lost_response_restart_reconciles_once_and_exits_without_signal(tmp_path):
    async def run():
        engine, broker, ledger, clock = setup(tmp_path)
        engine.on_book(book("CE",1))
        await engine.on_iep(obs("25100",1))
        broker.lose_response = True
        with pytest.raises(TimeoutError): await engine.on_iep(obs("25100",2))
        assert ledger.pending_intents()[0]["state"] == "SEND_UNKNOWN"
        recovered = SessionEngine(engine.runtime,{},now_fn=lambda:clock[0])
        assert recovered.reference == engine.reference
        await recovered.runtime.recover()
        recovered.runtime.status.auto_live_armed = False
        recovered.signal_reconnect(None)
        assert await recovered.cycle()
        assert [r["transactionType"] for r in broker.requests] == ["BUY","SELL"]
        assert broker.requests[1]["price"] == "0.05"
        assert not await recovered.cycle()
        assert recovered.active is None
        assert not ledger.pending_intents()
    asyncio.run(run())


def test_disarm_and_time_exit_with_zero_bid_still_reduce(tmp_path):
    async def run():
        engine, broker, ledger, clock = setup(tmp_path)
        engine.on_book(book("CE",1))
        await engine.on_iep(obs("25100",1)); await engine.on_iep(obs("25100",2))
        engine.runtime.disarm_new_entries()
        engine.on_book(book("CE",2,bid="0"))
        clock[0] = NOW.replace(hour=10,minute=9)
        assert await engine.cycle()
        assert broker.requests[-1]["transactionType"] == "SELL"
        assert broker.requests[-1]["price"] == "0.05"
        await engine.cycle()
        assert engine.active is None and len(broker.requests)==2
    asyncio.run(run())


def test_reconnect_invalidates_books_and_requires_two_new_observations(tmp_path):
    async def run():
        engine, broker, ledger, _ = setup(tmp_path)
        engine.on_book(book("CE",1))
        await engine.on_iep(obs("25100",1))
        engine.signal_reconnect("u2")
        assert not await engine.on_iep(obs("25100",2,"u1"))
        engine.on_status(CasStatus(CasPhase.CAS_LM_START,int(NOW.timestamp()*1000),DAY,"u2"))
        engine.market_reconnect("d2")
        engine.on_book(book("CE",1))  # old epoch rejected
        assert not engine.books
        engine.on_book(replace(book("CE",2),epoch="d2"))
        assert not await engine.on_iep(obs("25100",3,"u2"))
        assert await engine.on_iep(obs("25100",4,"u2"))
        assert len(broker.requests)==1
    asyncio.run(run())


def test_duplicate_or_reordered_trade_events_cannot_erase_fills(tmp_path):
    async def run():
        engine, broker, ledger, _ = setup(tmp_path)
        engine.on_book(book("CE",1))
        await engine.on_iep(obs("25100",1)); await engine.on_iep(obs("25100",2))
        await engine.runtime.orders.reconcile()
        before = ledger.lifecycle_totals(engine.active["lifecycle_id"])
        broker.trade_rows += broker.trade_rows[:]
        broker.order_rows[0]["orderStatus"] = "PENDING"
        broker.order_rows[0]["filledQty"] = 0
        await engine.runtime.orders.reconcile()
        after = ledger.lifecycle_totals(engine.active["lifecycle_id"])
        assert after == before and after["quantity"] == 195
    asyncio.run(run())
