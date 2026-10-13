"""Only provider-built, completed NIFTY I1 candles; never OHLC inferred from ticks."""
from datetime import datetime,timedelta,timezone
from decimal import Decimal as D
from .session_strategies import Bar
from .upstox_signal import NIFTY_KEY


class CompletedIndexMinutes:
    def __init__(self):self.reset()

    def reset(self):
        self.rows={};self.conflicts=set();self.epoch=None;self.received=None

    def accept(self,frame,epoch,received):
        if frame.type!=1 or NIFTY_KEY not in frame.feeds:return False
        try:
            stamp=datetime.fromtimestamp(int(frame.currentTs)/1000,timezone.utc)
            if not 0 <= (received-stamp).total_seconds() <= 5:return False
            rows=frame.feeds[NIFTY_KEY].fullFeed.indexFF.marketOHLC.ohlc
        except (ValueError,OverflowError,AttributeError):return False
        if epoch!=self.epoch:self.reset();self.epoch=epoch
        changed=False
        for row in rows:
            if row.interval!='I1':continue
            try:
                start=datetime.fromtimestamp(int(row.ts)/1000,timezone.utc)
                available=start+timedelta(minutes=1)
                values=[D(str(getattr(row,k))) for k in ('open','close','high','low')]
                op,close,high,low=values
                volume=int(row.vol)
                if (start.second or start.microsecond or available>stamp or available>received
                        or not 0 <= (received-available).total_seconds()<=90
                        or any(not v.is_finite() or v<=0 for v in values)
                        or low>min(op,close) or high<max(op,close) or low>high or volume<0):continue
                bar=Bar(available,op,close,volume,0,high,low)
            except (ValueError,OverflowError,ArithmeticError):continue
            if available in self.conflicts:continue
            if available in self.rows and self.rows[available]!=bar:
                self.rows.pop(available);self.conflicts.add(available);continue
            if available not in self.rows:changed=True
            self.rows[available]=bar;self.received=received
        self.rows={t:b for t,b in self.rows.items() if (received-t).total_seconds()<=120}
        self.conflicts={t for t in self.conflicts if (received-t).total_seconds()<=120}
        return changed

    def current(self,now):
        if self.received is None or not 0 <= (now-self.received).total_seconds()<=5:return None
        minute=now.replace(second=0,microsecond=0)
        return self.rows.get(minute)
