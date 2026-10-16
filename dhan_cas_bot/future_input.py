"""Small independent futures decoder; receipt freshness never comes from LTT."""
from types import SimpleNamespace
from decimal import Decimal
from .domain import Segment, ContractError
from .dhan_feed import packets, decode_full_binary, DhanFeedDisconnect
from .seconds_strategies import future_quote_mid


class FutureInput:
    def __init__(self, tape, security_id, option_epoch):
        self.tape, self.option_epoch = tape, option_epoch
        self.instrument = SimpleNamespace(security_id=str(security_id),
            tick_size=Decimal('.05'), segment=Segment.NSE_FNO)
        self.connected = False
        self.reason = 'FUTURES_DISCONNECTED'
        self.last_received_ns = None

    def connect(self):
        self.connected = True
        self.tape.reset()
        self.reason = 'FUTURES_WARMUP'

    def disconnect(self):
        self.connected = False
        self.tape.invalidate_future()
        self.reason = 'FUTURES_DISCONNECTED'

    def receive(self, payload, received_ns):
        if not self.connected:
            return False
        try:
            accepted=False
            batch = list(packets(payload))
            for packet in batch:
                if packet[0] != 8:
                    continue
                tick = decode_full_binary(packet, self.instrument)
                mid = future_quote_mid(tick)
                # A repeated valid book is an actual new receipt. It refreshes
                # availability but cannot invent a price change or momentum.
                self.tape.future_tick(mid, received_ns, self.option_epoch())
                self.last_received_ns = received_ns
                self.reason = 'CURRENT'
                accepted=True
            return accepted
        except DhanFeedDisconnect:
            self.disconnect()
            raise
        except ContractError:
            self.tape.invalidate_future()
            self.reason = 'FUTURES_PACKET_REJECTED'
            return False

    def health(self, now):
        age = (int(now.timestamp()*1e9)-self.last_received_ns)/1e6 if self.last_received_ns is not None else None
        current = self.connected and self.tape.future_current(now)
        return {'connected': self.connected, 'current': current,
            'age_ms': age, 'maximum_age_ms': 1500,
            'reason': 'CURRENT' if current else 'FUTURES_STALE' if self.reason == 'CURRENT' else self.reason}
