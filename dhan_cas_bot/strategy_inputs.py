"""Read-only minute inputs alongside the existing WebSocket execution feeds."""
import asyncio
from csv import DictReader
from dataclasses import asdict
from datetime import datetime, time, timedelta, timezone
from io import StringIO
import json

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
    return ((GAP in enabled and not expiry_today and time(9,40)<=local.time()<time(11,31))
            or (REBOUND in enabled and time(15,5)<=local.time()<time(15,10)))


class CalendarSource:
    def __init__(self, token, *, client=None):
        self.token, self.client = token, client

    async def fetch(self, now):
        if not self.token:
            raise ContractError("UPSTOX_CALENDAR_AUTH_UNAVAILABLE")
        day=now.astimezone(IST).date()
        own=self.client is None
        client=self.client or httpx.AsyncClient(timeout=5,follow_redirects=False)
        async def session(day):
            response=await client.get("https://api.upstox.com/v2/market/timings/"+str(day),headers={"Authorization":"Bearer "+self.token})
            response.raise_for_status()
            return parse_session(response.json(),day)
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
            return Calendar(*(current or (None,None)),*adjacent,now,day)
        finally:
            if own:
                await client.aclose()


class MinuteSource:
    def __init__(self, broker, *, now_fn=None):
        self.broker=broker
        self.now=now_fn or (lambda:datetime.now(timezone.utc))

    async def fetch(self, security, segment, instrument, start, end, *, oi=False):
        request={"securityId":security,"exchangeSegment":segment,"instrument":instrument,"interval":"1","oi":oi,
                 "fromDate":start.astimezone(IST).strftime("%Y-%m-%d %H:%M:%S"),
                 "toDate":end.astimezone(IST).strftime("%Y-%m-%d %H:%M:%S")}
        raw=await self.broker._request("POST","/charts/intraday",json=request)
        return parse_bars(raw,self.now(),require_oi=oi)


class StrategyInputWorker:
    def __init__(self, directional, token, future_id, *, wake, stop):
        self.directional=directional
        self.engine=directional.engine
        self.calendar_source=CalendarSource(token)
        self.minutes=MinuteSource(self.engine.runtime.broker,now_fn=self.engine.now)
        self.future_id=future_id
        self.wake,self.stop=wake,stop
        self.calendar=None
        self.option_bars={}
        self.last_calendar_error=""

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
            if self.calendar.is_open(now):
                spot=await self.minutes.fetch("13","IDX_I","INDEX",self.calendar.previous_opens,now)
                if GAP in self.directional.enabled and time(9,44)<=now.time()<time(11,32) and now.date() not in expiries:
                    if self.future_id:
                        await asyncio.sleep(.25)
                        future=await self.minutes.fetch(self.future_id,"NSE_FNO","FUTIDX",self.calendar.opens,now,oi=True)
            for strategy in self.directional.enabled:
                evaluations[strategy]=evaluate(strategy,now,self.calendar,spot,future,expiries)
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
                await asyncio.sleep(.25)
                start=self.calendar.opens or now.replace(hour=0,minute=0,second=0,microsecond=0)
                if active and active["security_id"]==security:
                    start=datetime.fromisoformat(json.loads(active["payload"])["signal"]["evaluated_at"])
                self.option_bars[security]=await self.minutes.fetch(security,"NSE_FNO","OPTIDX",start,self.engine.now(),oi=True)
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
            await self.refresh()
            # One bar refresh per minute, shortly after its close. Quotes and
            # actual fills still use the existing WebSockets; no fake ticks.
            now=self.engine.now()
            seconds=62-now.second-now.microsecond/1e6
            await asyncio.sleep(max(2,min(60,seconds)))
