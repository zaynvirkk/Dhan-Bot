"""Versioned net-profit protection candidate; not a forecast or live default.

Callers must supply current executable liquidation P&L after all costs. Stale
quotes, LTP and insufficient depth cannot stand in for that observation.
"""
from decimal import Decimal

D=Decimal


def observe(net_pnl, round_trip_cost, previous=None, *, retain=D('.5')):
    if any(not isinstance(x,D) or not x.is_finite() for x in (net_pnl,round_trip_cost,retain)):
        raise ValueError('finite Decimal observations required')
    if round_trip_cost<0 or not 0<retain<1:
        raise ValueError('invalid profit-protection policy')
    previous=previous or {}
    peak=max(net_pnl,D(previous['peak'])) if 'peak' in previous else net_pnl
    floor=D(previous['floor']) if previous.get('floor') is not None else None
    if peak>0 and peak>=2*round_trip_cost:
        floor=max(floor or D(0),peak*retain)
    triggered=previous.get('triggered') is True or (floor is not None and net_pnl<=floor)
    return {'version':'NET_PROFIT_RATCHET_V1','retain':str(retain),
            'peak':str(peak),'floor':str(floor) if floor is not None else None,
            'net_pnl':str(net_pnl),'triggered':triggered}
