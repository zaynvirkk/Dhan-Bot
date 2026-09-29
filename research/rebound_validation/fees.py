"""Dated statutory rate model; still a rounded model, not broker invoices."""
from datetime import timedelta
from math import ceil
from dhan_cas_bot.risk import FeeSchedule
from research.gauntlet.core import D, Order, tick_up


def schedule(day):
    # NSE/FA/73061: exchange + IPFT total unchanged on March 1.
    # NSE/FATAX/73524: option-sale STT changes on April 1.
    return FeeSchedule(exchange_rate=D('3503' if day < '2026-03-01' else '3552.99')/D('10000000'),
                       ipft_rate=D('50' if day < '2026-03-01' else '.01')/D('10000000'),
                       sell_stt_rate=D('.001' if day < '2026-04-01' else '.0015'))


def make_order(c, known, at, cash, signal_id, fees):
    if len(known) != 3 or any(b.available > at for b in known):
        raise ValueError('FUTURE_OR_MISSING_DECISION_DATA')
    if [b.start for b in known] != [at-timedelta(minutes=i) for i in (3, 2, 1)]:
        raise ValueError('STALE_OR_NONCONTIGUOUS_DECISION_DATA')
    if known[-1].close <= 0:
        return None, 'STALE_OR_ZERO_QUOTE_PROXY'
    if known[-1].oi < 10*c.lot:
        return None, 'INSUFFICIENT_KNOWN_OI'
    limit = tick_up(known[-1].close*D('1.05'), c.tick)
    capacity = int(D(min(b.volume for b in known))*D('.05'))//c.lot*c.lot
    high = min(int(cash*D('.95')/(limit*c.lot)), capacity//c.lot)
    low = 0
    while low < high:
        mid = (low+high+1)//2
        q = mid*c.lot
        if limit*q+fees.buy(limit*q, ceil(q/c.freeze)) <= cash*D('.95'):
            low = mid
        else:
            high = mid-1
    if low:
        return Order(c, at, limit, low*c.lot, signal_id, known[-1].close), 'ORDER_CREATED'
    return None, 'UNAFFORDABLE_OR_PAST_CAPACITY'
