from dataclasses import replace
from datetime import timedelta
from research.gauntlet.core import Bar,Contract,Order,D,entry,cash_after
from research.expiry.signals import stamp
from research.intraday_challengers.experiment import liquidate,reserve,run
from research.intraday_challengers.signals import scan

DAY='2026-06-17'
AT=stamp(DAY,'10:00')

def bar(at,p='10',high=None,low=None,volume=100000):
    p=D(p)
    return Bar(at,p,D(high) if high else p,D(low) if low else p,p,volume,100000)

def setup(qty=65):
    c=Contract('x','NIFTY','2026-06-23','CE',D(23000),65,D('.05'),1755,True)
    o=Order(c,AT,D('10.5'),qty,'test',D(10))
    bars=[bar(AT+timedelta(minutes=i)) for i in range(1,39)]
    return o,bars,entry(o,bars)

def test_high_touch_does_not_manufacture_target():
    o,bars,f=setup();bars[3]=replace(bars[3],high=D(100))
    result=liquidate(o,f,bars,'FAST',DAY)
    assert result['reason']=='TIMED_CLOSE' and result['price']==D('9.90')

def test_completed_close_target_waits_for_latency_and_can_lose():
    o,bars,f=setup();bars[3]=bar(bars[3].start,'13')
    result=liquidate(o,f,bars,'FAST',DAY)
    assert result['reason']=='TARGET_CLOSE'
    assert result['parts'][0]['at']==(bars[3].available+timedelta(minutes=1)).isoformat()
    assert cash_after(D('9411.18'),o,f['price'],result['price'],result['parts'])[0]<D('9411.18')

def test_entry_bar_prior_low_cannot_trigger_stop():
    o,bars,f=setup();bars[0]=replace(bars[0],low=D(1));f=entry(o,bars)
    result=liquidate(o,f,bars,'FAST',DAY)
    assert result['reason']=='TIMED_CLOSE' and result['worst']==D(10)

def test_partial_exit_accounts_each_slice_and_unknown_not_flat():
    o,bars,f=setup(130)
    for i in (30,31):bars[i]=replace(bars[i],volume=1300)
    result=liquidate(o,f,bars,'FAST',DAY)
    assert [p['quantity'] for p in result['parts']]==[65,65]
    a,splitfee=cash_after(D('9411.18'),o,f['price'],result['price'],result['parts'])
    b,singlefee=cash_after(D('9411.18'),o,f['price'],result['price'])
    assert a<b and splitfee>singlefee
    for i in (30,31,32):bars[i]=replace(bars[i],volume=0)
    assert liquidate(o,f,bars,'FAST',DAY)['status']=='UNKNOWN_EXIT_CAPACITY'
    del bars[5]
    assert liquidate(o,f,bars,'FAST',DAY)['status']=='UNKNOWN_HOLDING_BAR'

def test_fixed_order_misses_without_resizing_to_later_prices():
    o,bars,f=setup();bars[0]=bar(bars[0].start,'100')
    assert entry(o,bars)['status']=='MODELED_LIMIT_MISS'
    assert o.quantity==65 and o.limit==D('10.5')

def test_exit_fee_reserve_can_reject_even_cheap_option():
    o,_,_=setup();o=replace(o,limit=D('.05'))
    assert reserve(o,D(50)) is None
    assert reserve(o,D(200))==o

def test_signal_prefix_is_invariant_to_future_and_future_revisions():
    spot={};future={}
    for i in range(376):
        at=stamp(DAY,'09:15')+timedelta(minutes=i)
        b=bar(at,str(23000+i*4));spot[b.available]=b;future[b.available]=replace(b,volume=100000)
    prior='2026-06-16';b=bar(stamp(prior,'15:29'),'23000');spot[b.available]=b
    whole,_=scan(DAY,spot,future,spot,spot,prior)
    assert whole['OPEN_DRIVE']['at']==stamp(DAY,'09:45').isoformat()
    limit=stamp(DAY,'10:00')
    prefix=lambda m:{t:b for t,b in m.items() if t<=limit}
    short,_=scan(DAY,prefix(spot),prefix(future),prefix(spot),prefix(spot),prior)
    assert {k:v for k,v in whole.items() if v['at']<=limit.isoformat()}==short
    changed={t:replace(b,open=D(1),high=D(999999),low=D(1),close=D(999999)) if t>limit else b for t,b in spot.items()}
    changed_signals,_=scan(DAY,changed,future,changed,changed,prior)
    assert {k:v for k,v in changed_signals.items() if v['at']<=limit.isoformat()}==short

def test_missing_signal_is_unknown_not_no_trade_and_no_winner_deletion_on_loss():
    days={DAY:{'partition':'recent','signals':{},'gaps':{'OPEN_DRIVE':'MISSING_BAR'}}}
    r=run(days,'OPEN_DRIVE','FAST','recent')
    assert r['final_bankroll'] is None and r['best_trade_day'] is None
    days[DAY]['gaps']={}
    assert run(days,'OPEN_DRIVE','FAST','recent')['final_bankroll']=='9411.18'
