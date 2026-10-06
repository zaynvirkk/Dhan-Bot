"""Bounded read model of inputs already held by the engine; never evaluates trades."""
from datetime import datetime, timezone

from .domain import json_safe
from .risk import reserve_cash, worst_case_entry_cash
from .strategy import intrinsic


def observation_view(engine, instruments):
    pre_auction = getattr(engine, 'reference_observations', [])
    ltp = pre_auction[-1] if pre_auction else None
    value = engine.observations[-1][0] if engine.observations else None
    anchor = value if value is not None else ltp.value if ltp else None
    reference = engine.reference.value if engine.reference else None
    direction = None if value is None or reference is None or value == reference else ('CE' if value > reference else 'PE')
    # Qualifying streaks first, then proximity; this is explicitly a watchlist,
    # not the optimizer's ranking or a promise of executable liquidity.
    ordered = sorted(engine.books.values(), key=lambda b: (
        -len(engine.streaks.get(b.instrument.security_id, [])),
        abs(b.instrument.strike - anchor) if anchor is not None else b.instrument.strike,
        b.instrument.security_id))[:5]
    books = []
    for book in ordered:
        inst, bid, ask = book.instrument, book.top_bid, book.top_ask
        history = engine.streaks.get(inst.security_id, [])
        books.append({
            'security_id': inst.security_id, 'strike': inst.strike, 'option_type': inst.option_type,
            'expiry': inst.expiry, 'lot_size': inst.lot_size,
            'bid': bid.price if bid else None, 'ask': ask.price if ask else None,
            'bid_quantity': bid.quantity if bid else None, 'ask_quantity': ask.quantity if ask else None,
            'one_lot_cash': reserve_cash(worst_case_entry_cash(inst.lot_size, ask.price)) if ask else None,
            'conditional_intrinsic': min(intrinsic(inst.option_type, inst.strike, v) for v, _ in history) if history else None,
            'confirmations': len(history),
            'last_price': book.statistics.last_price if book.statistics else None,
            'volume': book.statistics.volume if book.statistics else None,
            'open_interest': book.statistics.open_interest if book.statistics else None,
            'observed_at': datetime.fromtimestamp(book.received_ns / 1e9, timezone.utc),
        })
    return json_safe({
        'phase': engine.status.phase if engine.status else None,
        'phase_at': datetime.fromtimestamp(engine.status.updated_time_ms / 1000, timezone.utc) if engine.status else None,
        'reference': reference, 'iep': value, 'direction': direction,
        'ltp': ltp.value if ltp else None,
        'ltp_at': datetime.fromtimestamp(ltp.provider_ts_ms / 1000, timezone.utc) if ltp else None,
        'ltp_received_at': datetime.fromtimestamp(ltp.received_ns / 1e9, timezone.utc) if ltp else None,
        'iep_at': datetime.fromtimestamp(engine.last_signal_timestamp / 1000, timezone.utc) if value is not None and engine.last_signal_timestamp > 0 else None,
        'final_value': engine.final_value.value if engine.final_value else None,
        'expiry': min((i.expiry for i in instruments), default=None),
        'watchlist': books,
    })
