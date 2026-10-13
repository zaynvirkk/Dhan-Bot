"""Read-only minute inputs alongside the existing WebSocket execution feeds."""
import asyncio
from csv import DictReader
from dataclasses import asdict
from datetime import datetime, time, timedelta, timezone
from io import StringIO
import json
from decimal import Decimal

import httpx

from .directional import Inputs
from .domain import ContractError
from .instruments import is_nifty_option, load_dhan_master, parse_date
from .session_strategies import CAS, GAP, REBOUND, STRATEGIES, IST, Calendar, Evaluation, evaluate, parse_bars, parse_session


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
                 "fromDate":(boundary-timedelta(minutes=1)).astimezone(IST).strftime("%Y-%m-%d %H:%M:%S"),
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

    def on_stream(self,frame,epoch,received):
        if self.stream_minutes.accept(frame,epoch,received):self.bar_wake.set()

    def stream_reset(self):self.stream_minutes.reset()

    async def refresh(self):
        now=self.engine.now().astimezone(IST)
        evaluations={}
        try:
            if self.calendar is None or not self.calendar.fresh(now) or (now-self.calendar.checked_at).total_seconds()>=3600:
                # Once a scheduled refresh fails, the last calendar is not
                # silently treated as a successful check.
                self.calendar=None
                self.calendar=await self.calendar_source.fetch(now)
                self.engine.runtime.ledger.observe("market-calendar:"+self.calendar.checked_at.isoformat(),"MARKET_CALENDAR",
                    {"source":"https://api.upstox.com/v2/market/timings/", **asdict(self.calendar)})
            expiries={i.expiry for i in self.engine.instruments.values()}
            spot=future={}
            features={}
            from .expanded_strategies import SPECS
            families={SPECS[n][0] for n in self.directional.enabled if n in SPECS}
            if self.calendar.is_open(now):
                spot=await self.minutes.fetch("13","IDX_I","INDEX",self.calendar.previous_opens,now)
                if ((GAP in self.directional.enabled and time(9,44)<=now.time()<time(11,32) and now.date() not in expiries)
                        or any(name not in (GAP,REBOUND) for name in self.directional.enabled)):
                    if self.future_id:
                        try:future=await self.minutes.fetch(self.future_id,"NSE_FNO","FUTIDX",self.calendar.opens,now,oi=True)
                        except Exception:future={}
                # Publish completed core signals immediately. Optional feature
                # requests cannot hold their entry behind a whole-universe scan.
                core={}
                from .expanded_strategies import evaluate as expanded
                for strategy in self.directional.enabled:
                    moment=self.engine.now()
                    core[strategy]=(evaluate(strategy,moment,self.calendar,spot,future,expiries)
                        if strategy in (GAP,REBOUND) else expanded(strategy,moment,self.calendar,spot,future,expiries,features={}))
                self.directional.update(Inputs(self.calendar,core,dict(self.option_bars),self.engine.now()))
                self.wake.set()
                preload=set()
                for sample in self.directional.signals.values():
                    if not sample.side or not 0 <= (self.engine.now()-sample.evaluated_at).total_seconds()<120:continue
                    contracts=[i for i in self.engine.instruments.values() if i.expiry>=sample.minimum_expiry and i.option_type.value==sample.side]
                    if not contracts:continue
                    expiry=min(i.expiry for i in contracts);contracts=[i for i in contracts if i.expiry==expiry]
                    atm=min(contracts,key=lambda i:(abs(i.strike-sample.spot),i.strike)).strike
                    direction=1 if sample.side=='CE' else -1
                    preload.update(i.security_id for i in sorted((i for i in contracts if direction*(i.strike-atm)>=0),key=lambda i:(direction*(i.strike-atm),i.security_id))[:4])
                active=self.engine.active
                if active and json.loads(active["payload"]).get("strategy",CAS)!=CAS:preload.add(active["security_id"])
                for security in sorted(preload):
                    try:self.option_bars[security]=await self.minutes.fetch(security,'NSE_FNO','OPTIDX',self.calendar.opens,self.engine.now(),oi=True)
                    except Exception:self.option_bars.pop(security,None)
                self.directional.update(Inputs(self.calendar,core,dict(self.option_bars),self.engine.now()))
                self.wake.set()
                # Auxiliary endpoints affect only families which consume them.
                for name in ('BANK','IT','VIX'):
                    required=(name in ('BANK','IT') and families&{'SECTOR_CATCHUP','SECTOR_CONFIRM'}) or (name=='VIX' and 'IV_CHEAP_TREND' in families)
                    if required and self.indexes.get(name):
                        try:
                            features[name]=await self.minutes.fetch(self.indexes[name],'IDX_I','INDEX',self.calendar.opens,now)
                        except Exception:pass
                if 'GIFT_CATCHUP' in families:
                    try:features['GIFT']=await self.features.gift(now)
                    except Exception:pass
                if families:
                    expiry=min(e for e in expiries if e>=now.date())
                    features.update(await self.features.refresh(now,self.calendar,expiry,families))
                    # Freeze exact contract identities. Changing ATM does not
                    # splice different strikes into one return/OI history.
                    options=[i for i in self.engine.instruments.values() if i.expiry==expiry]
                    current=spot.get(now.replace(second=0,microsecond=0))
                    if current and families&{'CHAIN_UNWIND','SKEW_UNWIND','OPTION_ACCEL','OPTION_ACCEL_OI','PRIOR_OI_WALL'}:
                        strikes=sorted({i.strike for i in options});atm=min(strikes,key=lambda k:(abs(k-current.close),k));j=strikes.index(atm)
                        wanted=set(strikes[max(0,j-1):j+2])
                        anchor=spot.get(now.replace(hour=14,minute=45,second=0,microsecond=0))
                        if anchor:wanted.add(min(strikes,key=lambda k:(abs(k-anchor.close),k)))
                        prior=features.get('prior_chain',{});wall_anchor=spot.get(now.replace(hour=9,minute=30,second=0,microsecond=0))
                        if wall_anchor:
                            for side in ('CE','PE'):
                                ks=[(k,oi) for (s,k),oi in prior.get('oi',{}).items() if s==side and abs(k-wall_anchor.close)<=200]
                                if ks:wanted.add(min(ks,key=lambda x:(-x[1],x[0]))[0])
                        features['options']={}
                        for inst in options:
                            if inst.strike not in wanted:continue
                            try:
                                rows=await self.minutes.fetch(inst.security_id,'NSE_FNO','OPTIDX',self.calendar.opens,now,oi=True)
                                self.option_bars[inst.security_id]=rows
                                features['options'][inst.option_type.value,inst.strike]=rows
                            except Exception:pass
            for strategy in self.directional.enabled:
                decision_now=self.engine.now()
                if strategy in (GAP,REBOUND):evaluations[strategy]=evaluate(strategy,decision_now,self.calendar,spot,future,expiries)
                else:
                    from .expanded_strategies import evaluate as expanded
                    evaluations[strategy]=expanded(strategy,decision_now,self.calendar,spot,future,expiries,features=features)
            # Publish signals before option requests so their original minute
            # is never changed by a slow request, nor lost at a minute boundary.
            self.directional.update(Inputs(self.calendar,evaluations,self.option_bars,self.engine.now()))
            needed=set()
            for sample in self.directional.signals.values():
                if sample.evaluated_at.date()!=now.date() or not sample.side:
                    continue
                if now>sample.evaluated_at+timedelta(minutes=2):
                    continue
                instruments=[i for i in self.engine.instruments.values() if i.expiry>=sample.minimum_expiry and i.option_type.value==sample.side]
                if instruments:
                    expiry=min(i.expiry for i in instruments)
                    instruments=[i for i in instruments if i.expiry==expiry]
                    atm=min(instruments,key=lambda i:(abs(i.strike-sample.spot),i.strike)).strike
                    sign=1 if sample.side=="CE" else -1
                    nearest=sorted((i for i in instruments if sign*(i.strike-atm)>=0),key=lambda i:(sign*(i.strike-atm),i.security_id))[:4]
                    needed.update(i.security_id for i in nearest)
            active=self.engine.active
            if active and json.loads(active["payload"]).get("strategy",CAS)!=CAS:
                needed.add(active["security_id"])
            for security in sorted(needed):
                start=self.calendar.opens or now.replace(hour=0,minute=0,second=0,microsecond=0)
                if active and active["security_id"]==security:
                    start=datetime.fromisoformat(json.loads(active["payload"])["signal"]["evaluated_at"])
                try:self.option_bars[security]=await self.minutes.fetch(security,"NSE_FNO","OPTIDX",start,self.engine.now(),oi=True)
                except Exception:self.option_bars.pop(security,None)
            self.directional.update(Inputs(self.calendar,evaluations,dict(self.option_bars),self.engine.now()))
            for sample in evaluations.values():
                identity=f"strategy-evaluation:{sample.strategy}:{sample.evaluated_at.isoformat()}:{sample.state}"
                self.engine.runtime.ledger.observe(identity,"STRATEGY_EVALUATION",asdict(sample))
        except Exception as exc:
            # Never pass a provider error body or authorization material to UI.
            error="STRATEGY_INPUT_UNAVAILABLE:"+type(exc).__name__
            self.directional.update(Inputs(self.calendar,evaluations,{},self.engine.now(),error))
        self.wake.set()

    async def run(self):
        while not self.stop.is_set():
            self.bar_wake.clear()
            await self.refresh()
            # One bar refresh per minute, shortly after its close. Quotes and
            # actual fills still use the existing WebSockets; no fake ticks.
            now=self.engine.now()
            seconds=62-now.second-now.microsecond/1e6
            try:await asyncio.wait_for(self.bar_wake.wait(),max(2,min(60,seconds)))
            except asyncio.TimeoutError:pass
