"""Minimal generated-equivalent Upstox V3 protobuf binding.

The descriptor is built from the official V3 field numbers used by the
service. Keeping the binding in source makes the clean Dhan bot installable
without requiring protoc on the host; unknown provider fields are ignored by
protobuf as required by the contract.
"""
from __future__ import annotations

from google.protobuf import descriptor_pb2, descriptor_pool, message_factory, wrappers_pb2


def _field(message, name, number, kind, *, type_name=None, label=1, oneof=None):
    field = message.field.add(name=name, number=number, type=kind, label=label)
    if type_name:
        field.type_name = type_name
    if oneof is not None:
        field.oneof_index = oneof


def _build():
    fd = descriptor_pb2.FileDescriptorProto(name="MarketDataFeed.proto", package="com.upstox.marketdatafeederv3udapi.rpc.proto", syntax="proto3", dependency=["google/protobuf/wrappers.proto"])
    ltpc = fd.message_type.add(name="LTPC")
    _field(ltpc, "ltp", 1, 1); _field(ltpc, "ltt", 2, 3); _field(ltpc, "ltq", 3, 3); _field(ltpc, "cp", 4, 1); _field(ltpc, "iep", 5, 11, type_name=".google.protobuf.DoubleValue")
    index = fd.message_type.add(name="IndexFullFeed")
    _field(index, "ltpc", 1, 11, type_name=".com.upstox.marketdatafeederv3udapi.rpc.proto.LTPC")
    full = fd.message_type.add(name="FullFeed")
    full.oneof_decl.add(name="FullFeedUnion")
    _field(full, "indexFF", 2, 11, type_name=".com.upstox.marketdatafeederv3udapi.rpc.proto.IndexFullFeed", oneof=0)
    feed = fd.message_type.add(name="Feed")
    feed.oneof_decl.add(name="FeedUnion")
    _field(feed, "fullFeed", 2, 11, type_name=".com.upstox.marketdatafeederv3udapi.rpc.proto.FullFeed", oneof=0)
    status = fd.message_type.add(name="StatusInfo")
    _field(status, "status", 1, 9); _field(status, "updatedTime", 2, 3)
    info = fd.message_type.add(name="MarketInfo")
    entry = info.nested_type.add(name="CasMarketStatusEntry", options=descriptor_pb2.MessageOptions(map_entry=True))
    _field(entry, "key", 1, 9); _field(entry, "value", 2, 11, type_name=".com.upstox.marketdatafeederv3udapi.rpc.proto.StatusInfo")
    _field(info, "casMarketStatus", 2, 11, type_name=".com.upstox.marketdatafeederv3udapi.rpc.proto.MarketInfo.CasMarketStatusEntry", label=3)
    response = fd.message_type.add(name="FeedResponse")
    feed_entry = response.nested_type.add(name="FeedsEntry", options=descriptor_pb2.MessageOptions(map_entry=True))
    _field(feed_entry, "key", 1, 9); _field(feed_entry, "value", 2, 11, type_name=".com.upstox.marketdatafeederv3udapi.rpc.proto.Feed")
    _field(response, "feeds", 2, 11, type_name=".com.upstox.marketdatafeederv3udapi.rpc.proto.FeedResponse.FeedsEntry", label=3)
    _field(response, "currentTs", 3, 3); _field(response, "marketInfo", 4, 11, type_name=".com.upstox.marketdatafeederv3udapi.rpc.proto.MarketInfo")
    pool = descriptor_pool.Default()
    try:
        pool.Add(fd)
    except Exception:
        pass
    return message_factory.GetMessageClass(pool.FindMessageTypeByName("com.upstox.marketdatafeederv3udapi.rpc.proto.FeedResponse"))


FeedResponse = _build()
