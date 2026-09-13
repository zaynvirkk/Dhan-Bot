from __future__ import annotations

import asyncio
import os
from pathlib import Path
from datetime import date, datetime, timezone
import json
from io import StringIO
from urllib.parse import urlencode

from .broker import DhanBroker
from .config import load_config, load_mandate
from .domain import ContractError
from .ledger import Ledger
from .feeds import DhanMarketClient, DhanOrderUpdateClient, UpstoxFeedClient
from .runtime import AutoLive
from .transport import WebSocketRunner
from .egress import require_expected_egress
from .release import current_verification
from .rules import RuleSource, DHAN_MASTER_URL, NSE_FREEZE_URL
from .instruments import load_dhan_master
from .dhan_feed import decode_full_binary, book_from_packet
from .upstox_signal import extract_status, observation, NIFTY_KEY
from .engine import SessionEngine
from .route import RouteQualifier
from .auth import resolve_dhan_access_token


async def run_service(config_path: str) -> None:
    config = load_config(config_path)
    state_dir = Path(config["state_dir"])
    mandate_path = state_dir / "mandate.json"
    if not mandate_path.exists():
        raise ContractError("service is not configured: mandate.json is missing")
    mandate = load_mandate(mandate_path)
    if mandate.account_id != config["account_id"]:
        raise ContractError("configured account and mandate account differ")
    dhan_token = await resolve_dhan_access_token(
        config["account_id"],
        access_token=os.environ.get("DHAN_ACCESS_TOKEN", ""),
        pin=os.environ.get("DHAN_PIN", ""),
        totp_secret=os.environ.get("DHAN_TOTP_SECRET", ""),
        auth_url=config.get("dhan_auth_url", "https://auth.dhan.co/app/generateAccessToken"),
    )
    upstox_token = os.environ.get("UPSTOX_ANALYTICS_TOKEN", "")
    if not dhan_token or not upstox_token:
        raise ContractError("DHAN_ACCESS_TOKEN and UPSTOX_ANALYTICS_TOKEN are required")
    if config["live_order_authority"] and mandate.live_order_authority:
        await require_expected_egress(config["expected_egress_ip"])
    broker = DhanBroker(config["account_id"], dhan_token, config["dhan_api_base"], allow_writes=bool(config["live_order_authority"] and mandate.live_order_authority))
    ledger = Ledger(state_dir / "ledger.sqlite3")
    runtime = AutoLive(ledger, broker, mandate, software_verified=current_verification(Path(__file__).resolve().parents[1], state_dir))
    if not config["live_order_authority"]:
        runtime.status.auto_live_armed = False
        runtime.status.state = "ARMED_WAITING_SESSION"
    # Recovery is deliberately before calendar, signal or transport startup.
    await runtime.recover()
    await runtime.refresh_account()
    (state_dir / "status.json").write_text(__import__("json").dumps(runtime.status.as_dict(), sort_keys=True) + "\n", encoding="utf-8")
    upstox = UpstoxFeedClient(upstox_token)
    dhan_market = DhanMarketClient(dhan_token)
    dhan_orders = DhanOrderUpdateClient(dhan_token)
    master_record = await RuleSource().fetch(config.get("dhan_master_url", DHAN_MASTER_URL))
    freeze_record = await RuleSource().fetch(config.get("nse_freeze_url", NSE_FREEZE_URL))
    freeze_by_symbol = {"__NIFTY__": RuleSource.parse_freeze(freeze_record.payload).get("NIFTY", 0)}
    expiry = RuleSource.current_expiry(master_record.payload, today=datetime.now(timezone.utc).date())
    instruments = load_dhan_master(StringIO(master_record.payload.decode("utf-8-sig")), expiry=expiry, freeze_by_security=freeze_by_symbol)
    instrument_by_id = {x.security_id: x for x in instruments}
    engine = SessionEngine(runtime, {})
    receiver_seq = {"upstox": 0}
    route_probe_order: dict[str, str] = {}
    route_probe_task: asyncio.Task | None = None

    async def upstox_endpoint() -> str:
        # Upstox authorisation returns a one-use URL. Re-authorise on every
        # reconnect instead of reusing an expired redirect code.
        import httpx
        authorize_url = config.get("upstox_authorize_url", "https://api.upstox.com/v3/feed/market-data-feed/authorize")
        async with httpx.AsyncClient(timeout=5.0, follow_redirects=False) as client:
            response = await client.get(authorize_url, headers={"Authorization": f"Bearer {upstox_token}", "Accept": "application/json"})
            response.raise_for_status()
            value = response.json()
        try:
            endpoint = value["data"]["authorized_redirect_uri"]
        except (KeyError, TypeError) as exc:
            raise ContractError("Upstox authorize response has no authorized_redirect_uri") from exc
        return str(endpoint)

    market_url = config.get("dhan_market_ws_url") or "wss://api-feed.dhan.co?" + urlencode({"version": "2", "token": dhan_token, "clientId": config["account_id"], "authType": "2"})
    order_url = config.get("dhan_order_ws_url") or "wss://api-order-update.dhan.co"

    async def record_upstox(payload: bytes) -> None:
        # Decode now even before the session has a selected chain. Invalid
        # protobuf is a transport incident and never a trading signal.
        from .upstox_signal import decode_binary
        response = decode_binary(payload)
        receiver_seq["upstox"] += 1
        status = extract_status(response, trading_date=datetime.now(timezone.utc).date(), epoch=upstox.protocol.epoch.id)
        if status is not None:
            if status.phase.value == "CTS_CLOSE":
                try:
                    engine.on_status(status)
                except ContractError as exc:
                    runtime.status.reason = str(exc)
            else:
                engine.status = status
        if engine.reference is None:
            try:
                engine.on_ltp(observation(response, received_ns=time_ns(), provider_ts_ms=int(response.currentTs), epoch=upstox.protocol.epoch.id, receiver_seq=receiver_seq["upstox"], raw_identity=f"u:{receiver_seq['upstox']}", ltp=True))
            except ContractError:
                return
        elif engine.status and engine.status.phase.value in {"CAS_LM_START", "CAS_M_STOP"}:
            try:
                await engine.on_iep(observation(response, received_ns=time_ns(), provider_ts_ms=int(response.currentTs), epoch=upstox.protocol.epoch.id, receiver_seq=receiver_seq["upstox"], raw_identity=f"u:{receiver_seq['upstox']}"))
            except ContractError as exc:
                runtime.status.reason = str(exc)

    async def record_dhan(payload: bytes) -> None:
        if not payload:
            raise ContractError("empty Dhan market frame")
        packet_id = int.from_bytes(payload[4:8], "little") if len(payload) >= 8 else -1
        inst = instrument_by_id.get(str(packet_id))
        if inst is None:
            return
        packet = decode_full_binary(payload, inst)
        book = book_from_packet(packet, inst, dhan_market.protocol.epoch.id, time_ns())
        engine.on_book(book)
        # A route probe is a deliberately non-marketable one-lot IOC. It is
        # allowed only after the operator has enabled live writes and the
        # order-update socket is in this same connection epoch.
        nonlocal route_probe_task
        if (config["live_order_authority"] and mandate.live_order_authority
                and not runtime.status.broker_route_verified
                and not route_probe_order and route_probe_task is None
                and dhan_orders.protocol.epoch.connected and book.top_bid is not None):
            qualifier = RouteQualifier(
                ledger, broker, session_id=datetime.now(timezone.utc).date().isoformat(),
                max_attempts=mandate.probe_max_attempts_per_session,
                debit_cap=mandate.probe_entry_debit_cap_per_session,
                mandate_spend_cap=mandate.probe_spending_cap_per_mandate,
            )
            async def qualify_route() -> None:
                try:
                    proof = await qualifier.qualify(book, epoch=dhan_orders.protocol.epoch.id)
                    route_probe_order["order_id"] = proof.order_id
                    route_probe_order["epoch"] = proof.epoch
                except (ContractError, OSError) as exc:
                    runtime.status.reason = f"route_probe_failed:{exc}"
            route_probe_task = asyncio.create_task(qualify_route())

    async def record_order(payload: bytes) -> None:
        if not payload:
            raise ContractError("empty Dhan order update frame")
        try:
            event = json.loads(payload.decode())
            data = event.get("Data") if isinstance(event.get("Data"), dict) else event
            identity = str(data.get("OrderNo") or data.get("orderNo") or data.get("orderId") or data.get("CorrelationId") or data.get("correlationId") or "")
            account = str(data.get("ClientId") or data.get("clientId") or event.get("dhanClientId") or broker.account_id)
            if identity and dhan_orders.accept_order_event(account, broker.account_id, identity):
                if (route_probe_order.get("epoch") == dhan_orders.protocol.epoch.id
                        and identity in {route_probe_order.get("order_id"), str(data.get("CorrelationId", ""))}):
                    runtime.status.broker_route_verified = True
                await runtime.orders.reconcile()
        except (UnicodeDecodeError, json.JSONDecodeError, ContractError):
            runtime.status.reason = "invalid_or_foreign_order_update"

    def order_connected() -> None:
        dhan_orders.protocol.on_connect()

    def order_disconnected() -> None:
        dhan_orders.protocol.on_disconnect()
        runtime.status.broker_route_verified = False

    runners = [
        WebSocketRunner(upstox_endpoint, {"Accept": "*/*"}, record_upstox, subscribe=upstox.subscription_messages([NIFTY_KEY]), binary=True, on_connect=upstox.protocol.on_connect, on_disconnect=upstox.protocol.on_disconnect),
        WebSocketRunner(market_url, {}, record_dhan, subscribe=dhan_market.subscription_messages(instrument_by_id), on_connect=dhan_market.protocol.on_connect, on_disconnect=dhan_market.protocol.on_disconnect),
        WebSocketRunner(order_url, {}, record_order, connect_messages=[{"LoginReq": {"MsgCode": 42, "ClientId": config["account_id"], "Token": dhan_token}, "UserType": "SELF"}], on_connect=order_connected, on_disconnect=order_disconnected),
    ]
    try:
        await asyncio.gather(*(runner.run() for runner in runners))
    finally:
        for runner in runners:
            runner.close()
        ledger.close()


def time_ns() -> int:
    import time
    return time.time_ns()
