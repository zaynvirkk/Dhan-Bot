from __future__ import annotations

import base64
import hashlib
import hmac
import struct
import time
from typing import Any

from .domain import ContractError


def totp_code(secret: str, *, timestamp: int | None = None) -> str:
    """Return the RFC 6238 SHA-1 six-digit code for a base32 secret."""
    if not secret:
        raise ContractError("TOTP secret is required")
    normalized = "".join(secret.split()).upper()
    try:
        key = base64.b32decode(normalized + "=" * ((8 - len(normalized) % 8) % 8), casefold=True)
    except Exception as exc:
        raise ContractError("TOTP secret is not valid base32") from exc
    counter = int((time.time() if timestamp is None else timestamp) // 30)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = (struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF) % 1_000_000
    return f"{value:06d}"


async def resolve_dhan_access_token(account_id: str, *, access_token: str = "", pin: str = "", totp_secret: str = "", auth_url: str = "https://auth.dhan.co/app/generateAccessToken") -> str:
    """Use a supplied token, or mint a fresh 24-hour token with PIN/TOTP."""
    if access_token:
        return access_token
    if not pin or not totp_secret:
        raise ContractError("provide DHAN_ACCESS_TOKEN or both DHAN_PIN and DHAN_TOTP_SECRET")
    import httpx
    params = {"dhanClientId": account_id, "pin": pin, "totp": totp_code(totp_secret)}
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(20, connect=10), follow_redirects=False) as client:
            response = await client.post(auth_url, params=params)
            response.raise_for_status()
            value: Any = response.json()
    except httpx.HTTPError as exc:
        raise ContractError("Dhan access-token request failed; verify network, PIN/TOTP setup and auth endpoint") from exc
    if not isinstance(value, dict) or str(value.get("dhanClientId")) != account_id:
        raise ContractError("Dhan authentication account mismatch")
    token = value.get("accessToken")
    if not token:
        raise ContractError("Dhan token endpoint returned no accessToken")
    return str(token)


async def session_token(config: dict, state_dir) -> str:
    """Share a bounded-life token between the daemon and read-only checks."""
    import asyncio
    import fcntl
    import json
    import os
    from pathlib import Path
    access_token = os.environ.get("DHAN_ACCESS_TOKEN", "")
    if access_token:
        return access_token
    path = Path(state_dir)
    path.mkdir(parents=True, exist_ok=True)
    lock_path = path / "token.lock"
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    acquired = False
    try:
        deadline = time.monotonic() + 25
        while not acquired:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise ContractError("authentication lock timeout")
                await asyncio.sleep(.05)
        cached = path / "dhan_token.json"
        try:
            record = json.loads(cached.read_text())
        except (OSError, ValueError):
            record = {}
        issued = record.get("issued", 0)
        if record.get("account") == config["account_id"] and isinstance(issued, (int, float)) and 0 <= time.time() - issued < 20 * 3600 and isinstance(record.get("token"), str) and record["token"]:
            return record["token"]
        token = await resolve_dhan_access_token(config["account_id"], pin=os.environ.get("DHAN_PIN", ""), totp_secret=os.environ.get("DHAN_TOTP_SECRET", ""), auth_url=config.get("dhan_auth_url", "https://auth.dhan.co/app/generateAccessToken"))
        temporary = path / "dhan_token.json.tmp"
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "w") as stream:
            json.dump({"account": config["account_id"], "issued": time.time(), "token": token}, stream)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(cached)
        return token
    finally:
        if acquired:
            fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
