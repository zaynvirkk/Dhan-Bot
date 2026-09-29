from datetime import timedelta
from dataclasses import replace
import pytest
from research.gauntlet.core import Bar,Contract,Order,D
from research.expiry.signals import stamp
from research.broader.prepare import selectors,known_late_open
from research.broader.replay import cash_order,share_fee,trade
from research.broader.options import history_key

DAY='2026-06-17';NEXT='2026-06-18';AT=stamp(DAY,'15:10')

def test_published_special_session_is_not_a_missing_data_success():
    assert known_late_open('VEDL','2026-04-30',stamp('2026-04-30','09:30'))
    assert not known_late_open('VEDL','2026-04-30',stamp('2026-04-30','10:00'))
    assert not known_late_open('VEDL','2026-04-29',stamp('2026-04-29','09:30'))
    assert not known_late_open('OTHER','2026-04-30',stamp('2026-04-30','09:30'))

def test_expired_fetch_preserves_exact_token_and_expiry():
    c=Contract('NSE_FO|123','NIFTY','2026-09-22','CE',D(24000),65,D('.05'),1800,True)
    assert history_key(c,'2026-09-18')=='NSE_FO|123'
    assert history_key(c,'2026-09-27')=='NSE_FO|123|22-09-2026'
    assert history_key(replace(c,key='NSE_FO|123|22-09-2026'),'2026-09-27')=='NSE_FO|123|22-09-2026'

def history():
    rows=[]
    for i in range(21):
        day=(stamp('2026-05-01','09:15')+timedelta(days=i)).date().isoformat();price=D(100)+i
        r={'ISIN':'x','ClsPric':str(price),'PrvsClsgPric':str(price-1),'HghPric':str(price),'TtlTradgVol':'1000000','TtlTrfVal':'200000000'}
        rows.append({'day':day,'universe':['A'],'cash':{'A':r},'futures':{}})
    return rows

def test_ranking_uses_historical_membership_and_rejects_future():
    h=history();r=selectors(h,DAY)
    assert r['MOMENTUM20'][0]['symbol']=='A'
    for row in h:row['cash']['FUTURE_WINNER']={**row['cash']['A'],'ClsPric':'999999'}
    assert selectors(h,DAY)==r
    h[-1]['day']=DAY
    with pytest.raises(ValueError,match='future'):selectors(h,DAY)

def test_past_corporate_action_discontinuity_is_excluded():
    h=history();h[-1]['cash']['A']['PrvsClsgPric']='50'
    assert not any(selectors(h,DAY).values())

def bar(at,p='10',v=100000):
    p=D(p);return Bar(at,p,p,p,p,v,100000)

class Fake:
    days=[DAY,NEXT]
    def __init__(self):
        self.maps={}
        for d in self.days:
            self.maps[d]={stamp(d,'09:15')+timedelta(minutes=i):bar(stamp(d,'09:15')+timedelta(minutes=i)) for i in range(361)}
    def rows(self,s,c,d,quality):return self.maps[d]

def setup(cash=False):
    c=Contract('key','X',NEXT,'EQ' if cash else 'CE',D(100),1 if cash else 65,D('.1') if cash else D('.05'),10000,not cash)
    o=Order(c,AT,D('10.5'),10 if cash else 65,'x',D(10))
    s={'at':AT.isoformat(),'day':DAY,'exit_day':NEXT,'exit_at':stamp(NEXT,'09:30').isoformat(),'mode':'CASH1' if cash else 'INDEX'}
    return s,o,Fake()

def test_overnight_gap_is_charged_at_next_session_price():
    s,o,ds=setup()
    for t in ds.maps[NEXT]:ds.maps[NEXT][t]=bar(t,'1')
    r=trade(ds,s,o)
    assert r['reason']=='STOP_CLOSE' and D(r['exit_parts'][0]['price'])==D('.95')
    assert r['exit_parts'][0]['at']==stamp(NEXT,'09:17').isoformat()

def test_post_target_gap_does_not_guarantee_target_fill():
    s,o,ds=setup();ds.maps[NEXT][stamp(NEXT,'09:16')]=bar(stamp(NEXT,'09:16'),'25')
    r=trade(ds,s,o)
    assert r['reason']=='TARGET_CLOSE' and D(r['exit_parts'][0]['price'])<D(r['entry'])

def test_missing_holding_bar_is_unknown_not_free_cash():
    s,o,ds=setup();del ds.maps[NEXT][stamp(NEXT,'09:20')]
    with pytest.raises(ValueError,match='HOLDING'):trade(ds,s,o)

def test_no_entry_resize_and_capacity_failure():
    s,o,ds=setup();ds.maps[DAY][AT+timedelta(minutes=1)]=bar(AT+timedelta(minutes=1),'100')
    assert trade(ds,s,o)['status']=='LIMIT_MISS'
    ds.maps[DAY][AT+timedelta(minutes=1)]=bar(AT+timedelta(minutes=1),'10',1)
    assert trade(ds,s,o)['status']=='CAPACITY_MISS'

def test_cash_size_reserves_costs_and_exact_whole_shares():
    s,o,ds=setup(True);o,status=cash_order(o.contract,ds.maps[DAY],AT,D('9411.18'))
    assert status=='ORDER_CREATED' and isinstance(o.quantity,int)
    t=o.quantity*o.limit
    assert t+share_fee(t,'BUY')<=D('9411.18')*D('.95')
    assert t+share_fee(t,'BUY')+3*share_fee(D(0),'SELL')<=D('9411.18')

def test_partial_exit_cannot_disappear_and_is_bounded():
    s,o,ds=setup();o=replace(o,quantity=130)
    for i in range(3):
        t=stamp(NEXT,'09:30')+timedelta(minutes=i);ds.maps[NEXT][t]=bar(t,v=1300 if i<2 else 0)
    r=trade(ds,s,o);assert [p['quantity'] for p in r['exit_parts']]==[65,65]
    ds.maps[NEXT][stamp(NEXT,'09:31')]=bar(stamp(NEXT,'09:31'),v=0)
    with pytest.raises(ValueError,match='EXIT_CAPACITY'):trade(ds,s,o)
