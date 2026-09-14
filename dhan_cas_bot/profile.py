"""Narrow account-profile eligibility, independent of data subscription."""
import re

from .domain import ContractError


def require_derivatives_profile(profile: dict, account: str) -> None:
    if not isinstance(profile,dict) or str(profile.get("dhanClientId"))!=account:
        raise ContractError("Dhan profile account mismatch")
    if profile.get("dataPlan")!="Active":
        raise ContractError("Dhan data subscription is not active")
    raw=profile.get("activeSegment")
    if not isinstance(raw,str):
        raise ContractError("Dhan active trading segments are unavailable")
    # The live profile uses compact exchange segment codes (E, D, C, M),
    # whereas the published profile example uses their descriptive names.
    segments={part.strip().upper() for part in re.split(r"[,;|]",raw)}
    if not segments & {"D","DERIVATIVE","DERIVATIVES","NSE_FNO","EQUITY F&O","F&O"}:
        raise ContractError("Dhan F&O segment is not confirmed active; check Profile > Equity F&O, Commodities & Currencies")
