from __future__ import annotations

import asyncio
import base64
from decimal import Decimal
from datetime import datetime, time, timezone
import fcntl
import hashlib
from io import StringIO
import json
import os
from pathlib import Path
import shutil
import signal
import time as monotime
from urllib.parse import urlencode, urlparse
from zoneinfo import ZoneInfo

import httpx

from .auth import session_token
from .broker import DhanBroker
from .commissioning import normalize_whitelist
from .config import load_config, load_mandate
from .dhan_feed import packets, decode_full_binary, book_from_packet
from .domain import CasPhase, ContractError
from .egress import require_expected_egress
from .engine import SessionEngine, restore_instrument
from .feeds import DhanMarketClient, DhanOrderUpdateClient, UpstoxFeedClient
from .final_source import NseFinalSource
from .instruments import load_dhan_master
from .ledger import Ledger
from .release import current_verification
from .profile import require_derivatives_profile
from .route import RouteQualifier
from .rules import RuleSource, DHAN_MASTER_URL, NSE_FREEZE_URL
from .runtime import AutoLive
from .transport import WebSocketRunner
from .upstox_signal import decode_binary, extract_status, observation, NIFTY_KEY

IST = ZoneInfo("Asia/Kolkata")


def write_status(state_dir: Path, runtime, **extra):
    value = {**runtime.status.as_dict(), **extra, "observed_at": datetime.now(timezone.utc).isoformat(), "writes": runtime.broker.allow_writes}
    path = state_dir / "status.json.tmp"
    with path.open("w") as stream:
        json.dump(value, stream, sort_keys=True)
        stream.write("\n")
    path.chmod(0o600)
    path.replace(state_dir / "status.json")


def parse_clock_uncertainty(payload: str) -> int:
    fields = payload.strip().split(",")
    # Newer chrony CSV includes a source-address field after the reference ID.
    # The ten trailing tracking values retain the same relative positions.
    if len(fields) not in {13,14} or fields[-1].strip() != "Normal":
        return 100000
    try:
        offset, delay, dispersion = (Decimal(fields[index]) for index in (-10,-4,-3))
        if not all(x.is_finite() for x in (offset,delay,dispersion)) or min(delay,dispersion)<0:
            return 100000
        return int((abs(offset)+dispersion+delay/2)*1000)+1
    except (ValueError, ArithmeticError):
        return 100000


async def clock_uncertainty() -> int:
    try:
        process = await asyncio.create_subprocess_exec("chronyc", "-c", "tracking", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
        stdout, _ = await asyncio.wait_for(process.communicate(), 3)
        if process.returncode:
            return 100000
        return parse_clock_uncertainty(stdout.decode())
    except (OSError, ValueError, asyncio.TimeoutError):
        return 100000


async def serve_session(config: dict, ledger: Ledger, stop: asyncio.Event, *, now_fn=None):
    now = now_fn or (lambda: datetime.now(timezone.utc))
    today = now().astimezone(IST).date()
    started_before_session = now().astimezone(IST).time() < time(15,5)
    state_dir = Path(config["state_dir"])
    mandate = load_mandate(state_dir / "mandate.json")
    if mandate.account_id != config["account_id"]:
        raise ContractError("configured account and mandate account differ")
    token = await session_token(config, state_dir)
    broker = DhanBroker(config["account_id"], token, config["dhan_api_base"], allow_writes=config["live_order_authority"] and mandate.live_order_authority)
    runtime = AutoLive(ledger, broker, mandate, software_verified=current_verification(Path(__file__).resolve().parents[1], state_dir))
    runtime.status.auto_live_armed = broker.allow_writes and not ledger.metadata("disarmed", False)
    engine = SessionEngine(runtime, {}, now_fn=now)
    tasks = []
    runners = []
    wake = asyncio.Event()
    records = asyncio.Queue(maxsize=4096)
    recorder_failed = False
    recorder_task = None
    final_task = None
    final_error = ""
    try:
        # Broker recovery precedes calendar, Upstox, egress admission and metadata.
        await runtime.recover()
        await runtime.refresh_account()
        if broker.allow_writes:
            ledger.put_mandate(mandate)
        account_admitted = False
        instruments = []
        metadata_error = ""
        try:
            master, freeze = await asyncio.gather(RuleSource(timeout=15).fetch(config.get("dhan_master_url", DHAN_MASTER_URL)), RuleSource(timeout=15).fetch(config.get("nse_freeze_url", NSE_FREEZE_URL)))
            expiry = RuleSource.current_expiry(master.payload, today=today)
            instruments = load_dhan_master(StringIO(master.payload.decode("utf-8-sig")), expiry=expiry, freeze_by_security={"__NIFTY__": RuleSource.parse_freeze(freeze.payload)["NIFTY"]})
            ledger.observe("master:"+master.digest, "MASTER", {"source": master.url, "retrieved_at": master.retrieved_at.isoformat(), "sha256": master.digest})
            ledger.observe("freeze:"+freeze.digest, "FREEZE", {"source": freeze.url, "retrieved_at": freeze.retrieved_at.isoformat(), "sha256": freeze.digest})
            account_admitted = expiry == today
            if broker.allow_writes:
                require_derivatives_profile(await broker._request("GET","/profile"),broker.account_id)
                await require_expected_egress(config["expected_egress_ip"])
                ips = normalize_whitelist(await broker._request("GET", "/ip/getIP"))
                if config["expected_egress_ip"] not in {ips["primary_ip"], ips["secondary_ip"]}:
                    raise ContractError("Dhan whitelist does not contain this execution IP")
        except Exception as exc:
            metadata_error = type(exc).__name__
            account_admitted = False
        instrument_by_id = {inst.security_id: inst for inst in instruments}
        active = engine.active
        if active:
            inst = restore_instrument(json.loads(active["payload"])["instrument"])
            instrument_by_id.setdefault(inst.security_id, inst)
        # A missing reference/feed can only remove entry permission, never recovery.
        upstox_token = os.environ.get("UPSTOX_ANALYTICS_TOKEN", "")
        upstox = UpstoxFeedClient(upstox_token) if upstox_token else None
        market = DhanMarketClient(token)
        orders = DhanOrderUpdateClient(token)
        received_seq = 0
        echoed = {}
        uncertainty = await clock_uncertainty()

        def record_frame(kind, epoch, payload):
            nonlocal recorder_failed
            identity = f"{epoch}:{hashlib.sha256(payload).hexdigest()}"
            if kind != "ORDER_FRAME" and not (time(15,5) <= now().astimezone(IST).time() <= time(15,45)) and engine.active is None:
                return identity
            try:
                records.put_nowait((identity, kind, {"epoch": epoch, "received_ns": monotime.time_ns(), "monotonic_ns": monotime.monotonic_ns(), "data_b64": base64.b64encode(payload).decode()}))
            except asyncio.QueueFull:
                recorder_failed = True
            return identity

        async def record_worker():
            nonlocal recorder_failed
            while True:
                batch = [await records.get()]
                while len(batch) < 128 and not records.empty():
                    batch.append(records.get_nowait())
                try:
                    if shutil.disk_usage(state_dir).free < 512*1024*1024:
                        raise ContractError("raw recorder reserves remaining disk for orders and recovery")
                    await asyncio.to_thread(ledger.observe_batch,batch)
                except Exception:
                    recorder_failed = True
                finally:
                    for _ in batch:
                        records.task_done()
                await asyncio.sleep(0)
        recorder_task = asyncio.create_task(record_worker())

        async def final_worker():
            nonlocal final_error
            source = NseFinalSource()
            while not stop.is_set():
                current = now().astimezone(IST)
                held = engine.active
                expired_date = restore_instrument(json.loads(held["payload"])["instrument"]).expiry if held else None
                stopped = engine.status and engine.status.phase is CasPhase.CAS_STOP
                if stopped or (expired_date and current.date() > expired_date):
                    try:
                        final = await source.fetch(expired_date or today)
                        if final:
                            engine.on_final(final)
                            final_error = ""
                            wake.set()
                    except Exception as exc:
                        final_error = type(exc).__name__
                await asyncio.sleep(5 if time(15,28) <= current.time() < time(15,40) else 30)
        # A slow archive must never delay execution or recovery.
        final_task = asyncio.create_task(final_worker())

        async def upstox_endpoint():
            async with httpx.AsyncClient(timeout=5, follow_redirects=False) as client:
                response = await client.get(config.get("upstox_authorize_url", "https://api.upstox.com/v3/feed/market-data-feed/authorize"), headers={"Authorization": f"Bearer {upstox_token}"})
                response.raise_for_status()
                endpoint = response.json()["data"]["authorized_redirect_uri"]
            return endpoint

        async def record_upstox(payload):
            nonlocal received_seq
            received_ns = int(now().timestamp()*1_000_000_000)
            value = decode_binary(payload)
            epoch = upstox.protocol.epoch.id
            record_frame("UPSTOX_FRAME", epoch, payload)
            received_seq += 1
            status = extract_status(value, trading_date=today, epoch=epoch)
            if status:
                actual_date = datetime.fromtimestamp(status.updated_time_ms/1000, IST).date()
                if actual_date != today:
                    engine.signal_reconnect(None)
                    runtime.status.reason = "FOREIGN_CAS_DATE"
                    wake.set()
                    return
                try:
                    engine.on_status(status, clock_uncertainty_ms=uncertainty)
                except ContractError as exc:
                    runtime.status.reason = str(exc)
            # The initial snapshot and status-only messages cannot manufacture
            # pre-CAS observations. Only currentTs + actual NIFTY payload identity.
            if value.type != 1 or NIFTY_KEY not in value.feeds:
                wake.set()
                return
            raw = value.feeds[NIFTY_KEY].SerializeToString()
            identity = f"{epoch}:{value.currentTs}:{hashlib.sha256(raw).hexdigest()}"
            try:
                sample = observation(value, received_ns=received_ns, provider_ts_ms=int(value.currentTs), epoch=epoch, receiver_seq=received_seq, raw_identity=identity, ltp=engine.reference is None)
                if engine.reference is None:
                    if now().astimezone(IST).time() < time(15,15):
                        engine.on_ltp(sample)
                else:
                    await engine.on_iep(sample, dispatch=False)
            except ContractError:
                if engine.reference is not None and engine.status and engine.status.phase in {CasPhase.CAS_LM_START, CasPhase.CAS_M_STOP}:
                    engine.streaks.clear()
                    runtime.status.reason = "OFFICIAL_INDEX_IEP_UNAVAILABLE"
            wake.set()

        last_packets = {}
        async def record_dhan(payload):
            received_ns = int(now().timestamp()*1_000_000_000)
            epoch = market.protocol.epoch.id
            record_frame("DHAN_FRAME", epoch, payload)
            for packet in packets(payload):
                inst = instrument_by_id.get(str(int.from_bytes(packet[4:8], "little")))
                if packet[0] != 8 or inst is None:
                    continue
                identity = hashlib.sha256(packet).digest()
                if last_packets.get(inst.security_id) == (epoch,identity):
                    continue
                last_packets[inst.security_id] = (epoch,identity)
                decoded = decode_full_binary(packet, inst)
                engine.on_book(book_from_packet(decoded, inst, epoch, received_ns))
            wake.set()

        async def record_order(payload):
            epoch = orders.protocol.epoch.id
            record_frame("ORDER_FRAME", epoch, payload)
            try:
                event = json.loads(payload)
                data = event.get("Data", event)
                if not isinstance(data, dict):
                    return
                account = str(data.get("ClientId") or data.get("clientId") or event.get("dhanClientId") or "")
                if account != broker.account_id:
                    return
                identity = str(data.get("OrderNo") or data.get("orderNo") or data.get("orderId") or "")
                correlation = str(data.get("CorrelationId") or data.get("correlationId") or "")
                state = str(data.get("Status") or data.get("OrderStatus") or data.get("orderStatus") or "").upper()
                if identity:
                    echoed[identity] = (epoch, state)
                if correlation:
                    echoed[correlation] = (epoch, state)
            except (ValueError, TypeError):
                runtime.status.reason = "INVALID_ORDER_EVENT"
            wake.set()

        def signal_connect():
            upstox.protocol.on_connect()
            engine.signal_reconnect(upstox.protocol.epoch.id)
        def signal_disconnect():
            upstox.protocol.on_disconnect()
            engine.signal_reconnect(None)
            wake.set()
        def market_connect():
            market.protocol.on_connect()
            engine.market_reconnect(market.protocol.epoch.id)
        def market_disconnect():
            market.protocol.on_disconnect()
            engine.market_reconnect(None)
            wake.set()
        def order_disconnect():
            orders.protocol.on_disconnect()
            runtime.status.broker_route_verified = False
            echoed.clear()
            wake.set()
        if upstox:
            runners.append(WebSocketRunner(upstox_endpoint, {}, record_upstox, subscribe=upstox.subscription_messages([NIFTY_KEY]), binary=True, on_connect=signal_connect, on_disconnect=signal_disconnect))
        else:
            engine.signal_reconnect(None)
        if instrument_by_id:
            market_url = config.get("dhan_market_ws_url") or "wss://api-feed.dhan.co?" + urlencode({"version": "2", "token": token, "clientId": broker.account_id, "authType": "2"})
            runners.append(WebSocketRunner(market_url, {}, record_dhan, subscribe=market.subscription_messages(instrument_by_id), on_connect=market_connect, on_disconnect=market_disconnect))
        else:
            engine.market_reconnect(None)
        runners.append(WebSocketRunner(config.get("dhan_order_ws_url") or "wss://api-order-update.dhan.co", {}, record_order, connect_messages=[{"LoginReq":{"MsgCode":42,"ClientId":broker.account_id,"Token":token},"UserType":"SELF"}], on_connect=orders.protocol.on_connect, on_disconnect=order_disconnect))
        tasks = [asyncio.create_task(runner.run()) for runner in runners]
        last_reconcile = last_status = last_clock = 0.0
        metadata_retry_at = monotime.monotonic()+30
        route_failed_epochs = set()
        while not stop.is_set():
            current = now().astimezone(IST)
            for task in tasks:
                if task.done():
                    task.result()
                    raise ContractError("a required transport stopped")
            monotonic = monotime.monotonic()
            if monotonic - last_clock > 60:
                uncertainty = await clock_uncertainty()
                last_clock = monotonic
            runtime.status.auto_live_armed = broker.allow_writes and not ledger.metadata("disarmed", False)
            try:
                busy = bool(engine.active or ledger.pending_intents())
                interval = .4 if busy else 5.0
                if ledger.metadata("reconcile_requested", False):
                    last_reconcile = 0
                    ledger.put_metadata("reconcile_requested", False)
                if monotonic - last_reconcile >= interval:
                    runtime.reconciled = await runtime.orders.reconcile()
                    last_reconcile = monotime.monotonic()
                    await runtime.refresh_account()
                    if not runtime.reconciled["unresolved"] and engine.active is None:
                        runtime.status.state = "ARMED_WAITING_SIGNAL"
                probe = ledger.metadata("route_probe", {})
                probe_totals = ledger.lifecycle_totals("route-probe")
                if probe_totals["quantity"] and not probe_totals["unresolved"]:
                    row = ledger.db.execute("SELECT payload FROM intents WHERE lifecycle_id='route-probe' AND side='BUY' ORDER BY created_at DESC LIMIT 1").fetchone()
                    inst = restore_instrument(json.loads(row[0])["instrument"])
                    from .domain import OptionBook
                    book = engine.books.get(inst.security_id) or OptionBook(inst, (), (), "probe-recovery", monotime.time_ns())
                    await engine.exit_manager.reduce(inst, probe_totals["quantity"], book, "route-probe", emergency=True)
                if probe.get("epoch") == orders.protocol.epoch.id and orders.protocol.epoch.connected:
                    saved = ledger.db.execute("SELECT * FROM orders WHERE intent_id=?", (probe.get("intent_id", ""),)).fetchone()
                    if saved:
                        evidence = echoed.get(saved["order_id"]) or echoed.get(probe.get("correlation_id"))
                        totals = ledger.lifecycle_totals("route-probe")
                        if evidence and evidence[0] == orders.protocol.epoch.id and evidence[1] not in {"REJECTED", ""} and saved["state"] != "REJECTED" and not totals["unresolved"]:
                            if totals["quantity"] == 0:
                                runtime.status.broker_route_verified = True
                may_probe = (account_admitted and broker.allow_writes and runtime.status.auto_live_armed and runtime.status.software_verified and uncertainty <= 100 and not runtime.status.broker_route_verified and engine.active is None and not ledger.pending_intents() and orders.protocol.epoch.connected and orders.protocol.epoch.id not in route_failed_epochs and time(15,5) <= current.time() < time(15,19,30))
                if may_probe:
                    choices = [book for book in engine.books.values() if book.instrument.expiry == today and book.top_bid and book.top_bid.quantity >= book.instrument.lot_size and book.top_bid.price > max(book.instrument.tick_size, book.instrument.lower_limit or 0)]
                    choices.sort(key=lambda book: (book.instrument.lot_size*max(book.instrument.tick_size,book.instrument.lower_limit or 0), int(book.instrument.security_id)))
                    if choices:
                        qualifier = RouteQualifier(ledger, broker, session_id=today.isoformat(), max_attempts=mandate.probe_max_attempts_per_session, debit_cap=mandate.probe_entry_debit_cap_per_session, mandate_spend_cap=mandate.probe_spending_cap_per_mandate)
                        try:
                            await qualifier.qualify(choices[0], epoch=orders.protocol.epoch.id)
                        except Exception as exc:
                            route_failed_epochs.add(orders.protocol.epoch.id)
                            runtime.status.reason = f"ROUTE_PROBE:{type(exc).__name__}"
                # No admission on unknown day/rules/clock/disk, but management
                # runs regardless of these entry prerequisites.
                admitted = account_admitted and uncertainty <= 100 and not recorder_failed and shutil.disk_usage(state_dir).free > 256*1024*1024
                armed = runtime.status.auto_live_armed
                if not admitted:
                    runtime.status.auto_live_armed = False
                if broker.allow_writes:
                    await engine.cycle(reconcile=False)
                runtime.status.auto_live_armed = armed
                # Rotation always starts with broker-first recovery, including
                # overnight settlement and ambiguous orders. Pending positions
                # must not prevent renewal before the authentication expires.
                if not ledger.order_lock.locked():
                    if metadata_error and engine.active is None and monotonic >= metadata_retry_at:
                        return
                    if current.date() != today or (started_before_session and current.time() >= time(15,5)):
                        return
                    cached = state_dir / "dhan_token.json"
                    if cached.exists() and not os.environ.get("DHAN_ACCESS_TOKEN"):
                        if monotime.time() - json.loads(cached.read_text()).get("issued",0) >= 20*3600:
                            return
                if not account_admitted and engine.active is None:
                    runtime.status.state = "NO_TRADE_DAY" if not metadata_error else "ENTRY_HALTED"
            except Exception as exc:
                runtime.status.reason = f"RECOVERY_REQUIRED:{type(exc).__name__}"
                runtime.status.state = "RECOVERING"
                last_reconcile = 0
            if monotonic - last_status >= 1:
                write_status(state_dir, runtime, session=today.isoformat(), contract_count=len(instruments), books_observed=len(engine.books), clock_uncertainty_ms=uncertainty, metadata_error=metadata_error, recorder_failed=recorder_failed, final_input="VERIFIED" if engine.final_value else "UNQUALIFIED", final_source_error=final_error)
                last_status = monotonic
            wake.clear()
            try:
                await asyncio.wait_for(wake.wait(), .25)
            except asyncio.TimeoutError:
                pass
    finally:
        if final_task:
            final_task.cancel()
            await asyncio.gather(final_task, return_exceptions=True)
        for runner in runners:
            runner.close()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        if recorder_task:
            try:
                await asyncio.wait_for(records.join(),3)
            except asyncio.TimeoutError:
                pass
            recorder_task.cancel()
            await asyncio.gather(recorder_task,return_exceptions=True)
        await broker.close()


async def run_service(config_path: str) -> None:
    config = load_config(config_path)
    state_dir = Path(config["state_dir"])
    state_dir.mkdir(parents=True, exist_ok=True)
    lock = os.open(state_dir / "writer.lock", os.O_CREAT | os.O_RDWR, 0o600)
    try:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ContractError("another account writer is already running") from exc
        ledger = Ledger(state_dir / "ledger.sqlite3")
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, stop.set)
        try:
            while not stop.is_set():
                config = load_config(config_path)
                await serve_session(config, ledger, stop)
        finally:
            ledger.close()
    finally:
        os.close(lock)
