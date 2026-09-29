"""Causal snapshots and a deliberately adverse minute-bar execution scenario.

No model fill here is an exchange execution receipt. Bar highs/volume are used
only AFTER order creation, never to pick a contract or resize an order.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
from math import ceil
from typing import Sequence
from dhan_cas_bot.risk import FeeSchedule

D = Decimal

@dataclass(frozen=True)
class Bar:
    start: datetime
    open: D
    high: D
    low: D
    close: D
    volume: int
    oi: int

    @property
    def available(self):
        return self.start + timedelta(minutes=1)

    @classmethod
    def parse(cls, row):
        out=cls(datetime.fromisoformat(row[0]),*(D(str(v)) for v in row[1:5]),int(row[5]),int(row[6] or 0))
        if out.start.tzinfo is None or not all(x.is_finite() for x in (out.open,out.high,out.low,out.close)):
            raise ValueError('invalid bar timestamp/price')
        if out.low<0 or out.high<max(out.open,out.close,out.low) or out.low>min(out.open,out.close) or out.volume<0 or out.oi<0:
            raise ValueError('invalid OHLCV/OI')
        return out

@dataclass(frozen=True)
class Contract:
    key: str
    symbol: str
    expiry: str
    side: str
    strike: D
    lot: int
    tick: D
    freeze: int
    index: bool

    @classmethod
    def parse(cls, row):
        lot=int(row['lot_size']); freeze=int(row.get('freeze_quantity') or lot)
        return cls(row['instrument_key'],row['underlying_symbol'],row['expiry'],row['instrument_type'],
                   D(str(row['strike_price'])),lot,D(str(row['tick_size']))/100,
                   freeze//lot*lot,row.get('underlying_type')=='INDEX')

@dataclass(frozen=True)
class Order:
    contract: Contract
    decided: datetime
    limit: D
    quantity: int
    signal_id: str
    reference_close: D

def tick_up(price,tick):
    return (price/tick).to_integral_value(rounding=ROUND_CEILING)*tick

def tick_down(price,tick):
    return (price/tick).to_integral_value(rounding=ROUND_FLOOR)*tick

def snapshot(rows: Sequence[Bar], at: datetime, lag=0):
    return tuple(r for r in rows if r.available+timedelta(seconds=lag)<=at)

def make_order(contract, known, at, cash, signal_id, participation=D('.05')):
    """Only completed, fresh bars; fixed quantity, fees and price bound."""
    if not known or any(b.available>at for b in known):
        raise ValueError('future or missing data in decision snapshot')
    last=known[-1]
    if at-last.available>timedelta(minutes=1) or last.close<=0:
        return None,'STALE_OR_ZERO_QUOTE_PROXY'
    if not contract.index and contract.expiry<=at.date().isoformat():
        return None,'DHAN_STOCK_EXPIRY_BLOCK'
    if last.oi<10*contract.lot:
        return None,'INSUFFICIENT_KNOWN_OI'
    limit=tick_up(last.close*D('1.05'),contract.tick)
    recent=[b for b in known if b.start>=last.start-timedelta(minutes=2)]
    if len(recent)<3:
        return None,'MISSING_RECENT_LIQUIDITY'
    max_volume=min(b.volume for b in recent)
    capacity=int(D(max_volume)*participation)//contract.lot*contract.lot
    qty=min(int(cash*D('.95')/(limit*contract.lot))*contract.lot,capacity)
    fees=FeeSchedule()
    while qty>0:
        children=ceil(qty/contract.freeze)
        turnover=limit*qty
        if turnover+fees.buy(turnover,children)<=cash*D('.95'):
            return Order(contract,at,limit,qty,signal_id,last.close),'ORDER_CREATED'
        qty-=contract.lot
    return None,'UNAFFORDABLE_OR_PAST_CAPACITY'

def entry(order, future, delay_bars=1, participation=D('.05'), adverse=True):
    """Strict next FULL bar after assumed processing delay. Never resize."""
    at=order.decided.replace(second=0,microsecond=0)+timedelta(minutes=delay_bars)
    if at<order.decided:
        raise ValueError('entry precedes decision')
    bar=next((b for b in future if b.start==at),None)
    if bar is None:
        return {'status':'UNKNOWN_ENTRY_BAR','time':at.isoformat()}
    price=tick_up(bar.high if adverse else bar.open*D('1.01'),order.contract.tick)
    if price>order.limit:
        return {'status':'MODELED_LIMIT_MISS','time':at.isoformat()}
    if D(order.quantity)>D(bar.volume)*participation:
        return {'status':'MODELED_CAPACITY_MISS','time':at.isoformat()}
    return {'status':'MODELED_FILL','time':at.isoformat(),'price':price,'bar':bar}

def exit_trade(order, fill, future, invalid_at, close_at, participation=D('.05'),liquidate_minutes=0):
    """Target rests only after entry bar; underlying invalidation has delay.

    Future market bars can determine executions, but cannot alter the submitted
    order. A missing holding minute or unresolved low-volume exit is UNKNOWN.
    """
    contract=order.contract
    target=tick_up(fill['price']*2,contract.tick)
    start=fill['bar'].available
    bars={b.start:b for b in future}
    at=start
    # The underlying invalidation time is an event scheduled by the replay,
    # not information supplied to the strategy before it occurs. Its dispatch
    # deadline must not depend on which option bar the loop happens to inspect.
    invalid_order_at=invalid_at+timedelta(minutes=1) if invalid_at is not None else None
    marks=[]
    remaining=order.quantity
    proceeds=D(0)
    parts=[]
    reason=None
    while at<=close_at:
        b=bars.get(at)
        if b is None:
            return {'status':'UNKNOWN_HOLDING_BAR','time':at.isoformat()}
        marks.append(b.low)
        # Exit decision after the invalidating underlying bar is completed.
        # Adverse precedence if target and pending invalidation share a bar.
        exiting=(invalid_order_at is not None and at>=invalid_order_at) or at>=close_at-timedelta(minutes=liquidate_minutes) or remaining<order.quantity
        if exiting:
            qty=min(remaining,int(D(b.volume)*participation)//contract.lot*contract.lot)
            px=tick_down(b.low,contract.tick)
            if qty:
                proceeds+=px*qty;remaining-=qty
                parts.append({'quantity':qty,'price':str(px),'at':at.isoformat()})
                reason=reason or ('INVALIDATION' if invalid_order_at is not None and at>=invalid_order_at else 'TIMED_CLOSE')
            if remaining==0:
                return {'status':'MODELED_EXIT','time':at.isoformat(),'price':proceeds/order.quantity,
                        'reason':reason,'worst_mark':min(marks),'parts':parts}
            if at>=close_at or not liquidate_minutes:
                return {'status':'UNKNOWN_EXIT_CAPACITY','time':at.isoformat(),'remaining':remaining,'parts':parts}
        elif invalid_at is not None and invalid_at<=b.available:
            # Intrabar ordering cannot be recovered from OHLC. Do not award a
            # target in the same minute the underlying invalidates the trade.
            pass
        elif D(order.quantity)<=D(b.volume)*participation and b.high>=target*D('1.02'):
            return {'status':'MODELED_EXIT','time':at.isoformat(),'price':target,'reason':'TARGET_2X','worst_mark':min(marks)}
        at+=timedelta(minutes=1)
    return {'status':'UNKNOWN_EXIT','time':at.isoformat()}

def cash_after(cash,order,entry_price,exit_price,exit_parts=None):
    n=ceil(order.quantity/order.contract.freeze);fees=FeeSchedule()
    buy=entry_price*order.quantity;sell=exit_price*order.quantity
    sell_fees=(sum((fees.sell(D(p['price'])*p['quantity'],ceil(p['quantity']/order.contract.freeze)) for p in exit_parts),D(0))
               if exit_parts else fees.sell(sell,n))
    costs=fees.buy(buy,n)+sell_fees
    return cash-buy+sell-costs,costs
