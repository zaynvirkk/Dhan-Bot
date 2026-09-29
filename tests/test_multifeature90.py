from datetime import timedelta,date
from dataclasses import replace
from decimal import Decimal as D
import json
import pytest
from research.gauntlet.core import Bar,Contract
from research.expiry.signals import stamp
from research.multifeature.signals import scan_day,option_value,Missing,market_maps
from research.multifeature.collect import WINDOWS
from research.multifeature.providers import request
from research.multifeature.quality import tape_issues

DAY='2026-07-07'

def market():
    rows={};at=stamp(DAY,'09:16');i=0
    while at<=stamp(DAY,'15:10'):
        px=D(24000+i*2)
        rows[at]=Bar(at-timedelta(minutes=1),px,px+1,px-1,px,10000,100000+i*500)
        i+=1;at+=timedelta(minutes=1)
    chain=[Contract(str(k),'NIFTY',DAY,s,D(k),65,D('.05'),1800,True) for s in ('CE','PE') for k in range(23500,25001,50)]
    return rows,chain

def test_each_window_is_ninety_consecutive_calendar_days():
    for a,b in WINDOWS.values():assert (date.fromisoformat(b)-date.fromisoformat(a)).days+1==90
    assert date.fromisoformat(WINDOWS['earlier'][1])+timedelta(days=1)==date.fromisoformat(WINDOWS['recent'][0])

def test_off_tick_tape_is_unknown_even_when_daily_volume_reconciles():
    raw={'metadata':{'tick_size':5.0},'audit':{'status':'RECONCILED'}}
    bar=Bar(stamp(DAY,'10:00'),D('10'),D('11'),D('9'),D('10.05'),1000,5000)
    assert tape_issues(raw,[bar])==[]
    assert tape_issues(raw,[replace(bar,close=D('10.04'))])==['UNKNOWN_OFF_TICK_PRICE']
    assert tape_issues(raw,[replace(bar,close=D('12'))])==['UNKNOWN_INVALID_OHLC']
    assert tape_issues(raw,[bar,bar])==['UNKNOWN_DUPLICATE_BAR']

def test_no_order_or_alert_endpoints_in_data_client():
    for provider,path in [('dhan','/v2/orders'),('dhan','/v2/alerts'),('upstox','/v2/order/place'),('unknown','/v2/order/place')]:
        with pytest.raises(ValueError):request(provider,path,{'quantity':1})

def test_future_price_change_cannot_change_existing_first_signal():
    rows,chain=market();idx={s:rows for s in ('NIFTY','BANK','IT','VIX','GIFT')}
    a,_=scan_day(DAY,idx,rows,{},chain)
    assert a['FUTURE_TREND']['at']==stamp(DAY,'10:00').isoformat()
    changed={t:replace(b,open=D(1),high=D(1),low=D(1),close=D(1),oi=1) if t>stamp(DAY,'10:00') else b for t,b in rows.items()}
    b,_=scan_day(DAY,{s:changed for s in idx},changed,{},chain)
    assert a['FUTURE_TREND']==b['FUTURE_TREND']

def test_missing_earlier_input_is_not_repaired_by_later_signal():
    rows,chain=market();idx={s:rows for s in ('NIFTY','BANK','IT','VIX','GIFT')}
    future={k:v for k,v in rows.items() if k!=stamp(DAY,'09:45')}
    sig,gaps=scan_day(DAY,idx,future,{},chain)
    assert 'FUTURE_TREND' not in sig and any(g.startswith('FUTURE_TREND:') for g in gaps)

def test_relative_strike_roll_cannot_manufacture_oi_change():
    at=stamp(DAY,'10:00');options={(at,'CE',24050.):(10,5000,15),(at-timedelta(minutes=3),'CE',24000.):(2,10000,15)}
    with pytest.raises(Missing):option_value(options,at-timedelta(minutes=3),'CE',24050)

def test_oi_publication_lag_changes_first_eligible_signal():
    rows,chain=market();idx={s:rows for s in ('NIFTY','BANK','IT','VIX','GIFT')}
    future={t:replace(b,oi=110000 if t>=stamp(DAY,'10:00') else 100000) for t,b in rows.items()}
    a,_=scan_day(DAY,idx,future,{},chain)
    b,_=scan_day(DAY,idx,future,{},chain,lag=5)
    assert a['FUTURE_OI']['at']==stamp(DAY,'10:00').isoformat()
    assert b['FUTURE_OI']['at']==stamp(DAY,'10:05').isoformat()

def test_pcr_uses_bucket_delay_and_ignores_daily_summary(tmp_path,monkeypatch):
    import research.multifeature.signals as mod
    monkeypatch.setattr(mod,'STORE',tmp_path);(tmp_path/'api').mkdir()
    raw={'status':200,'path':'/v2/market/pcr?date='+DAY,'body':{'data':{'pcr':999,'spot_closing_price':1,'insights':[{'time':'09:15','pcr':.8}]}}}
    (tmp_path/'api/a.json').write_text(json.dumps(raw))
    insights,_=market_maps([DAY]);assert insights['pcr']=={(DAY,stamp(DAY,'09:20')):.8}

def test_institutional_data_waits_two_following_sessions(tmp_path,monkeypatch):
    import research.multifeature.signals as mod
    monkeypatch.setattr(mod,'STORE',tmp_path);(tmp_path/'api').mkdir()
    days=['2026-07-02','2026-07-03','2026-07-06','2026-07-07']
    for kind in ('fii','dii'):
        rows=[{'time_stamp':int(stamp(day,'00:00').timestamp()*1000),'total_long_contracts':100+i*10,'total_short_contracts':50,'buy_amount':10,'sell_amount':2} for i,day in enumerate(days)]
        (tmp_path/'api'/(kind+'.json')).write_text(json.dumps({'status':200,'path':'/v2/market/'+kind+'?from=2026-07-07','body':{'data':{'x':rows}}}))
    _,resolved=market_maps(days)
    assert resolved['2026-07-07']['source_date']=='2026-07-03'
    assert resolved['2026-07-07']['fii_net_change']==10
    assert '2026-07-03' not in resolved
