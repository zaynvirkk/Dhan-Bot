from decimal import Decimal
import pytest

from dhan_cas_bot.domain import ContractError, Instrument, OptionType, Segment
from dhan_cas_bot.upstox_signal import extract_iep
from dhan_cas_bot.dhan_feed import decode_mapping
from dhan_cas_bot.dhan_feed import decode_full_binary
import struct
from datetime import date


def valid():
    return {"feeds": {"NSE_INDEX|Nifty 50": {"fullFeed": {"indexFF": {"ltpc": {"iep": {"value": 25000}}}}}}}


def test_official_upstox_path_and_presence():
    assert extract_iep(valid()) == Decimal("25000")
    missing = valid(); del missing["feeds"]["NSE_INDEX|Nifty 50"]["fullFeed"]["indexFF"]["ltpc"]["iep"]
    with pytest.raises(ContractError): extract_iep(missing)
    wrong = valid(); wrong["feeds"]["NSE_INDEX|Nifty 50"]["fullFeed"]["marketFF"] = wrong["feeds"]["NSE_INDEX|Nifty 50"]["fullFeed"].pop("indexFF")
    with pytest.raises(ContractError): extract_iep(wrong)


def test_dhan_foreign_packet_rejected():
    inst = Instrument("1", "NIFTY", Segment.NSE_FNO, date(2026, 9, 15), OptionType.PE, Decimal("23650"), 65, Decimal("0.05"), 1800)
    with pytest.raises(ContractError): decode_mapping({"packet":"FULL", "segment":"NSE_EQ", "security_id":"1", "bids":[], "asks":[]}, inst)


def test_dhan_documented_full_binary_packet():
    inst = Instrument("1", "NIFTY", Segment.NSE_FNO, date(2026, 9, 15), OptionType.PE, Decimal("23650"), 65, Decimal("0.05"), 1800)
    payload = bytearray(struct.pack("<BhBI", 8, 163, 2, 1))
    payload.extend(struct.pack("<fhi", 10.0, 1, 100))
    payload.extend(b"\0" * (63 - len(payload)))
    for i in range(5): payload.extend(struct.pack("<IIhhff", 65 if i == 0 else 0, 195 if i == 0 else 0, 1, 1, 9.0 - i * .05, 10.0 + i * .05))
    packet = decode_full_binary(bytes(payload), inst)
    assert packet.security_id == "1" and packet.bids[0].quantity == 65 and packet.asks[0].quantity == 195
