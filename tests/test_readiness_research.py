from datetime import timedelta
from decimal import Decimal as D
from dataclasses import replace
from research.gauntlet.core import Bar
from research.expiry.signals import stamp
from research.readiness.experiment import scan,vwap_series

DAY='2026-07-07'

def fixture():
    at=stamp(DAY,'09:16');spot={};future={}
    while at<=stamp(DAY,'15:10'):
        px=D(24000)
        if stamp(DAY,'09:46')<=at<=stamp(DAY,'09:57'):px=D(24030)
        if at>=stamp(DAY,'09:58'):px=D(24003)-(at-stamp(DAY,'09:58')).seconds//60
        spot[at]=Bar(at-timedelta(minutes=1),px,px+2,px-2,px,0,0)
        future[at]=replace(spot[at],volume=10000 if at>=stamp(DAY,'09:58') else 1000,oi=5000)
        at+=timedelta(minutes=1)
    return spot,future

def test_first_failed_break_signal_is_unchanged_by_future_prices():
    spot,future=fixture();a,_=scan(DAY,spot,future,{},[],DAY)
    assert a['FAILED_ORB']['side']=='PE' and a['FAILED_ORB']['at']==stamp(DAY,'10:00').isoformat()
    def corrupt(series):return {t:replace(b,open=D(1),high=D(1),low=D(1),close=D(1),volume=1) if t>stamp(DAY,'10:00') else b for t,b in series.items()}
    b,_=scan(DAY,corrupt(spot),corrupt(future),{},[],DAY)
    assert a['FAILED_ORB']==b['FAILED_ORB']

def test_missing_initial_range_does_not_become_no_trade():
    spot,future=fixture();del spot[stamp(DAY,'09:25')]
    signals,gaps=scan(DAY,spot,future,{},[],DAY)
    assert 'FAILED_ORB' not in signals and 'FAILED_ORB:MISSING_OPENING_RANGE' in gaps

def test_session_vwap_stops_at_missing_history():
    _,future=fixture();del future[stamp(DAY,'09:30')]
    v=vwap_series(future,DAY)
    assert stamp(DAY,'09:29') in v and stamp(DAY,'10:00') not in v

def test_compression_uses_past_range_and_requires_participation():
    spot,future=fixture()
    for t,b in list(spot.items()):
        px=D(24000) if t<stamp(DAY,'09:58') else D(24010)+(t-stamp(DAY,'09:58')).seconds//60
        spot[t]=replace(b,open=px,high=px+2,low=px-2,close=px)
        future[t]=replace(spot[t],volume=10000 if t>=stamp(DAY,'09:58') else 1000,oi=5000)
    signals,_=scan(DAY,spot,future,{},[],DAY)
    assert signals['COMPRESSION_BREAK']['at']==stamp(DAY,'10:00').isoformat()
    assert signals['COMPRESSION_BREAK']['side']=='CE'
    flat_volume={t:replace(b,volume=1000) for t,b in future.items()}
    other,_=scan(DAY,spot,flat_volume,{},[],DAY)
    assert 'COMPRESSION_BREAK' not in other

def test_wall_uses_frozen_prior_strike_and_rejects_missing_same_strike():
    spot,future=fixture();at=stamp(DAY,'10:00')
    for t,b in list(spot.items()):
        px=D(24000) if t<stamp(DAY,'09:59') else D(24020)+(t-stamp(DAY,'09:59')).seconds//60
        spot[t]=replace(b,open=px,high=px+2,low=px-2,close=px)
        future[t]=replace(spot[t],volume=1000,oi=5000)
    prior=[{'FinInstrmTp':'IDO','OptnTp':side,'XpryDt':DAY,'StrkPric':'24000','OpnIntrst':'10000'} for side in ('CE','PE')]
    options={(at,'CE',24000.):(13.,900.),(at-timedelta(minutes=3),'CE',24000.):(10.,1000.)}
    signals,_=scan(DAY,spot,future,options,prior,DAY)
    assert signals['PRIOR_OI_WALL']['at']==at.isoformat()
    wrong={(t,s,k+50):v for (t,s,k),v in options.items()}
    other,gaps=scan(DAY,spot,future,wrong,prior,DAY)
    assert 'PRIOR_OI_WALL' not in other
    assert any(g.startswith('PRIOR_OI_WALL:MISSING_SAME_STRIKE_OPTION') for g in gaps)
