"""Data-only subscription windows covering the existing option selectors."""
import asyncio
import json
from decimal import Decimal

from .feeds import dhan_subscription, chunked


def market_ids(catalogue, day, *, anchors=(), held=(), future_id=None, full_expiry=None):
    result=set(held)
    if future_id:result.add(future_id)
    anchors={a for a in anchors if isinstance(a,Decimal) and a.is_finite() and a>0}
    rows=[i for i in catalogue.values() if i.expiry>=day]
    if full_expiry is not None:result.update(i.security_id for i in rows if i.expiry==full_expiry)
    for expiry in sorted({i.expiry for i in rows})[:3]:
        eligible=[i for i in rows if i.expiry==expiry]
        for anchor in anchors:
            # Seconds rules choose at most24 nearest contracts. Minute rules
            # choose ATM and four outward strikes.32 around each independently
            # observed anchor covers both, with room before the window rolls.
            result.update(i.security_id for i in sorted(eligible,
                key=lambda i:(abs(i.strike-anchor),i.security_id))[:32])
    return result


class MarketSubscriptions:
    def __init__(self, bootstrap):
        self.bootstrap=set(bootstrap);self.wanted=set(bootstrap)
        self.applied=set();self.epoch=None;self.last_error=''

    async def sync(self, runner, epoch, desired, books):
        self.wanted=set(desired)
        # Retired quotes cannot stay eligible while an unsubscribe is pending.
        for security in set(books)-self.wanted:books.pop(security,None)
        socket=runner.socket
        if socket is None or not runner.subscriptions_ready:return False
        if epoch!=self.epoch:
            self.epoch=epoch;self.applied=set(self.bootstrap)
        additions=self.wanted-self.applied;removals=self.applied-self.wanted
        messages=dhan_subscription(sorted(additions))
        messages.extend({'RequestCode':22,'InstrumentCount':len(batch),
                         'InstrumentList':[{'ExchangeSegment':'NSE_FNO','SecurityId':sid} for sid in batch]}
                        for batch in chunked(sorted(removals),100))
        try:
            for message in messages:
                await asyncio.wait_for(socket.send(json.dumps(message,separators=(',',':'))),2)
                if runner.socket is not socket:return False
        except Exception as exc:
            self.last_error=type(exc).__name__
            if runner.socket is socket:await socket.close()
            return False
        self.applied=set(self.wanted);self.last_error=''
        return True
