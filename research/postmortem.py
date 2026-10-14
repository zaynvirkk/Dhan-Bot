"""Causal displayed-depth counterfactuals, not broker execution receipts."""
from decimal import Decimal as D
from dhan_cas_bot.profit_exit import observe
from dhan_cas_bot.risk import FeeSchedule


def sale(quote,quantity,limit=None):
    remaining=quantity;turn=D(0)
    for price,available in quote.get('bid',[]):
        price=D(price)
        if limit is not None and price<limit:continue
        q=min(remaining,int(available));turn+=q*price;remaining-=q
        if remaining==0:return turn
    return None


def exit_scenario(quotes,quantity,entry,start_ns,end_ns,retain,delay_seconds):
    fees=FeeSchedule();debit=entry*quantity+fees.buy(entry*quantity,1);state=None
    eligible=[q for q in quotes if start_ns<=q['received_ns']<=end_ns]
    if any(b['received_ns']<=a['received_ns'] for a,b in zip(eligible,eligible[1:])):
        raise ValueError('quotes must have strictly increasing receipts')
    for q in eligible:
        turnover=sale(q,quantity)
        if turnover is None:continue
        adverse=turnover-quantity*D('.10')
        exit_cost=fees.sell(adverse,3)
        net=adverse-exit_cost-debit
        state=observe(net,fees.buy(entry*quantity,1)+exit_cost,state,retain=retain)
        if not state['triggered']:continue
        trigger=q['received_ns'];due=trigger+int(delay_seconds*10**9)
        arrival=next((x for x in eligible if x['received_ns']>=due),None)
        out={'trigger_ns':trigger,'peak':state['peak'],'floor':state['floor'],'delay_seconds':delay_seconds}
        if not arrival or arrival['received_ns']-due>2*10**9:
            return {**out,'status':'UNKNOWN_ARRIVAL_QUOTE'}
        limit=D(q['bid'][0][0])-D('.10');proceeds=sale(arrival,quantity,limit)
        out['arrival_ns']=arrival['received_ns'];out['limit']=str(limit)
        if proceeds is None:return {**out,'status':'LIMIT_MISS'}
        return {**out,'status':'DISPLAYED_DEPTH_SCENARIO','exit_price':str(proceeds/quantity),
                'net':str(proceeds-fees.sell(proceeds,1)-debit)}
    return {'status':'NO_PROFIT_TRIGGER'}


def session_stop(closed_net,retain):
    if not isinstance(retain,D) or not retain.is_finite() or not 0<retain<1:
        raise ValueError('invalid retention')
    total=peak=D(0);floor=None
    for n,value in enumerate(closed_net,1):
        if not isinstance(value,D) or not value.is_finite():raise ValueError('invalid realised net')
        total+=value;peak=max(peak,total)
        if peak>0:floor=peak*retain
        if floor is not None and total<=floor:
            return {'closed_through':n,'net':str(total),'floor':str(floor),'stopped':True}
    return {'closed_through':len(closed_net),'net':str(total),'floor':str(floor) if floor is not None else None,'stopped':False}
