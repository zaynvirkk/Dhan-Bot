"""Five experimental quote-driven hypotheses; forecasts are not profits.

All timestamps are receipt boundaries. No minute candle supplies a subminute
fill, no quote queue is assumed, and missing event publication data stays unknown.
"""
from collections import deque
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D, ROUND_CEILING
from hashlib import sha256
from statistics import median
from bisect import bisect_right

from .risk import FeeSchedule, worst_case_entry_cash
from .domain import ContractError

NAMES = ('SECONDS_FUTURES_CATCHUP', 'SECONDS_FAILED_BREAKOUT',
         'SECONDS_FLOW_CONTINUATION', 'SECONDS_STRIKE_CATCHUP', 'SECONDS_EVENT_IMPULSE')
LABELS = dict(zip(NAMES, ('Futures catch-up', 'Failed breakout', 'Flow continuation',
                         'Strike catch-up', 'Event impulse')))
RULES = {
 NAMES[0]: 'A two-second futures impulse leaves an option behind its prior fitted response; fees and current depth must still permit entry.',
 NAMES[1]: 'Futures briefly break the preceding one-minute range, return inside, and resume toward its centre with an affordable option.',
 NAMES[2]: 'Persistent option quote pressure, rising premium and traded-volume growth agree with a fresh futures impulse.',
 NAMES[3]: 'A fresh same-expiry option lags both adjacent strikes relative to its own prior curvature; neighbours must be synchronised.',
 NAMES[4]: 'A timestamped official event is received first; a subsequent futures impulse confirms direction before an affordable option entry.',
}


def ns(at):
    return int(at.timestamp()*1_000_000_000)


def future_quote_mid(packet):
    """A FULL book reference on receipt time, never freshness from trade LTT."""
    if not packet.bids or not packet.asks:raise ContractError('future book unavailable')
    bid,ask=packet.bids[0],packet.asks[0]
    if (not bid.price.is_finite() or not ask.price.is_finite() or bid.price<=0
            or ask.price<bid.price or bid.quantity<=0 or ask.quantity<=0
            or (ask.price-bid.price)/bid.price>D('.001')):
        raise ContractError('future book unusable')
    return (bid.price+ask.price)/2


def current(book, at, max_age=1.5):
    return bool(book and book.top_bid and book.top_ask and
                0 <= ns(at)-book.received_ns <= int(max_age*1e9) and
                book.top_bid.price <= book.top_ask.price and
                book.instrument.expiry >= at.date())


def midpoint(book):
    return (book.top_bid.price+book.top_ask.price)/2


def opportunity(name, at, book, target, underlying, episode):
    from .session_strategies import Evaluation
    return Evaluation(name, 'SIGNAL', 'SECONDS_SETUP_DETECTED', at,
        book.instrument.option_type.value, underlying, book.instrument.expiry,
        at+timedelta(seconds=60), {'security_id': book.instrument.security_id,
          'target_price': str(target), 'episode': episode, 'exit_target': None,
          'exit_stop': '.95', 'exit_trail': False, 'seconds_policy': 'SECONDS_V1',
          'anchor_future': str(underlying), 'direction': 1 if book.instrument.option_type.value=='CE' else -1})


@dataclass(frozen=True)
class EntryAssessment:
    candidate: tuple | None
    reason: str
    details: dict


def entry_assessment(sample, books, budget, at):
    """Explain every rejection without mistaking data loss for absent demand."""
    def reject(reason, **details):
        return EntryAssessment(None, reason, details)
    if sample.strategy not in NAMES or sample.state != 'SIGNAL':
        return reject('SECONDS_SIGNAL_CHANGED')
    if not 0 <= (at-sample.evaluated_at).total_seconds() < 5:
        return reject('SECONDS_SIGNAL_EXPIRED')
    b=books.get(sample.details.get('security_id'))
    if not current(b,at):return reject('OPTIONS_FEED_UNAVAILABLE')
    if (b.instrument.option_type.value != sample.side
            or b.instrument.security_id!=sample.details.get('security_id')
            or b.instrument.expiry!=sample.minimum_expiry):
        return reject('SECONDS_OPTION_IDENTITY_MISMATCH')
    i=b.instrument;bid,ask=b.top_bid,b.top_ask;q=i.lot_size
    spread=(ask.price-bid.price)/midpoint(b)
    if spread>D('.01'):return reject('SECONDS_SPREAD_TOO_WIDE',spread_ratio=str(spread))
    if min(bid.quantity,ask.quantity)<q*2:
        return reject('SECONDS_DEPTH_TOO_THIN',bid_quantity=bid.quantity,ask_quantity=ask.quantity,required_depth=q*2)
    limit=ask.price+2*i.tick_size
    if (i.lower_limit and limit<i.lower_limit) or (i.upper_limit and limit>i.upper_limit):
        return reject('SECONDS_ENTRY_OUTSIDE_BAND')
    try: target=D(sample.details['target_price'])
    except (KeyError,ValueError,TypeError):return reject('SECONDS_TARGET_UNAVAILABLE')
    if not target.is_finite() or target<=0:return reject('SECONDS_TARGET_UNAVAILABLE')
    fees=FeeSchedule();debit=worst_case_entry_cash(q,limit)
    exit_fees=fees.sell(q*target,3)
    net=q*target-exit_fees-debit
    minimum=max(D(50),fees.buy(q*limit,1)+exit_fees)
    facts={'entry_cash':str(debit),'exit_fee_reserve':str(exit_fees),'cash_budget':str(budget),
           'net_at_target':str(net),'minimum_net_edge':str(minimum)}
    if not budget.is_finite() or budget<=0 or debit+exit_fees>budget:
        return reject('SECONDS_UNAFFORDABLE',**facts)
    if net<minimum:return reject('SECONDS_NET_EDGE_TOO_SMALL',**facts)
    return EntryAssessment((i,q,limit,b),'READY',facts)


def entry_candidate(sample, books, budget, at):
    return entry_assessment(sample,books,budget,at).candidate


class SecondsTape:
    def __init__(self):
        self.future=deque(maxlen=1200);self.options={};self.selected=set();self.epoch=None;self.future_usable=False
        self.last_samples={};self.last_eval_ns=0
        self.beta_cache={};self.curve_cache={};self.future_index=None

    def reset(self):
        self.future.clear();self.options.clear();self.selected.clear();self.last_samples.clear();self.epoch=None;self.future_usable=False
        self.beta_cache.clear();self.curve_cache.clear();self.future_index=None

    def invalidate_future(self):
        # A bad individual book revokes current-input permission, not valid
        # observations from earlier in this same uninterrupted socket epoch.
        self.future_usable=False

    def future_current(self, at):
        return bool(self.future_usable and self.future and 0<=ns(at)-self.future[-1][0]<=1_500_000_000)

    def future_tick(self, price, received_ns, epoch):
        if not isinstance(price,D) or not price.is_finite() or price<=0:return
        if self.epoch and epoch!=self.epoch:return
        self.epoch=epoch
        if self.future and received_ns<=self.future[-1][0]:return
        self.future_usable=True
        # At most ten observations/second, bounded by receipt time.
        if self.future and received_ns-self.future[-1][0]<100_000_000:return
        self.future.append((received_ns,price))
        self.future_index=None

    def ingest(self, books, at):
        self.selected.clear()
        # Retain prior fit data across brief quote gaps/nearest-strike changes.
        # Retained history never makes an old quote eligible for an entry.
        cutoff=ns(at)-90_000_000_000
        self.options={k:v for k,v in self.options.items() if v and v[-1][0]>=cutoff}
        if not self.future:return
        anchor=self.future[-1][1]
        eligible=[b for b in books.values() if current(b,at) and b.epoch==self.epoch]
        if not eligible:return
        expiry=min(b.instrument.expiry for b in eligible)
        eligible=sorted((b for b in eligible if b.instrument.expiry==expiry),
                        key=lambda b:(abs(b.instrument.strike-anchor),b.instrument.security_id))[:24]
        self.selected={b.instrument.security_id for b in eligible}
        recent=sorted((k for k in self.options if k not in self.selected),
                      key=lambda k:self.options[k][-1][0],reverse=True)[:96-len(self.selected)]
        keep=self.selected|set(recent)
        self.options={k:v for k,v in self.options.items() if k in keep}
        self.beta_cache={k:v for k,v in self.beta_cache.items() if k in keep}
        for b in eligible:
            rows=self.options.setdefault(b.instrument.security_id,deque(maxlen=600))
            if rows and b.received_ns-rows[-1][0]<200_000_000:continue
            stats=b.statistics
            rows.append((b.received_ns,midpoint(b),stats.volume if stats else None,
                         b.top_bid.quantity,b.top_ask.quantity))

    def future_at(self, stamp):
        if self.future_index is None:self.future_index=([t for t,p in self.future],[p for t,p in self.future])
        stamps,prices=self.future_index;i=bisect_right(stamps,stamp)-1
        return prices[i] if i>=0 and stamp-stamps[i]<=2_000_000_000 else None

    def beta(self, security, now_ns):
        cached=self.beta_cache.get(security)
        if cached and 0<=now_ns-cached[0]<5_000_000_000:return cached[1]
        pairs=[]
        for t,p,*_ in self.options.get(security,()):
            if not now_ns-60_000_000_000<=t<=now_ns-5_000_000_000:continue
            f=self.future_at(t)
            if f is not None:pairs.append((f,p))
        if len(pairs)<20:return None
        x=sum(p[0] for p in pairs)/len(pairs);y=sum(p[1] for p in pairs)/len(pairs)
        xx=sum((f-x)**2 for f,p in pairs);yy=sum((p-y)**2 for f,p in pairs)
        if xx<=0 or yy<=0:return None
        xy=sum((f-x)*(p-y) for f,p in pairs);beta=xy/xx
        if not D('.1')<=abs(beta)<=D('.9') or xy*xy/(xx*yy)<D('.4'):return None
        self.beta_cache[security]=(now_ns,beta)
        return beta

    def evaluate(self, at, books, instruments, calendar, *, event=None, budget=None):
        from .session_strategies import Evaluation
        stamp=ns(at)
        result={n:Evaluation(n,'UNKNOWN','FUTURES_FEED_UNAVAILABLE',at) for n in NAMES}
        result[NAMES[4]]=Evaluation(NAMES[4],'UNKNOWN','EVENT_FEED_UNAVAILABLE',at)
        # Calendar state does not depend on receiving after-hours quotes.
        if calendar is not None and calendar.fresh(at) and (not calendar.is_open(at) or at+timedelta(seconds=65)>=calendar.closes):
            return {n:Evaluation(n,'NOT_APPLICABLE','EXCHANGE_CLOSED',at) for n in NAMES}
        if not self.future_current(at):return result
        if calendar is None or not calendar.fresh(at):
            for n in NAMES[:4]:result[n]=Evaluation(n,'UNKNOWN','CALENDAR_UNAVAILABLE',at)
            return result
        self.ingest(books,at)
        if not self.selected:
            for n in NAMES[:4]:result[n]=Evaluation(n,'UNKNOWN','OPTIONS_FEED_UNAVAILABLE',at)
            return result
        warm=D(stamp-self.future[0][0])/D(1e9)
        if warm<60:
            for n in NAMES[:4]:result[n]=Evaluation(n,'WAITING','SECONDS_WARMUP',at,details={'warmup_seconds':str(warm)})
            return result
        future=self.future[-1][1];old=self.future_at(stamp-2_000_000_000)
        if old is None:return result
        move=future-old
        for n in NAMES[:4]:result[n]=Evaluation(n,'NO_SIGNAL','SECONDS_RULE_NOT_MET',at,details={'future_move_2s':str(move)})
        # Event direction is chosen from post-receipt futures, not headline NLP.
        event_ready=False
        if isinstance(event,dict):
            try:
                received=datetime.fromisoformat(event['received_at']);published=datetime.fromisoformat(event['published_at'])
                source=event['source_url']
                official=any(source.startswith(p) for p in ('https://nsearchives.nseindia.com/','https://www.nseindia.com/','https://www.rbi.org.in/','https://www.federalreserve.gov/'))
                event_ready=(official and event.get('underlying')=='NIFTY' and received.tzinfo and published.tzinfo
                    and published<=received<=at and 2<=(at-received).total_seconds()<=60)
            except (KeyError,ValueError,TypeError,AttributeError):pass
        if event_ready:result[NAMES[4]]=Evaluation(NAMES[4],'NO_SIGNAL','SECONDS_RULE_NOT_MET',at)
        eligible=[books[k] for k in self.selected if k in books and current(books[k],at) and books[k].epoch==self.epoch]
        eligible.sort(key=lambda b:(abs(b.instrument.strike-future),b.instrument.security_id))
        fitted_count=0;flow_count=0;curve_count=0
        previous=[p for t,p in self.future if stamp-65_000_000_000<=t<stamp-5_000_000_000]
        recent=[p for t,p in self.future if stamp-5_000_000_000<=t<=stamp]
        breakout_side=0
        if previous and len(recent)>=3:
            hi,lo=max(previous),min(previous)
            if max(recent)>hi+future*D('.0001') and future<hi and recent[-1]<recent[-2]:breakout_side=-1
            elif min(recent)<lo-future*D('.0001') and future>lo and recent[-1]>recent[-2]:breakout_side=1
        def emit(name,b,target,extra=None):
            if result[name].state=='SIGNAL':return
            # One event bucket prevents firing hundreds of copies of a tick.
            episode=sha256(f'{self.epoch}:{name}:{b.instrument.security_id}:{stamp//30_000_000_000}'.encode()).hexdigest()[:24]
            sample=opportunity(name,at,b,target,future,episode)
            if extra:sample=replace(sample,details={**sample.details,**extra})
            sample=replace(sample,exit_at=min(sample.exit_at,calendar.closes-timedelta(seconds=30)))
            assessment=entry_assessment(sample,books,budget if budget is not None else D('1000000000'),at)
            if assessment.candidate is None:
                state='UNKNOWN' if assessment.reason=='OPTIONS_FEED_UNAVAILABLE' else 'NO_SIGNAL'
                result[name]=replace(result[name],state=state,reason=assessment.reason,
                                     details={**assessment.details,'raw_setup_detected':True})
                return
            result[name]=sample
        for b in eligible:
            rows=list(self.options[b.instrument.security_id]);side=1 if b.instrument.option_type.value=='CE' else -1
            beta=self.beta(b.instrument.security_id,stamp)
            if beta is not None and side*beta>0:fitted_count+=1
            anchor=next((r for r in reversed(rows) if r[0]<=stamp-2_000_000_000),None)
            if beta is not None and side*beta>0 and anchor and stamp-anchor[0]<=4_000_000_000:
                f0=self.future_at(anchor[0])
                if f0 and side*move>=future*D('.0002'):
                    emit(NAMES[0],b,anchor[1]+beta*(future-f0),{'response_beta':str(beta)})
                if breakout_side==side and previous:
                    target_future=(max(previous)+min(previous))/2
                    if side*(target_future-future)>0:
                        emit(NAMES[1],b,midpoint(b)+beta*(target_future-future),{'response_beta':str(beta)})
                if event_ready:
                    start=self.future_at(int(received.timestamp()*1e9))
                    if start and side*(future-start)>=future*D('.0003') and side*move>0:
                        emit(NAMES[4],b,midpoint(b)+abs(beta*move),{'response_beta':str(beta)})
            last=rows[-3:]
            if (anchor and len(last)==3 and all(x[2] is not None for x in [anchor,*last])
                    and last[-1][2]>=anchor[2]+b.instrument.lot_size*10
                    and all(a[1]<c[1] for a,c in zip(last,last[1:]))
                    and all(D(r[3]-r[4])/max(1,r[3]+r[4])>=D('.6') for r in last)
                    and side*move>0):
                flow_count+=1
                emit(NAMES[2],b,midpoint(b)+max(D(0),midpoint(b)-anchor[1]))
            peers=sorted((x for x in eligible if x.instrument.option_type==b.instrument.option_type
                          and x.instrument.expiry==b.instrument.expiry),key=lambda x:x.instrument.strike)
            ix=next((i for i,x in enumerate(peers) if x.instrument.security_id==b.instrument.security_id),-1)
            if 0<ix<len(peers)-1:
                left,right=peers[ix-1],peers[ix+1]
                if right.instrument.strike-b.instrument.strike!=b.instrument.strike-left.instrument.strike:continue
                if max(x.received_ns for x in (left,b,right))-min(x.received_ns for x in (left,b,right))>500_000_000:continue
                curve_key=(left.instrument.security_id,b.instrument.security_id,right.instrument.security_id)
                cached=self.curve_cache.get(curve_key)
                if cached and 0<=stamp-cached[0]<5_000_000_000:
                    curve_count+=1
                    emit(NAMES[3],b,(midpoint(left)+midpoint(right))/2-cached[1]);continue
                offsets=[]
                lookup={p.instrument.security_id:([r[0] for r in self.options[p.instrument.security_id]],list(self.options[p.instrument.security_id])) for p in (left,right)}
                for t,p,*_ in rows:
                    if not stamp-60_000_000_000<=t<=stamp-5_000_000_000:continue
                    neighbours=[]
                    for peer in (left,right):
                        stamps,values=lookup[peer.instrument.security_id];i=bisect_right(stamps,t)-1
                        old_row=values[i] if i>=0 and t-values[i][0]<=500_000_000 else None
                        if old_row:neighbours.append(old_row[1])
                    if len(neighbours)==2:offsets.append(sum(neighbours)/2-p)
                if len(offsets)>=20:
                    curve_count+=1
                    curve=D(median(offsets));self.curve_cache[curve_key]=(stamp,curve)
                    emit(NAMES[3],b,(midpoint(left)+midpoint(right))/2-curve)
        # A mathematical discrepancy with negative conditional net value is
        # a failed condition, not a real trading signal.
        for name,sample in list(result.items()):
            if sample.state=='SIGNAL' and entry_candidate(sample,books,D('1000000000'),at) is None:
                result[name]=replace(sample,state='NO_SIGNAL',reason='SECONDS_EDGE_BELOW_COSTS',side=None)
        diagnostics={'future_move_2s':str(move),'impulse_threshold':str(future*D('.0002')),
            'eligible_contracts':str(len(eligible)),'fitted_contracts':str(fitted_count),
            'breakout_direction':str(breakout_side),'flow_candidates':str(flow_count),'curvature_candidates':str(curve_count)}
        for name in NAMES[:4]:
            result[name]=replace(result[name],details={**result[name].details,**diagnostics})
        return result
