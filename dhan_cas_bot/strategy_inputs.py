"""Read-only minute inputs alongside the existing WebSocket execution feeds."""
import asyncio
from csv import DictReader
from dataclasses import asdict, replace
from datetime import datetime, time, timedelta, timezone
from io import StringIO
import json
from decimal import Decimal

import httpx

from .directional import Inputs
from .domain import ContractError
from .instruments import is_nifty_option, load_dhan_master, parse_date
from .session_strategies import CAS, GAP, REBOUND, SHOCK, STRATEGIES, IST, Calendar, Evaluation, evaluate, parse_bars, parse_session
from .seconds_strategies import NAMES as SECONDS_NAMES


def strategy_names(config):
    names=config.get("strategies",[CAS])
    if not isinstance(names,list) or not names or any(not isinstance(n,str) or n not in STRATEGIES for n in names) or len(set(names))!=len(names):
        raise ContractError("strategies must be a nonempty unique list of supported strategy names")
    return tuple(names)


def selected_contracts(payload, freezes, today):
    rows=list(DictReader(StringIO(payload.decode("utf-8-sig"))))
    expiries=sorted({parse_date(r["SM_EXPIRY_DATE"]) for r in rows if is_nifty_option(r) and parse_date(r["SM_EXPIRY_DATE"])>=today})
    if not expiries:
        raise ContractError("current NIFTY expiry calendar unavailable")
    # Three actual expiries cover near-week and overnight selection. If none
    # extends beyond the next session, the rebound engine reports no contract.
    instruments=[]
    for expiry in expiries[:3]:
        instruments.extend(load_dhan_master(StringIO(payload.decode("utf-8-sig")),expiry=expiry,freeze_by_security={"__NIFTY__":freezes["NIFTY"]}))
    futures=[r for r in rows if r.get("INSTRUMENT")=="FUTIDX" and r.get("UNDERLYING_SYMBOL")=="NIFTY"
             and (r.get("SEGMENT")=="NSE_FNO" or (r.get("EXCH_ID")=="NSE" and r.get("SEGMENT")=="D"))
             and parse_date(r["SM_EXPIRY_DATE"])>=today]
    future=min(futures,key=lambda r:(parse_date(r["SM_EXPIRY_DATE"]),r["SECURITY_ID"]))["SECURITY_ID"] if futures else None
    return instruments, future


def route_window(enabled, now, calendar, expiry_today):
    local=now.astimezone(IST)
    if calendar is not None and not calendar.is_open(now):
        return False
    if CAS in enabled and expiry_today and time(15,5)<=local.time()<time(15,19,30):
        return True
    if calendar is None or not calendar.is_open(now):
        return False
    # Connection qualification is recovery work, not a trading signal. With
    # rebound enabled, permit bounded qualification throughout the verified
    # open session before its decision, including after a repaired restart.
    return ((GAP in enabled and not expiry_today and time(9,40)<=local.time()<time(11,31))
            or (REBOUND in enabled and local.time()<time(15,10))
            or any(name not in (CAS,GAP,REBOUND) for name in enabled))


class CalendarSource:
    def __init__(self, token, *, client=None):
        self.token, self.client = token, client

    async def fetch(self, now):
        if not self.token:
            raise ContractError("UPSTOX_CALENDAR_AUTH_UNAVAILABLE")
        day=now.astimezone(IST).date()
        own=self.client is None
        client=self.client or httpx.AsyncClient(timeout=5,follow_redirects=False)
        cash_sessions={}
        async def session(day):
            response=await client.get("https://api.upstox.com/v2/market/timings/"+str(day),headers={"Authorization":"Bearer "+self.token})
            response.raise_for_status()
            payload=response.json()
            future=parse_session(payload,day)
            cash_sessions[day]=parse_session(payload,day,exchange="NSE")
            if future and not cash_sessions[day]:
                raise ContractError("cash session calendar unavailable")
            return future
        try:
            current=await session(day)
            adjacent=[]
            for direction in (-1,1):
                found=None
                for offset in range(1,16):
                    found=await session(day+timedelta(days=direction*offset))
                    if found:
                        break
                if not found:
                    raise ContractError("adjacent trading session unavailable")
                adjacent.extend(found)
            return Calendar(*(current or (None,None)),*adjacent,now,day,
                            spot_closes=cash_sessions[day][1] if cash_sessions[day] else None,
                            previous_spot_closes=cash_sessions[adjacent[0].date()][1])
        finally:
            if own:
                await client.aclose()


class MinuteSource:
    def __init__(self, broker, *, now_fn=None,stream=None):
        self.broker=broker
        self.now=now_fn or (lambda:datetime.now(timezone.utc))
        self.cache={}
        self.stream=stream
        self.last_source='REST_BOOTSTRAP_OR_GAP_REPAIR'
        self.spot_source='NOT_OBSERVED'

    async def fetch(self, security, segment, instrument, start, end, *, oi=False):
        key=(security,segment,instrument,oi,start)
        saved=self.cache.get(key,{})
        current=self.stream.current(self.now()) if self.stream and (security,segment,instrument,oi)==('13','IDX_I','INDEX',False) else None
        if current and saved and current.available<=end:
            latest=max(saved)
            # A complete baseline plus every intervening provider minute is
            # required. Never silently jump over a gap after reconnect.
            t=latest+timedelta(minutes=1)
            missing=False
            while t<=current.available:
                if t not in self.stream.rows:missing=True;break
                t+=timedelta(minutes=1)
            if not missing and latest>=current.available-timedelta(minutes=2):
                result={t:b for t,b in saved.items() if start<=t<=min(end,self.now())}
                result.update({t:b for t,b in self.stream.rows.items() if start<=t<=min(end,self.now())})
                self.cache[key]=result
                self.last_source='UPSTOX_COMPLETED_I1_STREAM'
                self.spot_source=self.last_source
                return dict(result)
        self.last_source='REST_BOOTSTRAP_OR_GAP_REPAIR'
        if (security,segment,instrument)==('13','IDX_I','INDEX'):self.spot_source=self.last_source
        # Repair two overlapping completed minutes. Replace that interval,
        # including omissions; a provider hole must not retain a cached bar.
        boundary=max(start,max(saved)-timedelta(minutes=1)) if saved else start
        request={"securityId":security,"exchangeSegment":segment,"instrument":instrument,"interval":"1","oi":oi,
                 # Live chart responses exclude the bar starting at fromDate.
                 # Two minutes cover its start and close boundaries when
                 # replacing cached completed candles. Cold opening requests
                 # still begin one minute before the session boundary.
                 "fromDate":(boundary-timedelta(minutes=2 if saved else 1)).astimezone(IST).strftime("%Y-%m-%d %H:%M:%S"),
                 "toDate":end.astimezone(IST).strftime("%Y-%m-%d %H:%M:%S")}
        try:raw=await self.broker._request("POST","/charts/intraday",json=request)
        except Exception:
            self.cache.pop(key,None)
            raise
        received=self.now()
        try:
            rows={t:bar for t,bar in parse_bars(raw,received,require_oi=oi).items()
                  if boundary<=t<=min(end,received)}
        except Exception:
            self.cache.pop(key,None)
            raise
        result={t:bar for t,bar in saved.items() if start<=t<boundary and t<=min(end,received)}
        result.update(rows)
        # Old session/contracts cannot grow memory without a bound.
        if key not in self.cache and len(self.cache)>=96:self.cache.pop(next(iter(self.cache)))
        self.cache[key]=result
        return dict(result)


class StrategyInputWorker:
    def __init__(self, directional, token, future_id, *, wake, stop,indexes=None):
        self.directional=directional
        self.engine=directional.engine
        self.calendar_source=CalendarSource(token)
        from .stream_minutes import CompletedIndexMinutes
        self.stream_minutes=CompletedIndexMinutes()
        self.bar_wake=asyncio.Event()
        self.minutes=MinuteSource(self.engine.runtime.broker,now_fn=self.engine.now,stream=self.stream_minutes)
        self.future_id=future_id
        self.wake,self.stop=wake,stop
        self.calendar=None
        self.option_bars={}
        self.last_calendar_error=""
        from .strategy_features import FeatureSource
        self.features=FeatureSource(self.engine.runtime.broker,token,self.engine.now)
        self.indexes=indexes or {}
        self.aux_task=None
        self.aux_context=None
        self.aux_features={}
        self.aux_received=None
        self.aux_started=None
        self.aux_error=''
        self.input_health={}
        self.spot_bars={}
        self.future_bars={}


    def on_stream(self,frame,epoch,received):
        if self.stream_minutes.accept(frame,epoch,received):self.bar_wake.set()

    def stream_reset(self):self.stream_minutes.reset()

    def evaluations(self, bar_at, spot, future, expiries, features):
        """Use one completed-bar boundary, actual receipt time for admission."""
        moment=self.engine.now()
        return {strategy:evaluate(strategy,moment,self.calendar,spot,future,expiries,bar_at=bar_at)
                if strategy in (GAP,REBOUND) else self.shock(moment,spot,future,bar_at)
                if strategy==SHOCK else self.expanded(strategy,moment,self.calendar,spot,future,expiries,
                    features=features,bar_at=bar_at)
                for strategy in self.directional.enabled if strategy not in SECONDS_NAMES}

    def shock(self,moment,spot,future,bar_at):
        from .volatility_shock import evaluate_completed_shock
        return evaluate_completed_shock(moment,self.calendar,spot,future,bar_at=bar_at,
            source=self.minutes.spot_source+' + DHAN_INTRADAY_PER_MINUTE_FUTURE')

    @staticmethod
    def expanded(*args,**kwargs):
        from .expanded_strategies import evaluate as expanded
        return expanded(*args,**kwargs)

    def publish(self,evaluations):
        self.directional.update(Inputs(self.calendar,evaluations,dict(self.option_bars),self.engine.now(),
            spot_bars=dict(self.spot_bars),future_bars=dict(self.future_bars)))
        self.wake.set()

    def wanted_options(self,spot,bar_at,expiries):
        """Warm actual near contracts before a signal, bounded to 18 contracts."""
        wanted=set()
        current=spot.get(bar_at)
        expiry=min(expiries)
        instruments=list(self.engine.instruments.values())
        if current:
            for side in ('CE','PE'):
                rows=[i for i in instruments if i.expiry==expiry and i.option_type.value==side]
                if not rows:continue
                atm=min(rows,key=lambda i:(abs(i.strike-current.close),i.strike)).strike
                direction=1 if side=='CE' else -1
                outward=sorted((i for i in rows if direction*(i.strike-atm)>=0),key=lambda i:(direction*(i.strike-atm),i.security_id))[:4]
                inward=sorted((i for i in rows if direction*(i.strike-atm)<0),key=lambda i:(abs(i.strike-atm),i.security_id))[:1]
                wanted.update(i.security_id for i in (*outward,*inward))
        anchors_wanted=set()
        # Frozen acceleration anchors and published OI walls can move away
        # from current ATM. Keep their exact identities warm as well.
        anchors=[]
        anchor=spot.get(bar_at.replace(hour=14,minute=45))
        if anchor:anchors.append(anchor.close)
        wall_anchor=spot.get(bar_at.replace(hour=9,minute=30))
        prior=self.aux_features.get('prior_chain',{})
        for side in ('CE','PE'):
            rows=[i for i in instruments if i.expiry==expiry and i.option_type.value==side]
            for anchor_spot in anchors:
                if rows:anchors_wanted.add(min(rows,key=lambda i:(abs(i.strike-anchor_spot),i.strike)).security_id)
            if wall_anchor:
                walls=[(k,oi) for (s,k),oi in prior.get('oi',{}).items() if s==side and abs(k-wall_anchor.close)<=200]
                if walls:
                    strike=min(walls,key=lambda x:(-x[1],x[0]))[0]
                    anchors_wanted.update(i.security_id for i in rows if i.strike==strike)
        urgent=[]
        if self.engine.active:urgent.append(self.engine.active['security_id'])
        samples=sorted(self.directional.signals.values(),key=lambda s:(s.evaluated_at,s.strategy),reverse=True)
        for sample in samples:
            if not sample.side or not 0 <= (self.engine.now()-sample.evaluated_at).total_seconds()<120:continue
            rows=[i for i in instruments if i.expiry>=sample.minimum_expiry and i.option_type.value==sample.side]
            if not rows:continue
            expiry=min(i.expiry for i in rows);rows=[i for i in rows if i.expiry==expiry]
            atm=min(rows,key=lambda i:(abs(i.strike-sample.spot),i.strike)).strike
            direction=1 if sample.side=='CE' else -1
            urgent.extend(i.security_id for i in sorted((i for i in rows if direction*(i.strike-atm)>=0),key=lambda i:(direction*(i.strike-atm),i.security_id))[:4])
        return list(dict.fromkeys([*urgent,*sorted(anchors_wanted),*sorted(wanted)]))[:18]

    async def warm_options(self,wanted):
        slots=asyncio.Semaphore(3)
        async def read(security):
            async with slots:
                try:
                    from .read_scheduler import read_priority
                    with read_priority(4):
                        rows=await self.minutes.fetch(security,'NSE_FNO','OPTIDX',self.calendar.opens,self.engine.now(),oi=True)
                    self.option_bars[security]=rows
                    return True
                except Exception:
                    self.option_bars.pop(security,None)
                    return False
        ready=await asyncio.gather(*(read(s) for s in wanted))
        self.option_bars={s:rows for s,rows in self.option_bars.items() if s in wanted}
        return sum(ready),len(ready)-sum(ready)

    async def auxiliary(self,now,calendar,expiry,families,context):
        result={}
        try:
            slots=asyncio.Semaphore(3)
            async def index(name):
                required=(name in ('BANK','IT') and families&{'SECTOR_CATCHUP','SECTOR_CONFIRM'}) or (name=='VIX' and 'IV_CHEAP_TREND' in families)
                if not required or not self.indexes.get(name):return
                async with slots:
                    try:result[name]=await self.minutes.fetch(self.indexes[name],'IDX_I','INDEX',calendar.opens,self.engine.now())
                    except Exception:pass
            async def gift():
                if 'GIFT_CATCHUP' not in families:return
                async with slots:
                    try:result['GIFT']=await self.features.gift(self.engine.now())
                    except Exception:pass
            async def published():
                # Its own three-source bound and receipt-time validation remain.
                result.update(await self.features.refresh(now,calendar,expiry,families))
            await asyncio.wait_for(asyncio.gather(*(index(n) for n in ('BANK','IT','VIX')),gift(),published()),30)
            if context!=self.aux_context:return
            self.aux_features=result
            self.aux_received=self.engine.now()
            self.aux_error=''
        except Exception as exc:
            if context==self.aux_context:
                # Keep independently completed sources. A timed-out published
                # feed must not erase successful BANK/IT candles.
                self.aux_features=result;self.aux_received=self.engine.now()
                self.aux_error=type(exc).__name__
        finally:
            self.bar_wake.set()

    def start_auxiliary(self,now,expiries,families):
        context=(now.astimezone(IST).date(),min(expiries))
        if self.aux_context!=context:
            if self.aux_task and not self.aux_task.done():self.aux_task.cancel()
            self.aux_features={};self.aux_received=None;self.aux_started=None;self.aux_context=context
        due=self.aux_started is None or (self.engine.now()-self.aux_started).total_seconds()>=30
        if due and (self.aux_task is None or self.aux_task.done()):
            self.aux_started=self.engine.now()
            from .read_scheduler import read_priority
            with read_priority(10):
                self.aux_task=asyncio.create_task(self.auxiliary(now,self.calendar,min(expiries),families,context))

    def available_features(self,expiries):
        # A stalled/failed optional collector cannot preserve an indefinitely
        # current IV, insight or sector snapshot. Long-lived publications keep
        # their original receipt boundary and their existing source checks.
        now=self.engine.now()
        valid=self.aux_received and 0 <= (now-self.aux_received).total_seconds()<=90
        result=dict(self.aux_features) if valid else {}
        for key,limit in (('iv',60),('insights',90)):
            value=result.get(key)
            if value and not 0 <= (now-value['received_at']).total_seconds()<=limit:result.pop(key,None)
        expiry=min(expiries)
        result['options']={(i.option_type.value,i.strike):self.option_bars[i.security_id]
                           for i in self.engine.instruments.values() if i.expiry==expiry and i.security_id in self.option_bars}
        return result

    @staticmethod
    def series_health(rows,bar_at,opening,error=''):
        t=opening+timedelta(minutes=1) if opening else bar_at
        missing=[]
        while t<=bar_at:
            if t not in rows:missing.append(t)
            t+=timedelta(minutes=1)
        return {'rows':len(rows),'latest_completed':max(rows).isoformat() if rows else None,
                'current_complete':bar_at in rows,'missing_minutes':len(missing),
                'first_missing':missing[0].isoformat() if missing else None,'error':error}

    async def refresh(self):
        now=self.engine.now().astimezone(IST)
        bar_at=now.replace(second=0,microsecond=0)
        evaluations={}
        try:
            if self.calendar is None or not self.calendar.fresh(now) or (now-self.calendar.checked_at).total_seconds()>=3600:
                self.calendar=None
                self.calendar=await self.calendar_source.fetch(now)
                self.engine.runtime.ledger.observe('market-calendar:'+self.calendar.checked_at.isoformat(),'MARKET_CALENDAR',
                    {'source':'https://api.upstox.com/v2/market/timings/',**asdict(self.calendar)})
            expiries={i.expiry for i in self.engine.instruments.values() if i.expiry>=now.date()}
            from .expanded_strategies import SPECS
            families={SPECS[n][0] for n in self.directional.enabled if n in SPECS}
            spot,future={},{}
            errors={}
            if self.calendar.is_open(now):
                from .read_scheduler import read_priority
                async def read(name,security,segment,instrument,start,oi=False):
                    if not security:errors[name]='CONTRACT_UNAVAILABLE';return {}
                    try:
                        with read_priority(4):return await self.minutes.fetch(security,segment,instrument,start,now,oi=oi)
                    except Exception as exc:errors[name]=type(exc).__name__;return {}
                spot,future=await asyncio.gather(read('spot','13','IDX_I','INDEX',self.calendar.previous_opens),
                    read('future',self.future_id,'NSE_FNO','FUTIDX',self.calendar.opens,True))
                self.spot_bars,self.future_bars=spot,future
                if SHOCK in self.directional.enabled:
                    from .volatility_shock import ShockFeatureSnapshot
                    from .domain import digest
                    snapshot=ShockFeatureSnapshot(bar_at,self.engine.now(),
                        self.minutes.spot_source+' + DHAN_INTRADAY_PER_MINUTE_FUTURE',
                        tuple(b for t,b in sorted(spot.items()) if bar_at-timedelta(minutes=35)<=t<=bar_at),
                        tuple(b for t,b in sorted(future.items()) if self.calendar.opens<t<=bar_at))
                    observed=asdict(snapshot)
                    observed.update(spot_security_id='13',future_security_id=self.future_id)
                    identity=digest({k:v for k,v in observed.items() if k!='received_at'})
                    self.engine.runtime.ledger.observe('shock-input:'+identity,'SHOCK_INPUT',observed)
                self.publish(self.evaluations(bar_at,spot,future,expiries,self.available_features(expiries)))
                # Shock selection fits live books, not old option candles.
                wanted=[] if set(self.directional.enabled)=={SHOCK} else self.wanted_options(spot,bar_at,expiries)
                ready,failed=await self.warm_options(wanted)
                self.start_auxiliary(now,expiries,families)
                # Yield to the optional collector; never await its HTTP batch.
                await asyncio.sleep(0)
                self.input_health={'observed_at':self.engine.now().isoformat(),'decision_bar_at':bar_at.isoformat(),
                    'spot':self.series_health(spot,bar_at,self.calendar.opens,errors.get('spot','')),
                    'future':self.series_health(future,bar_at,self.calendar.opens,errors.get('future','')),
                    'options':{'requested':len(wanted),'loaded':ready,'failed':failed,
                        'ready':sum(all(bar_at-timedelta(minutes=n) in self.option_bars.get(s,{}) for n in range(3)) for s in wanted)},
                    'auxiliary':{'running':bool(self.aux_task and not self.aux_task.done()),
                        'received_at':self.aux_received.isoformat() if self.aux_received else None,'error':self.aux_error}}
            evaluations=self.evaluations(bar_at,spot,future,expiries,self.available_features(expiries))
            self.publish(evaluations)
            for sample in evaluations.values():
                identity=f'strategy-evaluation:{sample.strategy}:{sample.evaluated_at.isoformat()}:{sample.state}'
                self.engine.runtime.ledger.observe(identity,'STRATEGY_EVALUATION',asdict(sample))
        except Exception as exc:
            error='STRATEGY_INPUT_UNAVAILABLE:'+type(exc).__name__
            self.directional.update(Inputs(self.calendar,evaluations,{},self.engine.now(),error))
            self.input_health={'observed_at':self.engine.now().isoformat(),'decision_bar_at':bar_at.isoformat(),'error':type(exc).__name__}
        self.wake.set()

    async def close(self):
        if self.aux_task and not self.aux_task.done():self.aux_task.cancel()
        if self.aux_task:await asyncio.gather(self.aux_task,return_exceptions=True)

    async def run(self):
        try:
            while not self.stop.is_set():
                self.bar_wake.clear()
                await self.refresh()
                now=self.engine.now()
                seconds=62-now.second-now.microsecond/1e6
                delay=max(2,min(60,seconds))
                # Retry missing current candles while there is still a decision
                # window. No quote polling and no invented candle history.
                if any(self.input_health.get(k,{}).get('current_complete') is False for k in ('spot','future')):
                    delay=min(delay,5)
                try:await asyncio.wait_for(self.bar_wake.wait(),delay)
                except asyncio.TimeoutError:pass
        finally:await self.close()
