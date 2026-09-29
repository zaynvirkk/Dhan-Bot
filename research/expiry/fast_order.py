"""Same order as core.make_order; logarithmic whole-lot affordability search."""
from datetime import timedelta
from decimal import Decimal as D
from math import ceil
from dhan_cas_bot.risk import FeeSchedule
from research.gauntlet.core import Order,tick_up

def make_order(contract,known,at,cash,signal_id,participation=D('.05')):
    if not known or any(b.available>at for b in known):
        raise ValueError('future or missing data in decision snapshot')
    last=known[-1]
    if at-last.available>timedelta(minutes=1) or last.close<=0:return None,'STALE_OR_ZERO_QUOTE_PROXY'
    if not contract.index and contract.expiry<=at.date().isoformat():return None,'DHAN_STOCK_EXPIRY_BLOCK'
    if last.oi<10*contract.lot:return None,'INSUFFICIENT_KNOWN_OI'
    limit=tick_up(last.close*D('1.05'),contract.tick)
    recent=[b for b in known if b.start>=last.start-timedelta(minutes=2)]
    if len(recent)<3:return None,'MISSING_RECENT_LIQUIDITY'
    capacity=int(D(min(b.volume for b in recent))*participation)//contract.lot*contract.lot
    qty=min(int(cash*D('.95')/(limit*contract.lot))*contract.lot,capacity)
    low=0;high=max(0,qty//contract.lot);fees=FeeSchedule()
    # Turnover, child count and rounded fees are nondecreasing in whole lots.
    # This finds the exact same maximum as the original decrementing loop.
    while low<high:
        mid=(low+high+1)//2;n=mid*contract.lot;turnover=limit*n
        if turnover+fees.buy(turnover,ceil(n/contract.freeze))<=cash*D('.95'):low=mid
        else:high=mid-1
    if low:return Order(contract,at,limit,low*contract.lot,signal_id,last.close),'ORDER_CREATED'
    return None,'UNAFFORDABLE_OR_PAST_CAPACITY'
