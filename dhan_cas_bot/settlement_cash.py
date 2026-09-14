"""Strict broker cash matching. Unclassified ledger text remains pending."""
from decimal import Decimal
import re

from .domain import ContractError
from .risk import FeeSchedule
from .strategy import intrinsic


def match_settlement(rows, *, account, instrument, final, quantity):
    gross = intrinsic(instrument.option_type,instrument.strike,final.value)*quantity
    estimated = max(Decimal("0"),gross-FeeSchedule().sell(gross,1))
    found=[]
    for row in rows:
        if str(row.get("dhanClientId","")) != account:
            raise ContractError("foreign broker ledger account")
        narration = str(row.get("narration","")).upper()
        if not any(word in narration for word in ("EXERCISE","EXPIRY SETTLEMENT")):
            continue
        if not re.search(r"(?<!\d)"+re.escape(instrument.security_id)+r"(?!\d)",narration):
            continue
        # Freeform statement entries without exact contract/date binding
        # cannot establish a specific option's cash receipt.
        if instrument.expiry.isoformat() not in narration or "NIFTY" not in narration:
            continue
        if row.get("exchange") not in {"NSE-FO","NSE-FNO","NSE_FNO","NSE-DERIVATIVES"}:
            continue
        credit=Decimal(str(row.get("credit","0")))-Decimal(str(row.get("debit","0")))
        if credit.is_finite() and estimated <= credit <= gross and row.get("vouchernumber"):
            found.append((str(row["vouchernumber"]),credit,row))
    return found[0] if len(found)==1 else None
