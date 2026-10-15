from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime, timezone
import uuid

from .domain import ContractError, Instrument, Intent, OptionBook
from .ledger import Ledger
from .orders import Broker, OrderManager
from .risk import FeeSchedule, worst_case_entry_cash, reserve_cash


def probe_candidates(books, now, epoch, *, rejected=(), remaining_debit=None):
    """Observed liquidity prefilter, not a guarantee of broker RMS eligibility."""
    from .session_strategies import IST
    stamp=int(now.timestamp()*1_000_000_000);day=now.astimezone(IST).date()
    result=[]
    for b in books:
        inst=b.instrument;stats=b.statistics;bid=b.top_bid;ask=b.top_ask
        if (inst.security_id in rejected or b.epoch!=epoch or not 0<=stamp-b.received_ns<=2_000_000_000
                or inst.expiry<day or not bid or not ask or bid.quantity<inst.lot_size or ask.quantity<inst.lot_size
                or ask.price<bid.price or (ask.price-bid.price)/bid.price>Decimal('.02')
                or stats is None or stats.open_interest<100*inst.lot_size or stats.volume<100*inst.lot_size):continue
        floor=max(inst.tick_size,inst.lower_limit or Decimal(0))
        if floor>=bid.price or (inst.upper_limit is not None and floor>inst.upper_limit):continue
        cost=reserve_cash(worst_case_entry_cash(inst.lot_size,floor,1,FeeSchedule()))
        if remaining_debit is not None and cost>remaining_debit:continue
        result.append(b)
    result.sort(key=lambda b:(-b.statistics.open_interest,-b.statistics.volume,
        (b.top_ask.price-b.top_bid.price)/b.top_bid.price,b.instrument.expiry,int(b.instrument.security_id)))
    return result


def rejected_probe_contracts(ledger, now):
    from .session_strategies import IST
    day=now.astimezone(IST).date();result=set()
    for row in ledger.db.execute("SELECT i.security_id,i.created_at FROM intents i JOIN orders o ON o.intent_id=i.intent_id WHERE i.lifecycle_id='route-probe' AND o.state='REJECTED' ORDER BY i.created_at DESC LIMIT 128"):
        try:
            at=datetime.fromisoformat(row['created_at'])
            if at.tzinfo and at<=now and at.astimezone(IST).date()==day:result.add(row['security_id'])
        except (ValueError,TypeError):continue
    return result


def extra_attempts(ledger, session_id, normal_limit, now):
    """An explicit operator grant is one extra attempt on exactly one IST date."""
    from .session_strategies import IST
    if session_id!=now.astimezone(IST).date().isoformat():return 0
    value=ledger.metadata('probe.extra_attempt:'+session_id,{})
    if (not isinstance(value,dict) or type(value.get('extra')) is not int or value['extra']!=1
            or type(value.get('normal_limit')) is not int or value.get('normal_limit')!=normal_limit
            or value.get('operator_requested') is not True):return 0
    try:
        recorded=datetime.fromisoformat(value['recorded_at'])
        if recorded.tzinfo is None or recorded>now or recorded.astimezone(IST).date().isoformat()!=session_id:return 0
    except (KeyError,ValueError,TypeError):return 0
    return 1


def grant_extra_attempt(ledger, session_id, normal_limit, now):
    from .session_strategies import IST
    if session_id!=now.astimezone(IST).date().isoformat() or type(normal_limit) is not int or normal_limit<=0:
        raise ValueError('extra attempt must name the current IST date and existing normal limit')
    key='probe.extra_attempt:'+session_id
    if extra_attempts(ledger,session_id,normal_limit,now):return
    if ledger.metadata(key) is not None:raise ValueError('existing different extra-attempt record')
    ledger.put_metadata(key,{'extra':1,'normal_limit':normal_limit,'operator_requested':True,'recorded_at':now.isoformat()})


@dataclass(frozen=True)
class RouteProof:
    epoch: str
    order_id: str
    account_id: str
    accepted_at: datetime
    zero_fill: bool


def managed_exit_route(ledger, account, epoch, connected_at, echoed):
    """A real reduction fill can prove the current socket without a new buy.

    Historical or replayed trades cannot establish a newly connected route.
    This consumes no probe allowance and never submits an order itself.
    """
    if not connected_at or not epoch:return None
    for row in ledger.db.execute("SELECT i.intent_id,i.created_at,i.quantity,i.security_id,i.state,o.order_id,o.broker_account,o.state AS broker_state FROM intents i JOIN orders o ON o.intent_id=i.intent_id JOIN lifecycles l ON l.lifecycle_id=i.lifecycle_id WHERE i.side='SELL' AND i.lifecycle_id!='route-probe' AND i.security_id=l.security_id ORDER BY i.created_at DESC LIMIT 64"):
        try:
            submitted=datetime.fromisoformat(row['created_at'])
            if submitted.tzinfo is None or submitted<connected_at:continue
        except (ValueError,TypeError):continue
        evidence=echoed.get(row['order_id'])
        if (row['broker_account']!=account or row['state'] not in {'FILLED','CANCELLED','EXPIRED'}
                or row['broker_state']=='REJECTED' or not evidence or evidence[0]!=epoch
                or evidence[1] not in {'PART_TRADED','TRADED','CANCELLED','EXPIRED'}):continue
        fills=list(ledger.db.execute('SELECT security_id,quantity FROM fills WHERE order_id=? AND intent_id=?',(row['order_id'],row['intent_id'])))
        if (fills and all(f['security_id']==row['security_id'] and f['quantity']>0 for f in fills)
                and 0<sum(f['quantity'] for f in fills)<=row['quantity']):return row['order_id']
    return None


class RouteQualifier:
    def __init__(self, ledger: Ledger, broker: Broker, *, session_id: str, max_attempts: int, debit_cap: Decimal, mandate_spend_cap: Decimal):
        if max_attempts <= 0 or debit_cap <= 0 or mandate_spend_cap <= 0:
            raise ContractError("qualification budgets must be finite and positive")
        self.ledger = ledger
        self.broker = broker
        self.session_id = session_id
        self.max_attempts = max_attempts
        self.debit_cap = debit_cap
        self.mandate_spend_cap = mandate_spend_cap

    async def qualify(self, book: OptionBook, *, epoch: str) -> RouteProof:
        attempts = int(self.ledger.counter(f"probe.attempts:{self.session_id}"))
        totals = self.ledger.lifecycle_totals("route-probe")
        spent = totals["entry_debit"] + totals["reserved"]
        if attempts >= self.max_attempts+extra_attempts(self.ledger,self.session_id,self.max_attempts,datetime.now(timezone.utc)):
            raise ContractError("qualification attempt budget exhausted")
        bid = book.top_bid
        if bid is None or bid.quantity < book.instrument.lot_size:
            raise ContractError("no one-lot bid for qualification")
        from decimal import ROUND_CEILING
        limit = max(book.instrument.tick_size, book.instrument.lower_limit or Decimal("0"))
        limit = (limit / book.instrument.tick_size).to_integral_value(rounding=ROUND_CEILING) * book.instrument.tick_size
        if limit >= bid.price:
            raise ContractError("no positive non-marketable probe price")
        cost = reserve_cash(worst_case_entry_cash(book.instrument.lot_size, limit, 1, FeeSchedule()))
        session_debit = self.ledger.counter(f"probe.debit:{self.session_id}")
        if session_debit + cost > self.debit_cap or spent + cost > self.mandate_spend_cap:
            raise ContractError("qualification debit budget exhausted")
        funds = await self.broker.funds()
        if funds.broker_account != self.broker.account_id or cost > funds.spendable_cash:
            raise ContractError("qualification cash unavailable")
        intent = Intent("probe-" + uuid.uuid4().hex, "BUY", book.instrument, book.instrument.lot_size, limit, "p" + uuid.uuid4().hex[:28], datetime.now(timezone.utc), "route-probe")
        manager = OrderManager(self.ledger, self.broker)
        self.ledger.set_counter(f"probe.attempts:{self.session_id}", attempts + 1)
        self.ledger.set_counter("probe.spent", spent + cost)
        self.ledger.set_counter(f"probe.debit:{self.session_id}", session_debit + cost)
        self.ledger.put_metadata("route_probe", {"epoch": epoch, "correlation_id": intent.client_order_id, "intent_id": intent.intent_id})
        response = await manager.submit(intent, reserved_cash=cost)
        order_id = str(response["orderId"])
        if response.get("accountId", self.broker.account_id) != self.broker.account_id:
            raise ContractError("qualification response account mismatch")
        if response.get("orderStatus") == "REJECTED":
            raise ContractError("rejected probe cannot qualify route")
        return RouteProof(epoch, order_id, self.broker.account_id, datetime.now(timezone.utc), False)
