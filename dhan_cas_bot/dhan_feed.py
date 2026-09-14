from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Mapping
import struct

from .domain import ContractError, Instrument, Level, OptionBook


@dataclass(frozen=True)
class DhanPacket:
    packet_code: int
    declared_length: int
    segment: str
    security_id: str
    bids: tuple[Level, ...]
    asks: tuple[Level, ...]
    provider_ts_ms: int | None


def _level(item: Mapping[str, Any]) -> Level:
    price = Decimal(str(item.get("price")))
    quantity = int(item.get("quantity", 0))
    return Level(price, quantity)


def decode_mapping(packet: Mapping[str, Any], expected: Instrument) -> DhanPacket:
    if packet.get("segment") != expected.segment.value or str(packet.get("security_id")) != expected.security_id:
        raise ContractError("foreign Dhan packet")
    if packet.get("packet") not in {"FULL", 8, "8"}:
        raise ContractError("only Full packets establish the executable book")
    bids = tuple(_level(x) for x in packet.get("bids", ()))[:5]
    asks = tuple(_level(x) for x in packet.get("asks", ()))[:5]
    if not bids and not asks:
        raise ContractError("empty Full packet")
    return DhanPacket(8, int(packet.get("length", 0)), expected.segment.value, expected.security_id, bids, asks, packet.get("provider_ts_ms"))


def decode_full_binary(payload: bytes, expected: Instrument) -> DhanPacket:
    """Decode Dhan v2 FULL (code 8) in its documented little-endian layout."""
    if len(payload) != 163:
        raise ContractError("short Dhan Full packet")
    code, declared, segment_code, security_num = struct.unpack_from("<BhBI", payload, 0)
    expected_num = int(expected.security_id) if expected.security_id.isdigit() else None
    if code != 8 or declared != len(payload) or segment_code != 2 or expected_num is None or security_num != expected_num:
        raise ContractError("invalid Dhan Full packet header")
    import math
    ltp = struct.unpack_from("<f", payload, 8)[0]
    ltt = struct.unpack_from("<i", payload, 14)[0]
    if not math.isfinite(ltp) or ltp < 0:
        raise ContractError("invalid Dhan Full LTP")
    offset = 63
    bids: list[Level] = []
    asks: list[Level] = []
    def price(raw: float) -> Decimal:
        if not math.isfinite(raw) or raw <= 0:
            raise ContractError("non-finite or negative Dhan depth price")
        value = Decimal(str(raw))
        rounded = (value / expected.tick_size).to_integral_value() * expected.tick_size
        if abs(rounded - value) > max(Decimal("0.000001"), abs(value) * Decimal("0.0000002")):
            raise ContractError("Dhan depth price is not tick aligned")
        return rounded
    for _ in range(5):
        bid_qty, ask_qty, _bid_orders, _ask_orders, bid_price, ask_price = struct.unpack_from("<IIhhff", payload, offset)
        offset += 20
        if bid_qty and bid_price > 0:
            bids.append(Level(price(bid_price), bid_qty))
        if ask_qty and ask_price > 0:
            asks.append(Level(price(ask_price), ask_qty))
    # Empty depth invalidates this contract's previous liquidity. It must
    # neither retain the old book nor disconnect all other subscriptions.
    return DhanPacket(code, declared, expected.segment.value, expected.security_id, tuple(bids), tuple(asks), ltt * 1000)


def packets(payload: bytes):
    offset = 0
    while offset < len(payload):
        if len(payload) - offset < 8:
            raise ContractError("truncated Dhan packet header")
        length = int.from_bytes(payload[offset+1:offset+3], "little")
        if length < 8 or offset + length > len(payload):
            raise ContractError("invalid Dhan packet length")
        packet = payload[offset:offset+length]
        if packet[0] == 50:
            raise ContractError("Dhan feed disconnect packet")
        yield packet
        offset += length


def book_from_packet(packet: DhanPacket, expected: Instrument, epoch: str, received_ns: int) -> OptionBook:
    if packet.security_id != expected.security_id or packet.segment != expected.segment.value:
        raise ContractError("packet does not match subscription")
    return OptionBook(expected, packet.bids, packet.asks, epoch, received_ns, packet.provider_ts_ms)
