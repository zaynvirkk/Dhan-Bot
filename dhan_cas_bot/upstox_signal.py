from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Mapping
import math

from .domain import CasPhase, CasStatus, ContractError, IndexObservation


NIFTY_KEY = "NSE_INDEX|Nifty 50"
CAS_SEGMENT = "NSE_EQ"
REQUIRED_PHASES = {x.value for x in CasPhase if x is not CasPhase.UNKNOWN}


def _get(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _present(message: Any, field: str) -> bool:
    if isinstance(message, Mapping):
        return field in message and message[field] is not None
    has = getattr(message, "HasField", None)
    if callable(has):
        try:
            return bool(has(field))
        except (ValueError, KeyError):
            return False
    return hasattr(message, field) and getattr(message, field) is not None


def _feed(response: Any) -> Any:
    feeds = _get(response, "feeds", {})
    if isinstance(feeds, Mapping):
        return feeds.get(NIFTY_KEY)
    return None


def extract_iep(response: Any) -> Decimal:
    """Extract only the official full/index/LTPC/iep wrapper path."""
    feed = _feed(response)
    if feed is None or not _present(feed, "fullFeed"):
        raise ContractError("missing fullFeed for NIFTY")
    full = _get(feed, "fullFeed")
    if not _present(full, "indexFF"):
        raise ContractError("NIFTY feed is not indexFF")
    index = _get(full, "indexFF")
    if not _present(index, "ltpc"):
        raise ContractError("missing NIFTY LTPC")
    ltpc = _get(index, "ltpc")
    if not _present(ltpc, "iep"):
        raise ContractError("missing IEP wrapper")
    wrapper = _get(ltpc, "iep")
    value = _get(wrapper, "value") if not isinstance(wrapper, (str, int, Decimal, float)) else wrapper
    try:
        result = Decimal(str(value))
    except Exception as exc:
        raise ContractError("invalid IEP") from exc
    if not result.is_finite() or result <= 0:
        raise ContractError("IEP must be finite and positive")
    return result


def extract_ltp(response: Any) -> Decimal:
    feed = _feed(response)
    if feed is None or not _present(feed, "fullFeed"):
        raise ContractError("missing fullFeed")
    full = _get(feed, "fullFeed")
    if not _present(full, "indexFF"):
        raise ContractError("missing indexFF")
    ltpc = _get(_get(full, "indexFF"), "ltpc")
    ltp = _get(ltpc, "ltp")
    try:
        result = Decimal(str(ltp))
    except Exception as exc:
        raise ContractError("invalid LTP") from exc
    if not result.is_finite() or result <= 0:
        raise ContractError("LTP must be finite and positive")
    return result


def extract_status(response: Any, *, trading_date, epoch: str) -> CasStatus | None:
    info = _get(_get(response, "marketInfo", {}), "casMarketStatus", {})
    value = info.get(CAS_SEGMENT) if isinstance(info, Mapping) else None
    if value is None:
        return None
    phase_name = str(_get(value, "status", "UNKNOWN"))
    phase = CasPhase(phase_name) if phase_name in REQUIRED_PHASES else CasPhase.UNKNOWN
    updated = _get(value, "updatedTime")
    if not isinstance(updated, int) or updated < 0:
        raise ContractError("CAS status updatedTime is invalid")
    return CasStatus(phase, updated, trading_date, epoch)


def decode_binary(payload: bytes) -> Any:
    from .proto import FeedResponse
    try:
        return FeedResponse.FromString(payload)
    except Exception as exc:
        raise ContractError("invalid Upstox V3 protobuf frame") from exc


def observation(response: Any, *, received_ns: int, provider_ts_ms: int, epoch: str, receiver_seq: int, raw_identity: str, ltp: bool = False) -> IndexObservation:
    value = extract_ltp(response) if ltp else extract_iep(response)
    return IndexObservation(value, provider_ts_ms, received_ns, epoch, receiver_seq, raw_identity=raw_identity)


def dedupe_key(epoch: str, provider_ts_ms: int, payload_digest: str) -> tuple[str, int, str]:
    return epoch, provider_ts_ms, payload_digest
