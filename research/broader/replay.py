"""Overnight and stock-universe paths with delayed fills and unknown states."""
import argparse,hashlib,json,random
from collections import Counter
from datetime import datetime,timedelta
from decimal import ROUND_CEILING
from functools import lru_cache
from math import ceil
from pathlib import Path
from research.gauntlet.core import Bar,Contract,Order,D,tick_up,tick_down,entry
from research.gauntlet.data import CACHE,ROOT,save
from research.expiry.fast_order import make_order
from research.intraday_challengers.experiment import reserve
from research.expiry.signals import stamp
from dhan_cas_bot.risk import FeeSchedule
from .prepare import STORE,OUT,STOCK,NIFTY,calendar
from .options import pull_contract,option_day

START=D('9411.18')
NAMES=tuple(n+'_'+m for n in STOCK for m in ('CASH1','CASH5','CALL5'))+tuple('NIFTY_'+n+'_'+t for n in NIFTY for t in ('0930','1510'))

def digest():
    files=[Path(__file__),Path(__file__).with_name('prepare.py'),Path(__file__).with_name('options.py'),Path(__file__).with_name('PROTOCOL.md')]
    files += [ROOT/p for p in ('research/gauntlet/core.py','research/expiry/fast_order.py','research/intraday_challengers/experiment.py','dhan_cas_bot/risk.py')]
    return hashlib.sha256(b''.join(str(p.relative_to(ROOT)).encode()+p.read_bytes() for p in sorted(files))).hexdigest()

def upper(v,q='.01'):return v.quantize(D(q),rounding=ROUND_CEILING)

def share_fee(turn,side,dp=True):
    base=upper(turn*D('.000030699'))+upper(turn*D('.000001'))+upper(turn*D('.000000001'))
    return base+upper(base*D('.18'))+upper(turn*D('.001'),'1')+(upper(turn*D('.00015'),'1') if side=='BUY' else D('14.75') if dp else D(0))

def fee(turn,side,c,cash,quantity,dp=True):
    if cash:return share_fee(turn,side,dp)
    f=FeeSchedule();return (f.buy if side=='BUY' else f.sell)(turn,ceil(quantity/c.freeze))

class Dataset:
    def __init__(self,network=True):
        self.plan=json.loads((STORE/'signals.json').read_text());self.contracts=json.loads((STORE/'contracts.json').read_text()) if (STORE/'contracts.json').exists() else {}
        self.days=calendar();self.network=network;self.used=set();self.audit={};self._stocks={};self._daily={};self._loaded=set();self._option={};self._marks={}
        self.bans={}
        for p in (CACHE/'ban_lists.json',CACHE/'event90/ban_lists.json',STORE/'ban_lists.json'):
            if p.exists():self.bans.update(json.loads(p.read_text()))
    def daily(self,d):
        if d not in self._daily:self._daily[d]=json.loads((STORE/'daily'/f'{d}.json').read_text())
        return self._daily[d]
    def stocks(self,symbol):
        if symbol not in self._stocks:
            f=STORE/'underlying'/f'{symbol}.json';self.used.add(f);raw=json.loads(f.read_text())
            self._stocks[symbol]={b.start:b for b in map(Bar.parse,raw['bars'])}
        return self._stocks[symbol]
    def stock_audit(self,symbol,d):
        key=symbol+' '+d
        if key in self.audit:return self.audit[key]
        rows=[b for t,b in self.stocks(symbol).items() if t.date().isoformat()==d];off=self.daily(d)['cash'].get(symbol);issues=[]
        if off is None or not rows:issues.append('MISSING_STOCK_OFFICIAL_OR_BARS')
        else:
            if sum(b.volume for b in rows)!=int(off['TtlTradgVol']):issues.append('CASH_VOLUME_MISMATCH')
            if abs(max(b.high for b in rows)/D(off['HghPric'])-1)>D('.001') or abs(min(b.low for b in rows)/D(off['LwPric'])-1)>D('.001'):issues.append('CASH_RANGE_MISMATCH')
        self.audit[key]=issues;return issues
    def discontinuity(self,symbol,d):
        i=self.days.index(d);old=self.daily(self.days[i-1])['cash'].get(symbol);now=self.daily(d)['cash'].get(symbol)
        return (not old or not now or old['ISIN']!=now['ISIN'] or D(now['PrvsClsgPric'])<=0 or abs(D(old['ClsPric'])/D(now['PrvsClsgPric'])-1)>D('.005'))
    def options(self,c,d,end):
        if (c.key,d) not in self._option:
            if self.network:pull_contract(c,d,end)
            rows,issues=option_day(c.key,d,c.tick);self._option[c.key,d]={b.start:b for b in rows}
            self.audit[c.key+' '+d]=issues
            from research.gauntlet.option_history import day_path
            self.used.add(day_path(c.key,d))
        return self._option[c.key,d]
    def rows(self,s,c,d,quality):
        if s['mode'].startswith('CASH'):
            if self.discontinuity(s['symbol'],d):raise ValueError('UNKNOWN_CORPORATE_ACTION_OR_IDENTITY')
            issues=self.stock_audit(s['symbol'],d);rows=self.stocks(s['symbol'])
        else:
            if s['mode']=='CALL5' and self.discontinuity(s['symbol'],d):raise ValueError('UNKNOWN_CORPORATE_ACTION_OR_IDENTITY')
            rows=self.options(c,d,s['exit_day']);issues=self.audit[c.key+' '+d]
        if quality=='strict' and issues:raise ValueError('UNKNOWN_SOURCE_AUDIT:'+','.join(issues))
        return rows

def cash_order(c,rows,at,cash):
    recent=[rows.get(at-timedelta(minutes=i)) for i in (3,2,1)]
    if any(b is None for b in recent):return None,'UNKNOWN_DECISION_BAR'
    lim=tick_up(recent[-1].close*D('1.005'),c.tick)
    q=min(int(cash*D('.95')/lim),int(D(min(b.volume for b in recent))*D('.01')))
    while q:
        if lim*q+share_fee(lim*q,'BUY')<=cash*D('.95') and lim*q+share_fee(lim*q,'BUY')+3*share_fee(D(0),'SELL')<=cash:
            return Order(c,at,lim,q,'shares',recent[-1].close),'ORDER_CREATED'
        q-=1
    return None,'UNAFFORDABLE_OR_LIQUIDITY'

def select(ds,s,cash,quality,side):
    at=datetime.fromisoformat(s['at']);trace=[]
    if s['mode'].startswith('CASH'):
        c=Contract(s['key'],s['symbol'],'','EQ',D(0),1,D('.10'),100000,False)
        rows=ds.rows(s,c,s['day'],quality);o,status=cash_order(c,rows,at,cash)
        return o,status,trace
    key='|'.join((s['day'],s['symbol'],s['exit_day'],side));raw=ds.contracts.get(key)
    if raw is None or 'error' in raw:raise ValueError('UNKNOWN_CONTRACT_SELECTION')
    for m in raw['contracts']:
        if 'unresolved_key' in m:raise ValueError('MISSING_EXACT_METADATA:'+m['unresolved_key'])
        c=Contract.parse(m);rows=ds.rows(s,c,s['day'],quality)
        recent=[rows.get(at-timedelta(minutes=i)) for i in (3,2,1)]
        if any(b is None for b in recent):raise ValueError('UNKNOWN_DECISION_BARS')
        o,status=make_order(c,recent,at,cash,s['name']);trace.append({'key':c.key,'status':status})
        if o:
            o=reserve(o,cash)
            if o:
                if s['mode']=='CALL5':
                    ban=ds.bans.get(s['day'],{})
                    if ban.get('status')!='VERIFIED_DATE':raise ValueError('UNKNOWN_BAN_LIST')
                    if s['symbol'] in ban['symbols']:return None,'KNOWN_BANNED',trace
                return o,'ORDER_CREATED',trace
    return None,'NO_AFFORDABLE_CONTRACT',trace

def trade(ds,s,o,quality='reported',delay=1,slip=1):
    cash=s['mode'].startswith('CASH');participation=D('.01') if cash else D('.05');c=o.contract
    rows=ds.rows(s,c,s['day'],quality);when=o.decided+timedelta(minutes=delay);b=rows.get(when)
    if b is None:raise ValueError('UNKNOWN_ENTRY_BAR')
    px=tick_up(b.high*(1+D('.001')*slip) if cash else b.high,c.tick)
    if px>o.limit:return {'status':'LIMIT_MISS'}
    if D(o.quantity)>b.volume*participation:return {'status':'CAPACITY_MISS'}
    start=when;scheduled=datetime.fromisoformat(s['exit_at']);exit_at=scheduled;reason='TIMED_CLOSE'
    target=px*(D('1.2') if cash else 2);stop=px*(D('.9') if cash else D('.5'))
    remaining=o.quantity;parts=[];at=start;low=px;peak=px;markdd=D(0);currentday=s['day'];pending=False
    end_index=ds.days.index(s['exit_day'])
    while True:
        d=at.date().isoformat()
        if at.strftime('%H:%M')>'15:15':
            i=ds.days.index(d)
            if i>=end_index:raise ValueError('UNKNOWN_EXIT_AFTER_DEADLINE')
            at=stamp(ds.days[i+1],'09:15');d=at.date().isoformat()
        if d!=currentday:currentday=d;rows=ds.rows(s,c,d,quality)
        b=rows.get(at)
        if b is None:raise ValueError('UNKNOWN_HOLDING_BAR:'+at.isoformat())
        if at>start:low=min(low,b.low);peak=max(peak,b.high);markdd=max(markdd,1-b.low/peak)
        if at>=exit_at:
            if at>exit_at+timedelta(minutes=2):raise ValueError('UNKNOWN_EXIT_CAPACITY')
            q=min(remaining,int(D(b.volume)*participation)//c.lot*c.lot)
            if q:
                p=tick_down(b.low*(1-(D('.001') if cash else D('.01'))*slip),c.tick)
                parts.append({'at':at.isoformat(),'quantity':q,'price':str(p)});remaining-=q
            if not remaining:
                return {'status':'RESOLVED','entry':str(px),'entry_at':start.isoformat(),'exit_at':b.available.isoformat(),'exit_parts':parts,'reason':reason,'worst':str(low),'premium_drawdown':str(markdd)}
        elif not pending and (b.close>=target or b.close<=stop):
            proposed=b.available+timedelta(minutes=delay)
            if proposed<exit_at:exit_at=proposed;reason='TARGET_CLOSE' if b.close>=target else 'STOP_CLOSE';pending=True
        at+=timedelta(minutes=1)

def run(ds,name,period,quality='reported',delay=1,slip=1,skip=None,seed=None):
    cash=START;peak=cash;dd=D(0);busy='';ledger=[];counts=Counter();unknown=None;best=None;bestp=D(0);rng=random.Random(seed)
    for day,x in sorted(ds.plan.items()):
        if x['partition']!=period:continue
        counts['sessions']+=1
        if busy and day<=busy:counts['position_or_settlement_busy']+=1;continue
        if name in x['errors']:unknown=[day,x['errors'][name]];break
        if name in x.get('unavailable',{}):counts['known_session_unavailable']+=1;continue
        s=x['signals'].get(name)
        if not s:counts['no_signal']+=1;continue
        counts['signals']+=1
        if day==skip:counts['deleted_best']+=1;continue
        side=s['side'] if seed is None else rng.choice(['CE','PE']);row={'day':day,'signal_at':s['at'],'symbol':s['symbol'],'side':side,'cash_before':str(cash)}
        try:
            o,status,trace=select(ds,s,cash,quality,side);row.update(status=status,selection=trace)
            if status.startswith('UNKNOWN'):raise ValueError(status)
            if not o:counts['no_order']+=1;ledger.append(row);continue
            row.update(contract=o.contract.key,lot=o.contract.lot,freeze=o.contract.freeze,quantity=o.quantity,limit=str(o.limit),mode=s['mode'])
            result=trade(ds,s,o,quality,delay,slip);row.update(result)
            if result['status']!='RESOLVED':counts['misses']+=1;ledger.append(row);continue
            buy=D(result['entry'])*o.quantity;sell=sum((D(p['price'])*p['quantity'] for p in result['exit_parts']),D(0));is_cash=s['mode'].startswith('CASH')
            cost=fee(buy,'BUY',o.contract,is_cash,o.quantity)
            for j,p in enumerate(result['exit_parts']):cost+=fee(D(p['price'])*p['quantity'],'SELL',o.contract,is_cash,p['quantity'],dp=j==0)
            after=cash-buy+sell-cost;pnl=after-cash
            if after<0:raise ValueError('UNKNOWN_NEGATIVE_CASH')
            counts['trades']+=1;counts['wins' if pnl>0 else 'losses']+=1
            if pnl>bestp:bestp=pnl;best=day
            mark=cash-buy+D(result['worst'])*o.quantity-cost;dd=max(dd,1-mark/peak,1-after/peak)
            cash=after;peak=max(peak,cash);busy=result['exit_at'][:10]
            row.update(cash_after=str(cash),pnl=str(pnl),fees=str(cost));ledger.append(row)
        except Exception as e:
            row['status']='UNKNOWN';row['error']=type(e).__name__+':'+str(e);ledger.append(row);unknown=[day,row['error']];break
    return {'strategy':name,'period':period,'quality':quality,'delay':delay,'slip_multiplier':slip,'final_bankroll':None if unknown else str(cash.quantize(D('.01'))),
            'resolved_cash':str(cash),'unknown':unknown,'counts':dict(counts),'model_drawdown':str(dd),'best_trade_day':best,'ledger':ledger}

def evaluate(group):
    ds=Dataset();runs=[];names=[n for n in NAMES if (group=='cash' and '_CASH' in n) or (group=='options' and '_CASH' not in n)]
    for name in names:
        for period in ('earlier','recent'):
            b=run(ds,name,period);b['scenario']='primary';runs.append(b)
            for label,kw in [('delay3',{'delay':3}),('slippage2',{'slip':2}),('delete_best',{'skip':b['best_trade_day']}),('strict',{'quality':'strict'})]:
                r=run(ds,name,period,**kw);r['scenario']=label;runs.append(r)
            save(OUT/(group+'_progress.json'),{'source_sha256':digest(),'runs':runs})
            print(name,period,b['final_bankroll'],b['counts'].get('trades',0),b['unknown'],flush=True)
    paths=sorted(ds.used|set((STORE/'daily').glob('*.json'))|{STORE/'signals.json',STORE/'ranks.json',CACHE/'expiry_research/spot.json'}|
                 {p for p in (CACHE/'ban_lists.json',CACHE/'event90/ban_lists.json',STORE/'ban_lists.json',CACHE/'public/CMTR73856.pdf') if p.exists()})
    if group=='options':paths+=[STORE/'contracts.json']
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    save(OUT/(group+'.json'),{'source_sha256':digest(),'input_hashes':hashes,'audit':ds.audit,'runs':runs})

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('group',choices=['cash','options']);a=p.parse_args();evaluate(a.group)
