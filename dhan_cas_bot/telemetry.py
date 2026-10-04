"""Bounded, process-local timing samples. Never export order IDs or payloads."""
from collections import Counter, OrderedDict, deque
import math
import time

METRICS = frozenset({'decision_ms', 'signal_to_decision_ms', 'market_to_decision_ms',
                     'decision_to_submit_ms', 'http_ack_ms', 'first_fill_recorded_ms',
                     'reconcile_ms', 'loop_lag_ms', 'book_age_ms'})
REASONS = frozenset({'ACCOUNT_REFRESH_REQUIRED', 'ENTRY_NOT_PERMITTED', 'UNMANAGED_POSITION',
                     'OUTSIDE_ENTRY_WINDOW', 'FEED_NOT_READY', 'INPUTS_CHANGED',
                     'NO_EXECUTABLE_CANDIDATE', 'ENTRY_SUBMITTED', 'RECONCILE_FAILED',
                     'RECONCILE_SUPERSEDED', 'ORDER_EVENT', 'DUPLICATE_ORDER_EVENT',
                     'CONFIRMATION_MISSING', 'DIRECTION_MISMATCH', 'EMPTY_BOOK',
                     'INSUFFICIENT_DEPTH', 'INTRINSIC_GAP_MISSING', 'CASH_OR_CAP_TOO_SMALL',
                     'NET_EDGE_NONPOSITIVE', 'PRICE_BAND_REJECTED',
                     'MARKET_FRAME_REJECTED', 'MARKET_BOOK_REJECTED'})


class Telemetry:
    def __init__(self, clock=time.monotonic, size=512):
        self.clock, self.size = clock, size
        self.samples = {key: deque(maxlen=size) for key in METRICS}
        self.counts = Counter()
        self.feeds = {}
        self.orders = OrderedDict()
        self.decision_at = None

    def sample(self, name, milliseconds):
        if name in METRICS and math.isfinite(milliseconds) and milliseconds >= 0:
            self.samples[name].append(milliseconds)

    def reason(self, name):
        if name in REASONS:
            self.counts[name] += 1

    def received(self, feed):
        if feed in {'signal', 'market', 'order'}:
            self.feeds[feed] = self.clock()

    def decision(self):
        stamp = self.clock()
        self.decision_at = stamp
        for feed in ('signal', 'market'):
            if feed in self.feeds:
                self.sample(feed+'_to_decision_ms', (stamp-self.feeds[feed])*1000)
        return stamp

    def submitted(self, intent_id):
        stamp = self.clock()
        self.orders[intent_id] = stamp
        while len(self.orders) > self.size:
            self.orders.popitem(last=False)
        if self.decision_at is not None:
            self.sample('decision_to_submit_ms', (stamp-self.decision_at)*1000)
        return stamp

    def filled(self, intent_id):
        stamp = self.orders.pop(intent_id, None)
        if stamp is not None:
            self.sample('first_fill_recorded_ms', (self.clock()-stamp)*1000)

    def snapshot(self):
        result = {}
        for name, values in self.samples.items():
            if not values:
                continue
            ordered = sorted(values)
            result[name] = {'samples': len(values), **{
                'p'+str(p): round(ordered[max(0, math.ceil(len(ordered)*p/100)-1)], 3)
                for p in (50, 95, 99)}}
        return {'scope': 'current_process_rolling_512', 'latency': result,
                'decision_counts': dict(self.counts)}
