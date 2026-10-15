"""Delayed displayed-depth scenarios. This module has no broker capability."""
from datetime import datetime, timedelta
from decimal import Decimal as D
from .risk import FeeSchedule
from .seconds_strategies import NAMES, current, entry_candidate
from .domain import json_safe
from .profit_exit import observe


class PaperLab:
    def __init__(self, bankroll, *, delay_seconds=1, saved=None):
        if not isinstance(bankroll,D) or not bankroll.is_finite() or bankroll<=0:raise ValueError('positive model bankroll required')
        if not 0<delay_seconds<=5:raise ValueError('bounded positive delay required')
        self.delay=timedelta(seconds=delay_seconds);self.initial=bankroll
        self.rows={n:{'cash':str(bankroll),'net':'0','signals':0,'entries':0,'closed':0,'missed':0,
                      'pending':None,'position':None,'last_episode':None,'last_result':'NO_MODEL_TRADE'} for n in NAMES}
        self.events=[]
        if saved is not None:
            if saved.get('schema')!=1 or set(saved.get('rows',{}))!=set(NAMES):raise ValueError('invalid paper history')
            self.rows=saved['rows'];self.initial=D(saved['initial']);self.events=saved['events'][-100:]
            for row in self.rows.values():
                if not D(row['cash']).is_finite() or not D(row['net']).is_finite():raise ValueError('invalid paper money')

    def event(self,name,at,kind,**facts):
        self.events.append(json_safe({'strategy':name,'at':at,'kind':kind,**facts}));self.events=self.events[-100:]

    def step(self, at, samples, books, future):
        fee=FeeSchedule()
        for name,row in self.rows.items():
            pending=row['pending'];position=row['position']
            if pending:
                due=datetime.fromisoformat(pending['due'])
                if at<due:continue
                b=books.get(pending['security_id'])
                if not current(b,at):
                    row['last_result']='ARRIVAL_QUOTE_UNAVAILABLE'
                    if not position and at>due+timedelta(seconds=2):
                        row['pending']=None;row['missed']+=1
                    continue
                q=pending['quantity'];limit=D(pending['limit'])
                if pending['side']=='BUY':
                    sample=samples.get(name)
                    eligible=sample and sample.state=='SIGNAL' and sample.details.get('episode')==row['last_episode']
                    if (not eligible or b.top_ask.price>limit or b.top_ask.quantity<q*2
                            or at>due+timedelta(seconds=2)):
                        row['missed']+=1;row['pending']=None;row['last_result']='LIMIT_OR_SIGNAL_MISS'
                        self.event(name,at,'MODEL_MISS');continue
                    debit=limit*q+fee.buy(limit*q,1)
                    if debit+fee.sell(D(pending['target'])*q,3)>D(row['cash'])*D('.95'):
                        row['missed']+=1;row['pending']=None;row['last_result']='MODEL_UNAFFORDABLE';continue
                    row['cash']=str(D(row['cash'])-debit);row['entries']+=1
                    row['position']={'security_id':b.instrument.security_id,'quantity':q,'entry':str(limit),
                        'debit':str(debit),'target':pending['target'],'opened_at':at.isoformat(),
                        'deadline':pending['deadline'],'anchor_future':pending['anchor_future'],
                        'direction':pending['direction'],'guard':None}
                    row['pending']=None;row['last_result']='SIMULATED_POSITION'
                    self.event(name,at,'MODEL_ENTRY',quantity=q,price=limit)
                else:
                    if b.top_bid.price>=limit and b.top_bid.quantity>=q*2:
                        proceeds=limit*q-fee.sell(limit*q,1);pnl=proceeds-D(position['debit'])
                        row['cash']=str(D(row['cash'])+proceeds);row['net']=str(D(row['net'])+pnl)
                        row['closed']+=1;row['position']=row['pending']=None;row['last_result']='MODEL_CLOSED'
                        self.event(name,at,'MODEL_EXIT',quantity=q,price=limit,net=pnl)
                    else:
                        row['missed']+=1;row['last_result']='EXIT_LIMIT_MISS'
                        row['pending']={**pending,'limit':str(max(b.instrument.tick_size,b.top_bid.price-2*b.instrument.tick_size)),
                                        'due':(at+self.delay).isoformat()}
                continue
            if position:
                b=books.get(position['security_id'])
                if not current(b,at) or b.top_bid.quantity<position['quantity']*2:
                    row['last_result']='OPEN_MODEL_POSITION_QUOTE_UNAVAILABLE';continue
                q=position['quantity'];price=max(b.instrument.tick_size,b.top_bid.price-2*b.instrument.tick_size)
                costs=fee.buy(D(position['entry'])*q,1)+fee.sell(price*q,3)
                net=price*q-fee.sell(price*q,3)-D(position['debit'])
                position['guard']=observe(net,costs,position['guard'])
                direction=D(position['direction']);anchor=D(position['anchor_future'])
                invalid=future is None or direction*(future-anchor)<-anchor*D('.0001')
                if (b.top_bid.price>=D(position['target']) or b.top_bid.price<=D(position['entry'])*D('.95')
                        or invalid or position['guard']['triggered'] or at>=datetime.fromisoformat(position['deadline'])):
                    row['pending']={'side':'SELL','security_id':b.instrument.security_id,'quantity':q,
                                    'limit':str(price),'due':(at+self.delay).isoformat()}
                    row['last_result']='SIMULATED_EXIT_PENDING'
                continue
            sample=samples.get(name)
            if not sample or sample.state!='SIGNAL' or sample.details['episode']==row['last_episode']:continue
            row['last_episode']=sample.details['episode'];row['signals']+=1
            candidate=entry_candidate(sample,books,D(row['cash'])*D('.95'),at)
            if candidate is None:
                row['last_result']='MODEL_EXECUTION_CHECK_FAILED';continue
            inst,q,limit,b=candidate
            row['pending']={'side':'BUY','security_id':inst.security_id,'quantity':q,'limit':str(limit),
                'target':sample.details['target_price'],'anchor_future':sample.details['anchor_future'],
                'direction':sample.details['direction'],'deadline':sample.exit_at.isoformat(),'due':(at+self.delay).isoformat()}
            row['last_result']='SIMULATED_ENTRY_PENDING';self.event(name,at,'MODEL_SIGNAL')

    def saved(self):
        return {'schema':1,'initial':str(self.initial),'rows':self.rows,'events':self.events}

    def view(self):
        return {'mode':'SIMULATION','writes_to_broker':False,'initial_bankroll':str(self.initial),
            'delay_seconds':self.delay.total_seconds(),
            'results':[{'strategy':name,**{key:row[key] for key in ('cash','net','signals','entries','closed','missed','last_result')},
                        'open_position':row['position'] is not None} for name,row in self.rows.items()],
            'events':self.events[-20:]}
