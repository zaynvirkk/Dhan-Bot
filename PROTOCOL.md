# Protocol binding

The Dhan market adapter implements the documented v2 `FULL` packet directly:

- little-endian eight-byte header;
- response code `8`;
- NSE F&O segment code `2`;
- security ID;
- full trade/OI body;
- five 20-byte bid/ask depth levels.

Packets with an unexpected length, response code, segment, security ID, or
empty depth are rejected. Dhan sends requests as JSON and responses as binary;
the service never treats a JSON-looking market response as a valid book.

The official NIFTY signal adapter accepts only the Upstox V3 protobuf path:
`FeedResponse.feeds["NSE_INDEX|Nifty 50"].fullFeed.indexFF.ltpc.iep.value`, with
protobuf wrapper presence required. The future is not read by the strategy
admission path.

The runtime protobuf descriptor in `dhan_cas_bot/proto.py` contains the
field numbers needed by this service and ignores additive provider fields.
Unknown critical structure remains an entry-blocking protocol incident.
