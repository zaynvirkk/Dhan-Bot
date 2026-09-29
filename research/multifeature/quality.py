"""Retrospective tape validation, never a tradable feature or source repair."""
from research.gauntlet.core import D


def tape_issues(raw, bars):
    issues=[]
    if raw['audit']['status']!='RECONCILED':issues.append(raw['audit']['status'])
    tick=D(str(raw['metadata']['tick_size']))/100
    if tick<=0:raise ValueError('invalid contract tick')
    if any(getattr(b,k)%tick for b in bars for k in ('open','high','low','close')):
        issues.append('UNKNOWN_OFF_TICK_PRICE')
    if any(not b.low<=min(b.open,b.close)<=max(b.open,b.close)<=b.high for b in bars):
        issues.append('UNKNOWN_INVALID_OHLC')
    if len({b.start for b in bars})!=len(bars):issues.append('UNKNOWN_DUPLICATE_BAR')
    return issues
