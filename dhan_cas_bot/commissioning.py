"""Bounded connection checks. This module never constructs an order request."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from io import StringIO
import json
import os
from pathlib import Path
from urllib.parse import urlencode, urlparse
from zoneinfo import ZoneInfo

import httpx
from websockets.asyncio.client import connect

from .auth import resolve_dhan_access_token
from .broker import DhanBroker
from .domain import ContractError
from .egress import public_egress_ip
from .feeds import dhan_subscription, upstox_subscription
from .instruments import load_dhan_master
from .rules import RuleSource, DHAN_MASTER_URL, NSE_FREEZE_URL
from .upstox_signal import decode_binary, NIFTY_KEY
from .dhan_feed import decode_full_binary


def normalize_whitelist(value):
    if isinstance(value, list) and len(value) == 1:
        value = value[0]
    if not isinstance(value, dict):
        raise ContractError("unrecognized Dhan whitelist response")
    keys = {"primaryIP", "secondaryIP"}
    return {"primary_ip": value.get("primaryIP"), "secondary_ip": value.get("secondaryIP"), "whitelist_resolved": bool(keys & value.keys())}


async def check_connections(config: dict) -> dict:
    report = {"observed_at": datetime.now(timezone.utc).isoformat(), "writes": False, "connected": False, "checks": {}}
    checks = report["checks"]
    timeout = httpx.Timeout(20, connect=10)
    token = None
    instruments = []
    index_ltp = None

    async def attempt(name, operation):
        try:
            result = await asyncio.wait_for(operation(), timeout=55)
            checks[name] = {"status": "PASS", **result}
        except Exception as exc:
            # URLs and provider bodies can contain credentials. Only types
            # and HTTP status codes enter operator logs.
            checks[name] = {"status": "FAIL", "error_type": type(exc).__name__}
            if isinstance(exc, httpx.HTTPStatusError):
                checks[name]["http_status"] = exc.response.status_code

    async def egress():
        value = await public_egress_ip()
        return {"ip": value, "matches_expected": value == config.get("expected_egress_ip")}

    async def authenticate():
        nonlocal token
        token = await resolve_dhan_access_token(config["account_id"], access_token=os.environ.get("DHAN_ACCESS_TOKEN", ""), pin=os.environ.get("DHAN_PIN", ""), totp_secret=os.environ.get("DHAN_TOTP_SECRET", ""))
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get("https://api.dhan.co/v2/profile", headers={"access-token": token})
            response.raise_for_status()
            value = response.json()
        if str(value.get("dhanClientId")) != config["account_id"]:
            raise ContractError("Dhan profile account mismatch")
        return {"account_matches": True, "data_plan": str(value.get("dataPlan", "UNKNOWN")), "data_validity": str(value.get("dataValidity", "UNKNOWN")), "token_validity": str(value.get("tokenValidity", "UNKNOWN"))}

    async def metadata():
        nonlocal instruments
        master, freeze = await asyncio.gather(RuleSource(timeout=20).fetch(DHAN_MASTER_URL), RuleSource(timeout=20).fetch(NSE_FREEZE_URL))
        today = datetime.now(ZoneInfo("Asia/Kolkata")).date()
        expiry = RuleSource.current_expiry(master.payload, today=today)
        quantity = RuleSource.parse_freeze(freeze.payload)["NIFTY"]
        instruments = load_dhan_master(StringIO(master.payload.decode("utf-8-sig")), expiry=expiry, freeze_by_security={"__NIFTY__": quantity})
        return {"expiry": expiry.isoformat(), "is_expiry_today": expiry == today, "instruments": len(instruments), "lot_sizes": sorted({i.lot_size for i in instruments}), "tick_sizes": sorted({str(i.tick_size) for i in instruments}), "freeze_quantity": quantity, "master_digest": master.digest, "freeze_digest": freeze.digest}

    async def upstox():
        nonlocal index_ltp
        upstox_token = os.environ.get("UPSTOX_ANALYTICS_TOKEN", "")
        if not upstox_token:
            raise ContractError("Upstox token is missing")
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get("https://api.upstox.com/v3/feed/market-data-feed/authorize", headers={"Authorization": f"Bearer {upstox_token}", "Accept": "application/json"})
            response.raise_for_status()
            endpoint = response.json()["data"]["authorized_redirect_uri"]
        parsed = urlparse(endpoint)
        if parsed.scheme != "wss" or not (parsed.hostname or "").endswith(".upstox.com"):
            raise ContractError("invalid authorized Upstox endpoint")
        async with connect(endpoint, open_timeout=15) as socket:
            for msg in upstox_subscription([NIFTY_KEY]):
                await socket.send(json.dumps(msg).encode())
            frames, index_seen, iep_seen, cas_seen = 0, False, False, False
            deadline = asyncio.get_running_loop().time() + 12
            while asyncio.get_running_loop().time() < deadline:
                try:
                    frame = await asyncio.wait_for(socket.recv(), deadline - asyncio.get_running_loop().time())
                except asyncio.TimeoutError:
                    break
                if not isinstance(frame, bytes):
                    raise ContractError("Upstox did not send binary protobuf")
                value = decode_binary(frame)
                frames += 1
                if NIFTY_KEY in value.feeds:
                    index_seen = True
                    price = value.feeds[NIFTY_KEY].fullFeed.indexFF.ltpc.ltp
                    if price > 0:
                        index_ltp = Decimal(str(price))
                    iep_seen |= value.feeds[NIFTY_KEY].fullFeed.indexFF.ltpc.HasField("iep")
                cas_seen |= bool(value.marketInfo.casMarketStatus)
            if frames == 0:
                raise ContractError("Upstox socket opened without a feed frame")
            return {"websocket_connected": True, "protobuf_frames": frames, "index_seen": index_seen, "cas_status_seen": cas_seen, "index_iep_seen": iep_seen}

    await asyncio.gather(attempt("egress", egress), attempt("dhan_auth", authenticate), attempt("contract_metadata", metadata), attempt("upstox_feed", upstox))

    async def account():
        broker = DhanBroker(config["account_id"], token, allow_writes=False)
        orders, trades, positions, funds = await asyncio.gather(broker.orders(), broker.trades(), broker.positions(), broker.funds())
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get("https://api.dhan.co/v2/ip/getIP", headers={"access-token": token})
            response.raise_for_status()
            ips = response.json()
        return {"orders": len(orders), "trades": len(trades), "positions": len(positions), "spendable_cash": str(funds.spendable_cash), **normalize_whitelist(ips)}

    async def order_socket():
        async with connect("wss://api-order-update.dhan.co", open_timeout=15) as socket:
            await socket.send(json.dumps({"LoginReq": {"MsgCode": 42, "ClientId": config["account_id"], "Token": token}, "UserType": "SELF"}))
            try:
                await asyncio.wait_for(socket.recv(), timeout=4)
                received = True
            except asyncio.TimeoutError:
                received = False
            pong = await socket.ping()
            await asyncio.wait_for(pong, 5)
            return {"websocket_connected": True, "login_sent": True, "frame_received": received, "route_verified": False}

    async def market_socket():
        if not instruments:
            raise ContractError("current instrument metadata unavailable")
        # Read-only subscription only; no signal ranking or execution object.
        selected = sorted(instruments, key=lambda i: abs(i.strike - index_ltp))[:50] if index_ltp is not None else instruments[:50]
        by_id = {int(i.security_id): i for i in selected}
        endpoint = "wss://api-feed.dhan.co?" + urlencode({"version": "2", "token": token, "clientId": config["account_id"], "authType": "2"})
        async with connect(endpoint, open_timeout=15) as socket:
            for msg in dhan_subscription(str(i) for i in by_id):
                await socket.send(json.dumps(msg))
            count = 0
            deadline = asyncio.get_running_loop().time() + 12
            while asyncio.get_running_loop().time() < deadline:
                try:
                    frame = await asyncio.wait_for(socket.recv(), deadline - asyncio.get_running_loop().time())
                except asyncio.TimeoutError:
                    break
                if not isinstance(frame, bytes):
                    raise ContractError("Dhan market response is not binary")
                offset = 0
                while offset < len(frame):
                    size = int.from_bytes(frame[offset + 1:offset + 3], "little")
                    if size < 8 or offset + size > len(frame):
                        raise ContractError("invalid Dhan packet size")
                    packet = frame[offset:offset + size]
                    if packet[0] == 50:
                        raise ContractError("Dhan disconnected market feed")
                    inst = by_id.get(int.from_bytes(packet[4:8], "little"))
                    if packet[0] == 8 and inst:
                        decode_full_binary(packet, inst)
                        count += 1
                    offset += size
            return {"websocket_connected": True, "full_packets": count, "book_verified": count > 0}

    if token:
        await asyncio.gather(attempt("dhan_account", account), attempt("dhan_order_socket", order_socket), attempt("dhan_market_feed", market_socket))
    else:
        for name in ("dhan_account", "dhan_order_socket", "dhan_market_feed"):
            checks[name] = {"status": "SKIP", "reason": "authentication_unavailable"}
    report["connected"] = all(c["status"] == "PASS" for c in checks.values())
    report["trading_ready"] = False
    path = Path(config["state_dir"])
    path.mkdir(parents=True, exist_ok=True)
    temporary = path / "connections.json.tmp"
    temporary.write_text(json.dumps(report, sort_keys=True) + "\n")
    temporary.chmod(0o600)
    temporary.replace(path / "connections.json")
    return report
