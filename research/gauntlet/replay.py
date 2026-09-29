"""Independent chronological bankrolls for fully specified signal inputs.

The executable subset here is the explicitly named metadata-disclosure variant,
with a seven-calendar-day stock delivery buffer. It is not the complete nine-
engine tournament. Unknown coverage prevents a champion claim.
"""
import argparse
import json
from datetime import datetime,timedelta,timezone
from decimal import Decimal as D
from dataclasses import asdict
from .data import CACHE,save
from .core import Bar,snapshot,make_order,entry,exit_trade,cash_after
from .contracts import option_candidates,instrument_bars,execution_contract,confirmed_no_trades,exact_signal_contract,audited_option_bars
from .provenance import source_manifest,digest

def invalidate(signal,rows,after):
    direction=1 if signal['side']=='CE' else -1
    ref=D(signal['reference']); extreme=D(signal['extreme'])
    for b in rows:
        if b.available<=after:continue
        if signal.get('exit_rule')=='STRIKE_CROSS_BACK':
            if direction*(b.close-ref)<=0:return b.available
            continue
        if (direction==1 and b.high>extreme) or (direction==-1 and b.low<extreme):
            extreme=b.high if direction==1 else b.low
        if direction*(b.close-ref)<D('.5')*direction*(extreme-ref):return b.available
    return None

SOURCES={'EVENT_CONTINUATION':'event_candidates.json','INTRADAY_EVENT':'event_candidates.json',
 'NONEXPIRY_FORCED_FLOW':'nonexpiry_candidates.json','EXPIRY_FORCED_FLOW':'expiry_candidates.json',
 'PASSIVE_FLOW':'passive_candidates.json','SCHEDULED_EVENT_VOL':'scheduled_candidates.json',
 'BLOCK_OFS_DISLOCATION':'ofs_candidates.json','SECTOR_SHOCK_LAG':'leadlag_candidates.json','CROSS_MARKET_LEAD_LAG':'leadlag_candidates.json'}

def replay(engine,delay=1,adverse=True,skip_id=None,participation=D('.05'),liquidate_minutes=7,control=None,seed=0):
    started=datetime.now(timezone.utc)
    sources=source_manifest()
    is_event=engine in ('EVENT_CONTINUATION','INTRADAY_EVENT')
    source=SOURCES[engine]
    raw=json.loads((CACHE/source).read_text())
    input_sha=digest(CACHE/source)
    bans=json.loads((CACHE/'ban_lists.json').read_text())
    ban_sha=digest(CACHE/'ban_lists.json')
    signals=sorted([s for s in raw if s['engine']==engine],key=lambda s:(s['at'],s['symbol'],s['side']))
    if control:
        import random
        randomizer=random.Random(seed)
        signals=[dict(s) for s in signals]
        for s in signals:
            original=s['side'];s['side']=randomizer.choice(('CE','PE'))
            # Matched-time control uses the same signal time and underlying;
            # only the side changes. No future price selects control entries.
            if s['side']!=original:
                s['extreme']=str(2*D(s['reference'])-D(s['extreme']))
                s.pop('contract_key',None)
    cash=D('9411.18');ledger=[];busy=None;peak=cash;drawdown=D(0);stopped=False;coverage_gaps=[]
    for signal_index,s in enumerate(signals):
        if signal_index%10==0:
            print(engine,'processed',signal_index,'of',len(signals),'cash',cash,flush=True)
        row={'signal':s,'cash_before':str(cash)}
        if s['id']==skip_id:
            row['status']='BEST_TRADE_DELETED';ledger.append(row);continue
        at=datetime.fromisoformat(s['at'])
        ban=bans.get(s['at'][:10],{})
        if ban.get('status')!='VERIFIED_DATE':
            row['status']='UNKNOWN_BAN_FILE';ledger.append(row)
            coverage_gaps.append({'signal':s['id'],'reason':'UNKNOWN_BAN_FILE'});continue
        if s['symbol'] in ban['symbols']:
            row['status']='EXCHANGE_NEW_POSITION_BAN';ledger.append(row);continue
        if busy is not None and at<busy:
            row['status']='POSITION_ALREADY_OPEN';ledger.append(row);continue
        if s['materiality'] not in ('QUALIFYING_TEXT','NOT_REQUIRED'):
            row['status']='OUTSIDE_METADATA_VARIANT';ledger.append(row);continue
        if s['futures_confirmation'] not in ('CONFIRMED','NOT_REQUIRED'):
            row['status']='UNKNOWN_FUTURE_CONFIRMATION';ledger.append(row);stopped=True;break
        try:
            chain=([exact_signal_contract(s)] if 'contract_key' in s else option_candidates(s['symbol'],s['at'][:10],D(s['spot']),s['side']))
            if not chain:
                row['status']='NO_ELIGIBLE_CONTRACT_IN_PRIOR_FILE';ledger.append(row);continue
            selected=None;rejections=[]
            for contract in chain:
                if confirmed_no_trades(contract.key,s['at'][:10]):
                    rejections.append({'key':contract.key,'reason':'OFFICIAL_ZERO_TRADES_AUDIT'});continue
                raw_bars,audit=audited_option_bars(contract.key,s['at'][:10])
                if audit['status'].startswith('UNKNOWN'):
                    coverage_gaps.append({'signal':s['id'],'key':contract.key,'reason':audit})
                bars=sorted([Bar.parse(r) for r in raw_bars],key=lambda b:b.start)
                known=snapshot(bars,at)
                if not known:
                    # No current executable quote may be inferred from absent tape.
                    coverage_gaps.append({'signal':s['id'],'key':contract.key,'reason':'NO_KNOWN_OPTION_TAPE'})
                    rejections.append({'key':contract.key,'reason':'NO_KNOWN_QUOTE_PROXY'});continue
                contract=execution_contract(contract)
                order,reason=make_order(contract,known,at,cash,s['id'],participation)
                if order:
                    selected=(order,bars);break
                rejections.append({'key':contract.key,'reason':reason})
            row['rejected_contracts']=rejections
            if selected is None:
                row['status']='NO_ORDER_UNDER_MODEL';ledger.append(row);continue
            order,bars=selected
            row['order']={'key':order.contract.key,'lot':order.contract.lot,'quantity':order.quantity,
                          'strike':str(order.contract.strike),'expiry':order.contract.expiry,'limit':str(order.limit),
                          'decided':order.decided.isoformat(),'reference_close':str(order.reference_close)}
            fill=entry(order,bars,delay,participation,adverse)
            row['entry']={k:str(v) if isinstance(v,D) else v for k,v in fill.items() if k!='bar'}
            if fill['status']!='MODELED_FILL':
                row['status']=fill['status'];ledger.append(row)
                if fill['status'].startswith('UNKNOWN'):stopped=True;break
                continue
            underlying=[Bar.parse(r) for r in json.loads((CACHE/'underlying'/f"{s['symbol']}.json").read_text()) if r[0][:10]==s['at'][:10]]
            invalid=invalidate(s,underlying,at)
            if invalid is not None and invalid<=fill['bar'].start:
                row['status']='INVALIDATED_BEFORE_DISPATCH';ledger.append(row);continue
            close_at=at.replace(hour=15,minute=17,second=0,microsecond=0)
            result=exit_trade(order,fill,bars,invalid,close_at,participation,liquidate_minutes)
            row['exit']={k:str(v) if isinstance(v,D) else v for k,v in result.items()}
            if result['status']!='MODELED_EXIT':
                row['status']=result['status'];ledger.append(row);stopped=True;break
            new_cash,fees=cash_after(cash,order,fill['price'],result['price'],result.get('parts'))
            row.update(status='MODELED_ROUND_TRIP',cash_after=str(new_cash),net_pnl=str(new_cash-cash),fees=str(fees),
                       premium_multiple=str(result['price']/fill['price']))
            cash=new_cash
            busy=datetime.fromisoformat(result['time'])+timedelta(minutes=1)
            peak=max(peak,cash);drawdown=max(drawdown,1-cash/peak)
            ledger.append(row)
        except Exception as e:
            row['status']='UNKNOWN_DATA_ERROR';row['error']=type(e).__name__+':'+str(e);ledger.append(row)
            coverage_gaps.append({'signal':s['id'],'reason':row['error']})
            if row.get('entry',{}).get('status')=='MODELED_FILL':
                stopped=True;break
            # Continue only the explicitly conditional observed-data diagnostic.
            # Its bankroll is not promoted to full-period performance.
            continue
    trades=[r for r in ledger if r['status']=='MODELED_ROUND_TRIP']
    variant={
        'EVENT_CONTINUATION':'METADATA_ONLY_SEVEN_DAY_DELIVERY_BUFFER',
        'INTRADAY_EVENT':'METADATA_ONLY_SEVEN_DAY_DELIVERY_BUFFER',
        'NONEXPIRY_FORCED_FLOW':'EXACT_CONTRACT_REGULAR_SPOT_SEVEN_DAY_BUFFER',
        'EXPIRY_FORCED_FLOW':'NSE_INDEX_REGULAR_SPOT_WITHOUT_CAS',
        'PASSIVE_FLOW':'MSCI_STANDARD_ADDITIONS_DELETIONS_AUGUST_2026',
        'SCHEDULED_EVENT_VOL':'RBI_AUGUST_2026_INDEX_STRADDLE_FILTER',
        'BLOCK_OFS_DISLOCATION':'LICI_DISCLOSED_OFS_ONLY',
        'SECTOR_SHOCK_LAG':'FROZEN_PREPERIOD_BANKS_AND_SOFTWARE_GRAPH',
        'CROSS_MARKET_LEAD_LAG':'GIFT_NIFTY_WITH_TWO_MINUTE_FEED_DELAY',
    }[engine]
    drift=source_manifest()['sha256']!=sources['sha256'] or digest(CACHE/source)!=input_sha or digest(CACHE/'ban_lists.json')!=ban_sha
    result={'engine':engine,'variant':variant,'start_cash':'9411.18',
            'status':'UNKNOWN_PATH' if stopped else 'CONDITIONAL_BAR_MODEL_REPLAY',
            'final_cash':None if stopped or coverage_gaps or drift else str(cash),'last_resolved_cash':str(cash),
            'delay_bars':delay,'entry_model':'next_full_bar_high' if adverse else 'next_full_bar_open_plus_1pct',
            'execution_revision':5,'liquidation_window_minutes':liquidate_minutes,'control':control,'control_seed':seed,
            'signals':len(signals),'trades':len(trades),'wins':sum(D(r['net_pnl'])>0 for r in trades),
            'targets':sum(r['exit']['reason']=='TARGET_2X' for r in trades),
            'half_losses':sum(D(r['premium_multiple'])<=D('.5') for r in trades),
            'closed_trade_max_drawdown':str(drawdown),'ledger':ledger,
            'coverage':'NSE downloaded subset; materiality, RMS and universe gaps audited separately',
            'coverage_gaps':coverage_gaps,'source_manifest':sources,'signal_input_sha256':input_sha,
            'ban_lists_sha256':ban_sha,
            'started_at':started.isoformat(),'completed_at':datetime.now(timezone.utc).isoformat(),'source_drift_during_run':drift,
            'is_champion_eligible':False}
    if coverage_gaps or drift:result['status']='UNKNOWN_COVERAGE' if not drift else 'STALE_SOURCE'
    suffix=f'v5_{engine}_{delay}_{"high" if adverse else "open"}'+('_delete_best' if skip_id else '')+(f'_random_{seed}' if control else '')
    save(CACHE/'results'/'history'/(started.strftime('%Y%m%dT%H%M%S%f')+'_'+suffix+'.json'),result)
    save(CACHE/'results'/(suffix+'.json'),result)
    print(engine,'delay',delay,'status',result['status'],'trades',len(trades),'cash',result['final_cash'],flush=True)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--engine',choices=list(SOURCES),required=True)
    p.add_argument('--delay',type=int,default=1);p.add_argument('--open-model',action='store_true');p.add_argument('--delete-best',action='store_true')
    a=p.parse_args();result=replay(a.engine,a.delay,not a.open_model)
    if a.delete_best:
        trades=[r for r in result['ledger'] if r['status']=='MODELED_ROUND_TRIP']
        if trades:
            best=max(trades,key=lambda r:D(r['net_pnl']))
            replay(a.engine,a.delay,not a.open_model,best['signal']['id'])
