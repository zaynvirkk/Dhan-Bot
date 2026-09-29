"""Fast bankroll controls, checked for exact parity with the original replay."""
import json
import random
from dataclasses import dataclass
from datetime import datetime,timedelta,timezone
from decimal import Decimal as D
from functools import lru_cache

from research.gauntlet.data import CACHE,save
from research.gauntlet.core import Bar,Contract,make_order,entry,exit_trade,cash_after
from research.gauntlet.provenance import source_manifest,digest
from research.gauntlet.replay import SOURCES
from research.noise.compile import NOISE

START=D('9411.18')

class Runner:
    def __init__(self,engine,compiled_file=None):
        self.engine=engine
        self.compiled_file=compiled_file or NOISE/(engine+'_compiled.json')
        self.source=json.loads(self.compiled_file.read_text())
        assert self.source['source_sha']==source_manifest()['sha256']
        assert self.source['input_sha']==digest(CACHE/self.source.get('input_path',SOURCES[engine]))
        from research.noise import compile
        assert self.source['compiler_sha']==digest(compile.__file__)
        assert self.source['ban_sha']==digest(CACHE/'ban_lists.json')
        self.bans=json.loads((CACHE/'ban_lists.json').read_text())
        self.items={}
        for raw in self.source['observations']:
            s=raw['signal'];at=datetime.fromisoformat(s['at'])
            items=[]
            for original in raw['contracts']:
                item=dict(original)
                item['has_bars']='bars' in original
                bars=tuple(sorted((Bar.parse(r) for r in item.get('bars',[])),key=lambda b:b.start))
                item['bars']=bars
                item['known']=tuple(b for b in bars if b.available<=at)[-3:]
                if 'contract' in item:
                    c=dict(item['contract'])
                    for field in ('strike','tick'):c[field]=D(c[field])
                    item['contract']=Contract(**c)
                items.append(item)
            self.items[(s['id'],s['side'])]={**raw,'at':at,'contracts':items,
                'invalid_at':datetime.fromisoformat(raw['invalid_at']) if raw.get('invalid_at') else None}

    @lru_cache(maxsize=65536)
    def outcome(self,signal_id,side,contract_index,quantity,limit,delay,adverse):
        from research.gauntlet.core import Order
        data=self.items[(signal_id,side)];item=data['contracts'][contract_index];at=data['at']
        c=item['contract'];bars=item['bars'];known=item['known']
        order=Order(c,at,limit,quantity,signal_id,known[-1].close)
        fill=entry(order,bars,delay,D('.05'),adverse)
        if fill['status']!='MODELED_FILL':return {'status':fill['status']}
        invalid=data['invalid_at']
        if invalid is not None and invalid<=fill['bar'].start:return {'status':'INVALIDATED_BEFORE_DISPATCH'}
        close=at.replace(hour=15,minute=17,second=0,microsecond=0)
        result=exit_trade(order,fill,bars,invalid,close,D('.05'),7)
        if result['status']!='MODELED_EXIT':return {'status':result['status']}
        pnl,fees=cash_after(D(0),order,fill['price'],result['price'],result.get('parts'))
        return {'status':'MODELED_ROUND_TRIP','pnl':pnl,'fees':fees,'entry_price':fill['price'],
                'exit_price':result['price'],'exit_time':result['time'],'target':result['reason']=='TARGET_2X',
                'quantity':quantity,'key':c.key}

    def run(self,seed=None,strict=False,delay=1,adverse=True):
        rng=random.Random(seed);cash=START;busy=None;gaps=0;stopped=False;ledger=[];peak=cash;dd=D(0)
        for original in self.source['signals']:
            side=rng.choice(('CE','PE')) if seed is not None else original['side']
            data=self.items[(original['id'],side)];s=data['signal'];at=data['at']
            row={'id':s['id'],'side':side,'cash_before':str(cash)}
            status=None
            ban=self.bans.get(s['at'][:10],{})
            if ban.get('status')!='VERIFIED_DATE':status='UNKNOWN_BAN_FILE';gaps+=1
            elif s['symbol'] in ban['symbols']:status='EXCHANGE_NEW_POSITION_BAN'
            elif busy is not None and at<busy:status='POSITION_ALREADY_OPEN'
            elif s['materiality'] not in ('QUALIFYING_TEXT','NOT_REQUIRED'):status='OUTSIDE_METADATA_VARIANT'
            elif s['futures_confirmation'] not in ('CONFIRMED','NOT_REQUIRED'):status='UNKNOWN_FUTURE_CONFIRMATION';stopped=True
            if status:
                row['status']=status;ledger.append(row)
                if stopped or strict and status.startswith('UNKNOWN'):stopped=True;break
                continue
            if data.get('error'):
                row.update(status='UNKNOWN_DATA_ERROR',error=data['error']);gaps+=1;ledger.append(row)
                if strict:stopped=True;break
                continue
            if not data['contracts']:
                row['status']='NO_ELIGIBLE_CONTRACT_IN_PRIOR_FILE';ledger.append(row);continue
            selected=None;error=None;before=gaps
            for i,item in enumerate(data['contracts']):
                if item.get('skip'):continue
                if item.get('audit',{}).get('status','').startswith('UNKNOWN'):gaps+=1
                if item['has_bars'] and not item['known']:
                    gaps+=1
                    if strict:error='UNKNOWN_OPTION_HISTORY';break
                    continue
                if item.get('error'):gaps+=1;error=item['error'];break
                if strict and gaps>before:error='UNKNOWN_OPTION_HISTORY';break
                order,_=make_order(item['contract'],item['known'],at,cash,s['id'])
                if order:selected=(i,order);break
            if error:
                row.update(status='UNKNOWN_DATA_ERROR',error=error);ledger.append(row)
                if strict:stopped=True;break
                continue
            if selected is None:
                row['status']='NO_ORDER_UNDER_MODEL';ledger.append(row);continue
            i,order=selected
            out=self.outcome(s['id'],side,i,order.quantity,order.limit,delay,adverse)
            row['status']=out['status']
            if out['status'].startswith('UNKNOWN'):
                ledger.append(row);stopped=True;break
            if out['status']=='MODELED_ROUND_TRIP':
                cash+=out['pnl'];busy=datetime.fromisoformat(out['exit_time'])+timedelta(minutes=1)
                row.update(cash_after=str(cash),pnl=str(out['pnl']),target=out['target'],
                           quantity=out['quantity'],key=out['key'])
                peak=max(peak,cash);dd=max(dd,1-cash/peak)
            ledger.append(row)
        trades=[r for r in ledger if r['status']=='MODELED_ROUND_TRIP']
        return {'engine':self.engine,'seed':seed,'strict':strict,'stopped':stopped,'gaps':gaps,
            'terminal_conditional_cash':None if stopped else str(cash),'last_resolved_cash':str(cash),
            'trades':len(trades),'wins':sum(D(r['pnl'])>0 for r in trades),'targets':sum(r['target'] for r in trades),
            'drawdown':str(dd),'ledger':ledger}

    def parity(self):
        for seed in (None,0,1,2,3,4):
            f=CACHE/'results'/('v5_'+self.engine+'_1_high'+('' if seed is None else f'_random_{seed}')+'.json')
            if not f.exists():
                if seed is not None and not self.source['signals']:continue
                raise ValueError('Parity reference missing: '+str(f))
            ref=json.loads(f.read_text());ours=self.run(seed)
            if len(ref['ledger'])!=len(ours['ledger']):raise ValueError('Parity ledger length '+self.engine+str(seed))
            for a,b in zip(ref['ledger'],ours['ledger']):
                if (a['status'],a['cash_before'],a.get('cash_after'))!=(b['status'],b['cash_before'],b.get('cash_after')):
                    raise ValueError('Parity mismatch '+self.engine+' '+str(seed)+' '+a['signal']['id']+' '+str((a['status'],a['cash_before'],a.get('cash_after')))+' vs '+str(b))
            assert ref['last_resolved_cash']==ours['last_resolved_cash']
        return True

def run_all():
    summaries=[]
    for engine in SOURCES:
        runner=Runner(engine);runner.parity();base=runner.run();strict=runner.run(strict=True)
        print('PARITY_PASS',engine,flush=True)
        paths=[]
        if runner.source['signals']:
            for seed in range(999):
                x=runner.run(seed);x.pop('ledger');paths.append(x)
                if (seed+1)%100==0:print('NOISE_PATHS',engine,seed+1,flush=True)
        valid=[D(x['terminal_conditional_cash']) for x in paths if not x['stopped']]
        unknown=len(paths)-len(valid);rank=None
        if base['terminal_conditional_cash'] is not None and paths:
            beaten=sum(v>=D(base['terminal_conditional_cash']) for v in valid)
            rank={'lower':(1+beaten)/(len(paths)+1),'upper':(1+beaten+unknown)/(len(paths)+1),
                  'meaning':'Conditional random-side rank bounds; not a significance test of a clean-universe strategy.'}
        summary={'engine':engine,'baseline':base,'strict':strict,'random_paths':len(paths),
            'unresolved_random_paths':unknown,'rank_bounds':rank,
            'random_terminal_percentiles':None if not valid else {str(p):str(sorted(valid)[int((len(valid)-1)*p)]) for p in (.05,.5,.95)},
            'random_profitable_paths':sum(v>START for v in valid),'source_sha':runner.source['source_sha'],
            'compiled_sha':digest(runner.compiled_file),'runner_sha':digest(__file__),'paths':paths,
            'parity_passed':True,'parity_reference_sha':{str(seed):digest(CACHE/'results'/('v5_'+engine+'_1_high'+('' if seed is None else f'_random_{seed}')+'.json')) for seed in (None,0,1,2,3,4) if seed is None or runner.source['signals']}}
        save(NOISE/(engine+'_noise.json'),summary);summaries.append({k:v for k,v in summary.items() if k not in ('paths',)})
        runner.outcome.cache_clear()
    save(NOISE/'noise_summary.json',{'status':'COMPLETE_CONDITIONAL_NOISE_DIAGNOSTICS','engines':summaries,
         'generated_at':datetime.now(timezone.utc).isoformat(),'full_family_winner':None})

if __name__=='__main__':run_all()
