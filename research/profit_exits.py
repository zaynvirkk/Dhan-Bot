"""Re-test fixed entry rules with causal, cost-aware profit protection.

Minute closes minus 1% are an adverse liquidation proxy, never a historical
bid. A floor uses only earlier completed closes. Unknown tapes stay unknown.
"""
import hashlib,json
from datetime import timedelta
from decimal import Decimal as D
from math import ceil
from pathlib import Path

from dhan_cas_bot.profit_exit import observe
from dhan_cas_bot.risk import FeeSchedule
from research.expiry.replay import liquidate,run
from research.gauntlet.core import tick_down
from research.gauntlet.data import save
from research.multifeature.replay import inputs,STRATEGIES,digest
from research.multifeature.collect import WINDOWS


def protected_liquidate(order,fill,bars,style,close_at):
    if not style.startswith('NET'):return liquidate(order,fill,bars,style,close_at)
    retain=D(style[3:])/100;by={b.start:b for b in bars};at=fill['bar'].start
    qty=order.quantity;remaining=qty;parts=[];pending=None;worst=fill['price'];state=None
    children=ceil(qty/order.contract.freeze);fees=FeeSchedule()
    debit=qty*fill['price']+fees.buy(qty*fill['price'],children)
    stop=tick_down(fill['price']*D('.5'),order.contract.tick)
    def net(px):return qty*px-fees.sell(qty*px,children)-debit
    while at<close_at:
        b=by.get(at)
        if b is None:return {'status':'UNKNOWN_HOLDING_BAR','at':at.isoformat(),'parts':parts}
        worst=min(worst,b.low)
        if not pending:
            if b.low<=stop:pending='STOP'
            elif state and state['floor'] is not None and net(tick_down(b.low*D('.99'),order.contract.tick))<=D(state['floor']):pending='NET_PROFIT_FLOOR'
            elif at>=close_at-timedelta(minutes=6):pending='TIMED_CLOSE'
        capacity=int(D(b.volume)*D('.05'))//order.contract.lot*order.contract.lot
        if at==fill['bar'].start:capacity=max(0,capacity-qty)
        if pending:
            sold=min(remaining,capacity)
            if sold:
                px=tick_down(b.low*D('.99'),order.contract.tick)
                parts.append({'quantity':sold,'price':str(px),'at':at.isoformat()});remaining-=sold
            if not remaining:return {'status':'MODELED_EXIT','at':b.available.isoformat(),
                'price':sum(D(p['price'])*p['quantity'] for p in parts)/qty,
                'parts':parts,'reason':pending,'worst':worst}
        else:
            px=tick_down(b.close*D('.99'),order.contract.tick)
            cost=fees.buy(qty*fill['price'],children)+fees.sell(qty*px,children)
            state=observe(net(px),cost,state,retain=retain)
        at+=timedelta(minutes=1)
    return {'status':'UNKNOWN_EXIT_CAPACITY','remaining':remaining,'at':at.isoformat(),'parts':parts}


def main():
    out=Path('research/results/profit_exits');runs=[];hashes={}
    own=hashlib.sha256(Path(__file__).read_bytes()+Path('dhan_cas_bot/profit_exit.py').read_bytes()).hexdigest()
    before=digest()
    for quality in ('reported','strict'):
        days,datahash,audits=inputs(quality);hashes[quality]=datahash
        for period in WINDOWS:
            for name in STRATEGIES:
                for style in ('TRAIL','TARGET','NET25','NET50','NET75'):
                    base=run(days,name,style,period,liquidator=protected_liquidate)
                    base.update(quality=quality,scenario='primary');runs.append(base)
                    for delay in (2,3):
                        r=run(days,name,style,period,delay=delay,liquidator=protected_liquidate)
                        r.update(quality=quality,scenario='delay'+str(delay));runs.append(r)
                    r=run(days,name,style,period,skip=base['best_trade_day'],liquidator=protected_liquidate)
                    r.update(quality=quality,scenario='delete_best');runs.append(r)
            print(quality,period,'complete',flush=True)
    if before!=digest() or own!=hashlib.sha256(Path(__file__).read_bytes()+Path('dhan_cas_bot/profit_exit.py').read_bytes()).hexdigest():
        raise RuntimeError('source drift during exit comparison')
    save(out/'comparison.json',{'source_hash':before,'exit_source_hash':own,'data_hashes':hashes,
        'windows':WINDOWS,'interpretation':'Retrospective minute-candle scenarios, not quote replay, causal probabilities or verified fills.',
        'runs':runs})
    for period in WINDOWS:
        print(period,[(r['strategy'],r['final_bankroll'],r['unknown']) for r in runs
            if r['period']==period and r['quality']=='reported' and r['scenario']=='primary'
            and r['strategy'].startswith('ORDINARY_PUBLISHED_PCR_')],flush=True)


if __name__=='__main__':main()
