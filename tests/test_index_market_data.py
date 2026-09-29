"""Public wire format and inventory boundary cases; no live orders."""
import csv
import io
import struct
from datetime import date
from decimal import Decimal

import pytest

from dhan_cas_bot.dhan_feed import book_from_packet, decode_full_binary, packets
from dhan_cas_bot.domain import ContractError, Instrument, OptionType, Segment
from dhan_cas_bot.index_catalog import index_catalog


def instrument():
    return Instrument("100", "NIFTY", Segment.NSE_FNO, date(2026, 9, 29),
                      OptionType.CE, Decimal("23500"), 65, Decimal("0.05"), 1800)


def sdk_frame():
    # Independent full struct from Dhan's public SDK: 62-byte prefix, 100-byte
    # depth. In particular, there is no spare byte between OHLC and depth.
    depth = b"".join(struct.pack("<IIHHff", 65, 130, 1, 2, 9.95-i*.05, 10.05+i*.05) for i in range(5))
    return struct.pack("<BHBIfHIfIIIIIIffff100s", 8, 162, 2, 100,
                       10.05, 40000, 1700000000, 10.123, 3_000_000_000,
                       650, 1300, 195000, 260000, 130000,
                       9, 0, 12, 8, depth)


def test_sdk_wire_retains_observed_statistics_and_receipt_time():
    packet = decode_full_binary(sdk_frame(), instrument())
    book = book_from_packet(packet, instrument(), "epoch:1", 1700000001999999999)
    s = book.statistics
    assert s.last_price == Decimal("10.05")
    assert s.last_quantity == 40000 and s.volume == 3_000_000_000
    assert (s.total_buy_quantity, s.total_sell_quantity) == (1300, 650)
    assert (s.open_interest, s.oi_day_high, s.oi_day_low) == (195000, 260000, 130000)
    assert (s.day_open, s.day_high, s.day_low, s.day_close) == (9, 12, 8, None)
    assert Decimal("10.122") < s.average_price < Decimal("10.124")
    assert book.provider_ts_ms == 1700000000000
    assert book.received_ns == 1700000001999999999
    assert book.bids[0].price == Decimal("9.95") and book.asks[-1].quantity == 130
    assert len(list(packets(sdk_frame()+sdk_frame()))) == 2


def test_obsolete_padded_frame_is_rejected():
    raw = bytearray(sdk_frame()); raw.insert(62, 0)
    struct.pack_into("<H", raw, 1, 163)
    with pytest.raises(ContractError):
        decode_full_binary(bytes(raw), instrument())


@pytest.mark.parametrize("offset", [8, 18, 46, 50, 54, 58])
def test_nonfinite_statistics_do_not_enter_decisions(offset):
    raw = bytearray(sdk_frame()); struct.pack_into("<f", raw, offset, float("nan"))
    with pytest.raises(ContractError):
        decode_full_binary(bytes(raw), instrument())


def master(*overrides):
    base = dict(EXCH_ID="NSE", SEGMENT="D", SECURITY_ID="100", INSTRUMENT="OPTIDX",
                UNDERLYING_SYMBOL="NIFTY", UNDERLYING_SECURITY_ID="26000", SM_EXPIRY_DATE="2026-09-29",
                LOT_SIZE="65.0", OPTION_TYPE="CE", TICK_SIZE="5.0000", BUY_SELL_INDICATOR="A")
    stream = io.StringIO(); w = csv.DictWriter(stream, fieldnames=base); w.writeheader()
    for change in overrides: w.writerow(base | change)
    stream.seek(0)
    return stream


def test_catalog_uses_index_rows_not_derivative_underlying_ids():
    rows = index_catalog(master({}, {"INSTRUMENT":"INDEX", "SEGMENT":"I", "SECURITY_ID":"13"},
                                {"SECURITY_ID":"101", "UNDERLYING_SYMBOL":"NIFTYFPI", "LOT_SIZE":"1100"}),
                         as_of=date(2026, 9, 29))
    assert rows[0]["index_quote_security_id"] == "13"
    assert rows[0]["derivative_underlying_ids"] == ["26000"]
    assert rows[1]["symbol"] == "NIFTYFPI" and rows[1]["index_quote_security_id"] is None
    assert all(r["live_tradability"] == "UNVERIFIED" for r in rows)


def test_catalog_preserves_lot_changes_and_rejects_expired_contracts():
    rows = index_catalog(master({}, {"SECURITY_ID":"101", "SM_EXPIRY_DATE":"2026-10-06", "LOT_SIZE":"60"},
                                {"SECURITY_ID":"102", "SM_EXPIRY_DATE":"2026-09-22"}), as_of=date(2026, 9, 29))
    assert rows[0]["contracts"] == 2
    assert rows[0]["expiries"] == {"2026-09-29":[65], "2026-10-06":[60]}


@pytest.mark.parametrize("change", [{"LOT_SIZE":"1.5"}, {"TICK_SIZE":"NaN"}, {"OPTION_TYPE":"XX"}, {"SM_EXPIRY_DATE":"bad"}])
def test_catalog_rejects_malformed_specs(change):
    with pytest.raises(ContractError):
        index_catalog(master(change), as_of=date(2026, 9, 29))


def test_empty_or_duplicate_master_is_not_success():
    for stream in (io.StringIO(""), master({}, {})):
        with pytest.raises(ContractError):
            index_catalog(stream, as_of=date(2026, 9, 29))


def test_bse_alias_and_overlapping_security_ids_are_exchange_scoped():
    rows = index_catalog(master({}, {"EXCH_ID":"BSE", "UNDERLYING_SYMBOL":"SENSEX50", "LOT_SIZE":"75"},
                                {"EXCH_ID":"BSE", "SEGMENT":"I", "INSTRUMENT":"INDEX", "UNDERLYING_SYMBOL":"SNSX50", "SECURITY_ID":"83"}),
                         as_of=date(2026, 9, 29))
    assert rows[0]["symbol"] == "SENSEX50" and rows[0]["index_quote_security_id"] == "83"
    assert rows[0]["exchange_segment"] == "BSE_FNO"
