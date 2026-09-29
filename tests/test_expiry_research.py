from datetime import timedelta
from decimal import Decimal as D
from dataclasses import replace
from research.gauntlet.core import Bar,Contract,Order,entry,make_order
from research.expiry.signals import stamp,spot_signals,option_signals
from research.expiry.replay import liquidate,choose,run

DAY='2026-07-21'

def bar(hm,o='20',h='21',l='19',c='20',v=100000,oi=100000):
    return Bar(stamp(DAY,hm),D(o),D(h),D(l),D(c),v,oi)

def contract(side='CE',strike='24000',key='a'):
    return Contract(key,'NIFTY',DAY,side,D(strike),65,D('.05'),1800,True)

def order(qty=65):
    return Order(contract(),stamp(DAY,'14:45'),D('21'),qty,'test',D('20'))

def fill(b,px='20'):
    return {'bar':b,'price':D(px),'time':b.start.isoformat(),'status':'MODELED_FILL'}

def test_signal_snapshot_rejects_future_bars():
    known=[bar('14:43'),bar('14:44'),bar('14:45')]
    import pytest
    with pytest.raises(ValueError):make_order(contract(),known,stamp(DAY,'14:45'),D('9411.18'),'x')

def test_limit_and_quantity_frozen_before_next_bar():
    o=order();f=entry(o,[bar('14:46',h='22')]);assert f['status']=='MODELED_LIMIT_MISS'
    f=entry(o,[bar('14:46',v=1000)]);assert f['status']=='MODELED_CAPACITY_MISS'
    assert o.quantity==65

def test_unknown_closest_option_cannot_skip_to_cheaper():
    c=contract();far=contract(strike='24050',key='b')
    x={'chain':[c,far],'errors':{'a':'UNKNOWN_VOLUME_MISMATCH'},'bars':{'b':[bar('14:42'),bar('14:43'),bar('14:44')]}}
    s={'at':stamp(DAY,'14:45').isoformat(),'side':'CE','spot':'24000','name':'x'}
    assert choose(x,s,D('9411.18'))[1]=='UNKNOWN_SELECTION_DATA'

def test_stop_beats_target_when_bar_order_is_ambiguous():
    b=bar('14:46');both=bar('14:47',h='45',l='8')
    r=liquidate(order(),fill(b),[b,both],'TARGET',stamp(DAY,'15:30'))
    assert r['reason']=='STOP' and r['price']==D('7.90')

def test_entry_bar_target_is_not_credited_and_stop_is_adverse():
    b=bar('14:46',h='45',l='8')
    r=liquidate(order(),fill(b),[b],'TARGET',stamp(DAY,'15:30'))
    assert r['reason']=='STOP'

def test_trailing_stop_uses_previous_completed_close_only():
    b=bar('14:46');jump=bar('14:47',h='43',l='12',c='42');after=bar('14:48',o='42',h='43',l='20',c='21')
    r=liquidate(order(),fill(b),[b,jump,after],'TRAIL',stamp(DAY,'15:30'))
    assert r['reason']=='STOP' and r['at']==after.available.isoformat()
    assert r['price']==D('19.80')

def test_stop_capacity_pending_not_fabricated_exit():
    b=bar('14:46');thin=bar('14:47',l='8',v=100);nextb=bar('14:48',l='5')
    r=liquidate(order(),fill(b),[b,thin,nextb],'TARGET',stamp(DAY,'15:30'))
    assert r['price']==D('4.95') and r['at']==nextb.available.isoformat()

def test_missing_holding_bar_does_not_become_zero():
    b=bar('14:46')
    r=liquidate(order(),fill(b),[b],'TARGET',stamp(DAY,'15:30'))
    assert r['status']=='UNKNOWN_HOLDING_BAR'

def test_target_needs_trade_through_and_begins_after_entry():
    b=bar('14:46');touch=bar('14:47',h='40.1');through=bar('14:48',h='40.8')
    r=liquidate(order(),fill(b),[b,touch,through],'TARGET',stamp(DAY,'15:30'))
    assert r['reason']=='TARGET_2X' and r['at']==through.available.isoformat()

def test_opening_range_signal_requires_two_completed_closes():
    start=stamp(DAY,'09:15');rows=[]
    while start<stamp(DAY,'15:24'):
        px=D('24010') if start>=stamp(DAY,'09:45') else D('24000')
        rows.append(Bar(start,px,px+1,px-1,px,0,0));start+=timedelta(minutes=1)
    sig,gaps,anchor=spot_signals(rows,DAY)
    assert sig['ORB30']['at']==stamp(DAY,'09:47').isoformat()
    assert sig['ORB30']['side']=='CE'
    changed=[replace(b,close=D('22000'),low=D('21900')) if b.start>=stamp(DAY,'12:00') else b for b in rows]
    assert spot_signals(changed,DAY)[0]['ORB30']==sig['ORB30']

def test_option_accel_compares_same_contract_and_past_volume():
    rows=[];at=stamp(DAY,'14:12')
    while at<stamp(DAY,'15:20'):
        last=at==stamp(DAY,'14:44')
        rows.append(Bar(at,D('20'),D('26'),D('19'),D('26') if last else D('20'),3000 if at>=stamp(DAY,'14:42') else 1000,90000 if last else 100000));at+=timedelta(minutes=1)
    sig,gap=option_signals({'CE':rows,'PE':[replace(b,close=D('20')) for b in rows]},DAY,D('24000'))
    assert sig['OPTION_ACCEL']['at']==stamp(DAY,'14:45').isoformat()
    assert sig['OPTION_ACCEL_OI']['side']=='CE'
    # A future favorable candle cannot repair the missing signal-time lookback.
    assert not option_signals({'CE':rows[1:],'PE':rows},DAY,D('24000'))[0]

def test_unknown_path_final_cash_null():
    r=run({DAY:{'partition':'development','error':'missing'}},'ORB30','TARGET','development')
    assert r['final_bankroll'] is None and r['resolved_cash']=='9411.18'

def test_whole_lot_cash_replay_and_best_trade_deletion():
    rows=[bar('14:42'),bar('14:43'),bar('14:44'),bar('14:45'),bar('14:46'),bar('14:47',h='43')]
    x={'partition':'development','chain':[contract()],'bars':{'a':rows},'errors':{},'gaps':[],
       'signals':{'TEST':{'name':'TEST','at':stamp(DAY,'14:45').isoformat(),'side':'CE','spot':'24000'}}}
    r=run({DAY:x},'TEST','TARGET','development')
    trade=r['ledger'][0]
    assert trade['quantity']%65==0 and D(r['final_bankroll'])>D('9411.18')
    assert D(trade['cash_after'])-D(trade['cash_before'])==D(trade['pnl'])
    assert (D(trade['exit'])-D(trade['entry']))*trade['quantity']-D(trade['fees'])==D(trade['pnl'])
    again=run({DAY:x},'TEST','TARGET','development')
    assert again==r  # Cached and uncached paths agree exactly.
    deleted=run({DAY:x},'TEST','TARGET','development',skip=DAY)
    assert deleted['final_bankroll']=='9411.18' and not deleted['counts'].get('trades')

def test_fast_sizing_matches_original_fee_and_freeze_boundaries():
    import random
    from research.expiry.fast_order import make_order as fast
    rng=random.Random(26)
    for i in range(240):
        px=D(rng.choice(['.05','.10','.50','1','20','118.25']))
        c=replace(contract(),lot=rng.choice([25,65,75]),freeze=1500)
        c=replace(c,freeze=c.freeze//c.lot*c.lot)
        cash=D(rng.choice(['-1','20','50','9411.18','50000','500000']))
        rows=[replace(bar(hm),open=px,high=px,low=px,close=px,volume=rng.randint(1,10000000)) for hm in ['14:42','14:43','14:44']]
        assert fast(c,rows,stamp(DAY,'14:45'),cash,str(i))==make_order(c,rows,stamp(DAY,'14:45'),cash,str(i))
