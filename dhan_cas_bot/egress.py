from __future__ import annotations

import ipaddress
import httpx

from .domain import ContractError


async def public_egress_ip(url: str = "https://api.ipify.org") -> str:
    async with httpx.AsyncClient(timeout=3.0, follow_redirects=False) as client:
        response = await client.get(url)
        response.raise_for_status()
        value = response.text.strip()
    try:
        ipaddress.ip_address(value)
    except ValueError as exc:
        raise ContractError("egress service returned a non-IP value") from exc
    return value


async def require_expected_egress(expected: str, *, lookup: str = "https://api.ipify.org") -> str:
    if not expected:
        raise ContractError("expected_egress_ip is required before any Dhan write")
    try:
        ipaddress.ip_address(expected)
    except ValueError as exc:
        raise ContractError("expected_egress_ip is invalid") from exc
    actual = await public_egress_ip(lookup)
    if actual != expected:
        raise ContractError("actual public egress does not match expected Dhan-whitelisted IP")
    return actual
