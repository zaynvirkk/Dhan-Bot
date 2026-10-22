"""shock_v1: causal hypothesis and finite-book scenarios, never expected profit.

Money stays Decimal. Only the isolated European zero-rate/zero-dividend pricing
calibration uses float; resulting scenario cash is rounded DOWN to instrument ticks.
"""
from dataclasses import dataclass, field, replace
from datetime import datetime, date, time, timedelta
from decimal import Decimal as D, ROUND_FLOOR
from hashlib import sha256
from math import erf, exp, isfinite, log, sqrt, ceil
from statistics import median

from .session_strategies import Evaluation, IST
from .risk import Allocation, FeeSchedule, worst_case_entry_cash

SHOCK = 'VOLATILITY_SHOCK_V1'
RULE = 'shock_v1'
ALLOCATION = 'SHOCK_FULL_CASH_V1'
EXIT = 'SHOCK_EXIT_V1'


@dataclass(frozen=True)
class ShockConfig:
    revision: str = RULE
    minimum_bars: int = 35
    shock: D = D('.0030')
    abnormal_multiple: D = D(2)
    breakout_buffer: D = D('.0002')
    maximum_extension: D = D('.0055')
    future_minimum: D = D('.001')
    volume_multiple: D = D('1.3')
    validity_seconds: int = 30
    cooldown_minutes: int = 15


@dataclass(frozen=True)
class ShockFeatureSnapshot:
    bar_at: datetime
    received_at: datetime
    source: str
    spot_bars: tuple
    future_bars: tuple
    volume_semantics: str = 'DHAN_INTRADAY_PER_MINUTE'


def episode_id(day, direction, available, revision=RULE):
    return sha256(f'{day}|{direction}|{available.isoformat()}|{revision}'.encode()).hexdigest()[:24]


def flatten_at(calendar):
    # Ten-minute margin also handles verified shortened sessions.
    return min(datetime.combine(calendar.opens.date(), time(15,15), IST),
               calendar.closes-timedelta(minutes=10))


def evaluate_completed_shock(now, calendar, spot, future, *, bar_at, source='DHAN_INTRADAY_PER_MINUTE', config=ShockConfig()):
    details={'rule_version':config.revision,'decision_minute':bar_at.isoformat(),'source':source}
    conditions=[]
    def result(state,reason,side=None):
        return Evaluation(SHOCK,state,reason,bar_at,side,
            spot[bar_at].close if bar_at in spot else None,
            now.astimezone(IST).date(),flatten_at(calendar) if calendar and calendar.opens else None,
            details,conditions)
    if not calendar or not calendar.fresh(now):return result('INPUT_UNAVAILABLE','CALENDAR_UNAVAILABLE')
    if not calendar.is_open(now):return result('WAITING','EXCHANGE_CLOSED')
    local=now.astimezone(IST)
    if not time(9,50)<=bar_at.astimezone(IST).time()<=time(14,45) or now>=flatten_at(calendar):
        return result('WAITING','OUTSIDE_STRATEGY_WINDOW')
    if bar_at.second or bar_at.microsecond or not 0<=(now-bar_at).total_seconds()<=config.validity_seconds:
        return result('INPUT_UNAVAILABLE','SHOCK_COMPLETED_BAR_UNAVAILABLE')
    times=[bar_at-timedelta(minutes=n) for n in range(config.minimum_bars)]
    if times[-1]<calendar.opens+timedelta(minutes=1):return result('WAITING','SHOCK_WARMUP')
    if any(t not in spot or t not in future for t in times):return result('INPUT_UNAVAILABLE','SHOCK_NONCONTIGUOUS_BARS')
    for rows in (spot,future):
        if any(rows[t].available!=t or any(not isinstance(x,D) or not x.is_finite() or x<=0
            for x in (rows[t].open,rows[t].close,rows[t].high,rows[t].low)) or rows[t].low>min(rows[t].open,rows[t].close)
            or rows[t].high<max(rows[t].open,rows[t].close) for t in times):
            return result('INPUT_UNAVAILABLE','SHOCK_INVALID_BAR')
    details.update(bar_at=bar_at.isoformat(),source_received_at=now.isoformat())
    r5=spot[bar_at].close/spot[bar_at-timedelta(minutes=5)].close-1
    direction=1 if r5>0 else -1
    baseline=[abs(spot[t].close/spot[t-timedelta(minutes=5)].close-1)
              for n in range(6,31) if (t:=bar_at-timedelta(minutes=n)) in spot
              and t-timedelta(minutes=5) in spot and t-timedelta(minutes=5)>=calendar.opens+timedelta(minutes=1)]
    if len(baseline)<20 or median(baseline)<=0:return result('INPUT_UNAVAILABLE','SHOCK_BASELINE_UNAVAILABLE')
    prior=[spot[bar_at-timedelta(minutes=n)] for n in range(2,32)]
    high=max(b.high for b in prior);low=min(b.low for b in prior)
    boundary=high if direction>0 else low
    confirmed=all(direction*(spot[bar_at-timedelta(minutes=n)].close-boundary*(1+direction*config.breakout_buffer))>0 for n in (0,1))
    extension=direction*(spot[bar_at].close/boundary-1)
    f5=future[bar_at].close/future[bar_at-timedelta(minutes=5)].close-1
    # Nonoverlapping baseline windows, before the last three completed minutes.
    earlier=sorted(t for t in future if calendar.opens<t<=bar_at-timedelta(minutes=3))
    windows=[]
    for start in range(0,len(earlier)-2,3):
        ts=earlier[start:start+3]
        if ts[2]-ts[0]==timedelta(minutes=2):windows.append(sum(future[t].volume for t in ts))
    if len(windows)<5 or median(windows)<=0 or any(type(future[t].volume) is not int or future[t].volume<0 for t in times):
        return result('INPUT_UNAVAILABLE','SHOCK_VOLUME_UNAVAILABLE')
    volume=D(sum(future[bar_at-timedelta(minutes=n)].volume for n in range(3)))/D(median(windows))
    details.update(spot_5m=r5,prior_abs_r5=D(median(baseline)),pre_break_high=high,pre_break_low=low,
                   breakout_boundary=boundary,extension=extension,future_5m_return=f5,volume_ratio=volume,
                   baseline_comparisons=len(baseline),volume_windows=len(windows))
    tests=[('shock_size',abs(r5),config.shock,abs(r5)>=config.shock),
           ('shock_abnormal',abs(r5)/D(median(baseline)),config.abnormal_multiple,abs(r5)>=config.abnormal_multiple*D(median(baseline))),
           ('persistence',D(int(confirmed)),D(1),confirmed),
           ('extension',extension,config.maximum_extension,0<=extension<=config.maximum_extension),
           ('future_direction',direction*f5,config.future_minimum,direction*f5>=config.future_minimum),
           ('volume_ratio',volume,config.volume_multiple,volume>=config.volume_multiple)]
    for name,value,threshold,passed in tests:
        conditions.append({'key':name,'state':'PASS' if passed else 'FAIL','value':value,
                           'maximum' if name=='extension' else 'minimum':threshold})
    if not all(t[3] for t in tests):return result('NO_SIGNAL','SHOCK_RULE_NOT_MET')
    details['episode']=episode_id(local.date(),direction,bar_at)
    return result('SIGNAL','SHOCK_CONFIRMED','CE' if direction>0 else 'PE')


def shock_allocation(allocation):
    """Scoped rule; generic allocations and mandate consumption are unchanged."""
    consumed_reserved=max(D(0),allocation.ceiling-allocation.remaining)
    return replace(allocation,ceiling=allocation.bankroll,remaining=max(D(0),allocation.bankroll-consumed_reserved))


def contract_cutoff(instrument, calendar):
    closing=calendar.closes
    day=calendar.opens.astimezone(IST).date()
    if day>=date(2026,12,7) and instrument.expiry==day:
        closing=min(closing,datetime.combine(day,time(15,30),IST))
    return closing


def shock_universe(instruments, side, spot, day):
    rows=[i for i in instruments if i.expiry>=day and i.option_type.value==side]
    result=[];direction=1 if side=='CE' else -1
    for expiry in sorted({i.expiry for i in rows})[:2]:
        group=[i for i in rows if i.expiry==expiry]
        atm=min(group,key=lambda i:(abs(i.strike-spot),i.strike)).strike
        outward=sorted((i for i in group if direction*(i.strike-atm)>=0),key=lambda i:(abs(i.strike-atm),i.security_id))[:13]
        inward=sorted((i for i in group if direction*(i.strike-atm)<0),key=lambda i:(abs(i.strike-atm),i.security_id))[:2]
        result.extend((*inward,*outward))
    return result


def option_value(spot,strike,years,vol,side):
    values=[float(x) for x in (spot,strike,years,vol)]
    s,k,t,v=values
    if any(not isfinite(x) for x in values) or min(s,k)<=0 or min(t,v)<0 or side not in ('CE','PE'):
        raise ValueError('invalid pricing inputs')
    if not t or not v:return max(D(0),(spot-strike) if side=='CE' else (strike-spot))
    d1=(log(s/k)+v*v*t/2)/(v*sqrt(t));d2=d1-v*sqrt(t)
    normal=lambda x:(1+erf(x/sqrt(2)))/2
    value=s*normal(d1)-k*normal(d2) if side=='CE' else k*normal(-d2)-s*normal(-d1)
    return max(D(0),D(str(value)))


def implied_volatility(spot,strike,years,price,side):
    intrinsic=max(D(0),spot-strike if side=='CE' else strike-spot)
    upper=spot if side=='CE' else strike
    if years<=0 or not intrinsic<price<upper:raise ValueError('impossible option quote')
    lo=D('.000001');hi=D(8)
    if option_value(spot,strike,years,hi,side)<price:raise ValueError('IV out of bounds')
    for _ in range(70):
        mid=(lo+hi)/2
        if option_value(spot,strike,years,mid,side)<price:lo=mid
        else:hi=mid
    return (lo+hi)/2


@dataclass(frozen=True)
class ShockCandidate:
    instrument: object
    quantity: int
    limit: D
    book: object
    entry_cash: D
    exit_reserve: D
    scenario_multiple: D
    ending_bankroll: D
    assumptions: dict = field(default_factory=dict)


def select_shock_candidate(signal,instruments,books,cash,now,calendar):
    candidates=[];checks=[];fees=FeeSchedule()
    universe=shock_universe(instruments,signal.side,signal.spot,now.astimezone(IST).date())
    if not universe:return None,[{'reason':'SHOCK_EXPIRY_CUTOFF','budget':str(cash)}]
    for inst in universe:
        row={'security_id':inst.security_id,'strike':str(inst.strike),'expiry':str(inst.expiry),'budget':str(cash),'lot_size':inst.lot_size}
        checks.append(row)
        def reject(reason):row['reason']=reason
        book=books.get(inst.security_id)
        if not book or not 0<=int(now.timestamp()*1e9)-book.received_ns<=2_000_000_000:
            reject('OPTION_BOOK_UNAVAILABLE_OR_STALE');continue
        bid,ask=book.top_bid,book.top_ask
        if not bid or not ask or bid.price>ask.price:
            reject('SHOCK_INVALID_BOOK');continue
        spread=(ask.price-bid.price)/((ask.price+bid.price)/2)
        if spread>D('.015'):reject('SHOCK_SPREAD_TOO_WIDE');continue
        cutoff=contract_cutoff(inst,calendar)
        if (cutoff-now).total_seconds()<3600:reject('SHOCK_EXPIRY_CUTOFF');continue
        expiry_clock=time(15,30) if inst.expiry>=date(2026,12,7) else cutoff.astimezone(IST).time()
        expiry_time=datetime.combine(inst.expiry,expiry_clock,IST)
        years=D(str((expiry_time-now).total_seconds()))/D(365*86400)
        horizon=min(D(45*60),D(str((cutoff-now).total_seconds()))-1800)
        direction=1 if signal.side=='CE' else -1
        move=min(D('.018'),max(D('.006'),D('1.75')*abs(D(signal.details['spot_5m']))))
        scenario_spot=signal.spot*(1+direction*move)
        try:
            iv=implied_volatility(signal.spot,inst.strike,years,(ask.price+bid.price)/2,signal.side)
            scenario=option_value(scenario_spot,inst.strike,years-horizon/D(365*86400),iv*D('.9'),signal.side)
            scenario=(scenario/inst.tick_size).to_integral_value(rounding=ROUND_FLOOR)*inst.tick_size
        except (ValueError,ArithmeticError,OverflowError):reject('SHOCK_IV_UNAVAILABLE');continue
        # At most two ticks and never over 0.4% above CURRENT ask.
        allowance=min(2*inst.tick_size,ask.price*D('.004'))
        limit=((ask.price+allowance)/inst.tick_size).to_integral_value(rounding=ROUND_FLOOR)*inst.tick_size
        if limit<ask.price or (inst.lower_limit and limit<inst.lower_limit) or (inst.upper_limit and limit>inst.upper_limit):
            reject('OPTION_LIMIT_OUTSIDE_BAND');continue
        ask_capacity=sum(l.quantity for l in book.asks if l.price<=limit)
        bid_capacity=sum(l.quantity for l in book.bids if l.price>=max(inst.tick_size,bid.price-2*inst.tick_size))
        capacity=min(inst.freeze_qty,ask_capacity,bid_capacity)
        quantity=0;entry=reserve=D(0)
        for q in range(inst.lot_size,capacity+1,inst.lot_size):
            debit=worst_case_entry_cash(q,limit)
            reserve=fees.sell(q*max(limit,scenario),3)
            if debit+reserve>cash:break
            quantity=q;entry=debit
        if not quantity:reject('NO_AFFORDABLE_LIQUID_CONTRACT');continue
        reserve=fees.sell(quantity*max(limit,scenario),3)
        proceeds=quantity*scenario-fees.sell(quantity*scenario,1)
        multiple=proceeds/entry
        charges=fees.buy(quantity*limit,1)+fees.sell(quantity*scenario,1)
        gross_profit=quantity*(scenario-limit)
        row.update(limit=str(limit),quantity=quantity,entry_cash=str(entry),exit_fee_reserve=str(reserve),
                   scenario_multiple=str(multiple),scenario_only=True)
        if multiple<D('1.8') or gross_profit<3*charges:reject('SHOCK_SCENARIO_BELOW_FLOOR');continue
        assumptions={'model':'EUROPEAN_BS_ZERO_RATE_ZERO_DIVIDEND','iv':str(iv),'stressed_iv':str(iv*D('.9')),
            'spot':str(signal.spot),'scenario_spot':str(scenario_spot),'scenario_premium':str(scenario),
            'horizon_seconds':str(horizon),'years':str(years),'quote_received_ns':book.received_ns,
            'spread_ratio':str(spread),'expiry_intrinsic_now':str(max(D(0),direction*(signal.spot-inst.strike))),
            'scenario_only':True,'time_basis':'ACT_365_CALENDAR_SECONDS','allocation_policy':ALLOCATION}
        candidates.append(ShockCandidate(inst,quantity,limit,book,entry,reserve,multiple,cash-entry+proceeds,assumptions))
        reject('READY')
    candidates.sort(key=lambda c:(c.ending_bankroll,-D(c.assumptions['spread_ratio']),
        sum(l.quantity for l in c.book.bids),c.book.received_ns,c.instrument.security_id),reverse=True)
    return (candidates[0] if candidates else None),checks


def shock_exit(entry_cash,net_profit,held_minutes,previous,invalidated,*,deadline=False):
    old=previous or {};peak=D(old.get('peak_net_profit','0'))
    if net_profit is not None:peak=max(peak,net_profit)
    armed=bool(old.get('trailing_armed')) or peak>=entry_cash*D('.8')
    floor=max(D(old.get('floor','0')),max(peak*D('.4'),peak-entry_cash*D('.45'))) if armed else D(0)
    state={'version':EXIT,'peak_net_profit':str(peak),'floor':str(floor),'trailing_armed':armed,
           'net_liquidation_profit':str(net_profit) if net_profit is not None else None}
    reason=old.get('triggered_reason')
    if reason is None:
        if invalidated:reason='SHOCK_UNDERLYING_INVALIDATED'
        elif net_profit is not None and net_profit<=-entry_cash*D('.4'):reason='SHOCK_PREMIUM_STOP'
        elif armed and net_profit is not None and net_profit<floor:reason='SHOCK_PROFIT_FLOOR'
        elif held_minutes>=45 and peak<entry_cash*D('.2'):reason='SHOCK_NO_MOMENTUM'
        elif held_minutes>=120 or deadline:reason='SHOCK_MAX_EXPOSURE'
    if reason:state['triggered_reason']=reason
    return state,reason
