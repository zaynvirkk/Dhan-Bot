"""Pure, timestamp-bounded rules for the two recorded NIFTY experiments.

These rules describe hypotheses, not a profitability qualification. Bar keys
are availability times (start + one minute); daily membership comes from the
contract catalogue and the exchange calendar, never weekday arithmetic.
"""
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from .domain import ContractError, dec

IST = ZoneInfo("Asia/Kolkata")
CAS = "CAS_LAG_V1"
GAP = "GAP_FADE_DOUBLE"
REBOUND = "NIFTY_SELLOFF_REBOUND_1510"
STRATEGIES = (GAP, REBOUND, CAS)
D = Decimal


@dataclass(frozen=True)
class Bar:
    available: datetime
    open: Decimal
    close: Decimal
    volume: int
    oi: int


@dataclass(frozen=True)
class Calendar:
    opens: datetime | None
    closes: datetime | None
    previous_opens: datetime
    previous_closes: datetime
    next_opens: datetime
    next_closes: datetime
    checked_at: datetime
    day: date | None = None

    def fresh(self, now):
        return (self.checked_at.tzinfo is not None
                and self.checked_at.astimezone(IST).date() == now.astimezone(IST).date()
                and 0 <= (now-self.checked_at).total_seconds() <= 12*3600
                and (self.opens.date() if self.opens else self.day) == now.astimezone(IST).date())

    def is_open(self, now):
        return bool(self.fresh(now) and self.opens and self.opens <= now < self.closes)


@dataclass(frozen=True)
class Evaluation:
    strategy: str
    state: str
    reason: str
    evaluated_at: datetime
    side: str | None = None
    spot: Decimal | None = None
    minimum_expiry: date | None = None
    exit_at: datetime | None = None
    details: dict = field(default_factory=dict)


def parse_session(payload, day):
    if not isinstance(payload, dict) or payload.get("status") != "success" or not isinstance(payload.get("data"), list):
        raise ContractError("market calendar unavailable")
    if any(not isinstance(row, dict) or not row.get("exchange") for row in payload["data"]):
        raise ContractError("invalid market calendar row")
    rows = [row for row in payload["data"] if row.get("exchange") == "NFO"]
    if not rows:
        return None  # authoritative successful response, not a request failure
    if len(rows) != 1:
        raise ContractError("ambiguous NFO trading session")
    try:
        stamps = [rows[0][name] for name in ("start_time", "end_time")]
        if any(type(value) is not int for value in stamps):
            raise ContractError("nonintegral calendar timestamp")
        start, end = [datetime.fromtimestamp(value/1000, IST) for value in stamps]
        if start.date() != day or end.date() != day or start >= end:
            raise ContractError("inconsistent calendar date")
        return start, end
    except (KeyError, OverflowError, OSError) as exc:
        raise ContractError("invalid calendar timestamps") from exc


def parse_bars(payload, received_at, *, require_oi=False):
    names = ("timestamp", "open", "high", "low", "close", "volume")
    if not isinstance(payload, dict) or any(not isinstance(payload.get(key), list) for key in names):
        raise ContractError("minute history unavailable")
    size = len(payload["timestamp"])
    if any(len(payload[key]) != size for key in names):
        raise ContractError("misaligned minute history")
    oi = payload.get("open_interest")
    if oi is None and not require_oi:
        oi = [0]*size
    if not isinstance(oi, list) or len(oi) != size:
        raise ContractError("open interest history unavailable")
    result = {}
    seen = set()
    for i, stamp in enumerate(payload["timestamp"]):
        if type(stamp) is not int or stamp % 60 or stamp in seen:
            raise ContractError("ambiguous minute timestamp")
        seen.add(stamp)
        available = datetime.fromtimestamp(stamp, IST)+timedelta(minutes=1)
        prices = [dec(payload[key][i], key) for key in ("open", "high", "low", "close")]
        op, hi, lo, close = prices
        volume, interest = payload["volume"][i], oi[i]
        if min(prices) <= 0 or not lo <= min(op, close) <= max(op, close) <= hi:
            raise ContractError("invalid minute OHLC")
        if any(type(v) is not int or v < 0 for v in (volume, interest)):
            raise ContractError("invalid minute quantities")
        if available <= received_at:
            result[available] = Bar(available, op, close, volume, interest)
    return dict(sorted(result.items()))


def evaluate(strategy, now, calendar, spot, future, expiries):
    now = now.astimezone(IST)
    at = now.replace(second=0, microsecond=0)
    def result(state, reason, **kw):
        return Evaluation(strategy, state, reason, at, **kw)
    if strategy not in (GAP, REBOUND):
        raise ContractError("unknown directional strategy")
    if calendar is None or not calendar.fresh(now):
        return result("UNKNOWN", "CALENDAR_UNAVAILABLE")
    if not calendar.is_open(now):
        return result("WAITING", "EXCHANGE_CLOSED")
    if not expiries:
        return result("UNKNOWN", "CONTRACT_CALENDAR_UNAVAILABLE")
    if strategy == GAP and now.date() in expiries:
        return result("NOT_APPLICABLE", "EXPIRY_SESSION_OUTSIDE_RESEARCH_SCOPE")
    if (strategy == GAP and not (time(9,45) <= now.time() < time(11,31) and now.minute % 5 == 0)
            or strategy == REBOUND and (now.hour, now.minute) != (15,10)):
        return result("WAITING", "OUTSIDE_STRATEGY_WINDOW")
    # Research assumes the regular opening session; special sessions do not
    # inherit its thresholds merely because a market happens to be open.
    if calendar.opens.time() != time(9,15):
        return result("NOT_APPLICABLE", "SPECIAL_SESSION_OUTSIDE_RESEARCH_SCOPE")
    try:
        opening = spot[calendar.opens+timedelta(minutes=1)].open
        current = spot[at].close
        if min(opening, current) <= 0:
            raise ContractError("nonpositive index reference")
        if strategy == REBOUND:
            change = current/opening-1
            exit_at = datetime.combine(calendar.next_opens.date(), time(15,10), IST)
            if not calendar.next_opens < exit_at < calendar.next_closes:
                return result("UNKNOWN", "NEXT_SESSION_EXIT_UNAVAILABLE")
            side = "CE" if change <= D("-.0075") else None
            return result("SIGNAL" if side else "NO_SIGNAL", "SELLOFF_THRESHOLD_MET" if side else "SELLOFF_BELOW_THRESHOLD",
                          side=side, spot=current, minimum_expiry=exit_at.date()+timedelta(days=1),
                          exit_at=exit_at, details={"open_return":str(change)})
        previous = spot[calendar.previous_closes].close
        if previous <= 0:
            raise ContractError("nonpositive previous close")
        gap = opening/previous-1
        direction = -1 if gap > 0 else 1
        fraction = (opening-current)/(opening-previous) if opening != previous else D(0)
        closes = [spot[at-timedelta(minutes=i)].close for i in (2,1,0)]
        f5 = future[at].close / future[at-timedelta(minutes=5)].close-1
        persistent = all(direction*(b-a)>0 for a,b in zip(closes, closes[1:]))
        yes = abs(gap)>=D(".005") and D(".25")<=fraction<=1 and direction*f5>0 and persistent
        return result("SIGNAL" if yes else "NO_SIGNAL", "GAP_FADE_CONFIRMED" if yes else "GAP_FADE_CONDITIONS_NOT_MET",
                      side=("CE" if direction>0 else "PE") if yes else None, spot=current,
                      minimum_expiry=now.date(), exit_at=calendar.closes-timedelta(minutes=6),
                      details={"gap":str(gap), "fraction_filled":str(fraction), "future_5m_return":str(f5), "persistent":persistent})
    except (KeyError, ArithmeticError, ContractError):
        return result("UNKNOWN", "COMPLETED_INPUT_MISSING_OR_INVALID")
