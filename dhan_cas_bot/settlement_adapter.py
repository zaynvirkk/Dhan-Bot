from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from .domain import ContractError
from .settlement import FinalValue


class FinalValueAdapter:
    """Accept only a dated official final value; provisional fields are rejected."""

    def parse(self, payload: dict[str, Any]) -> FinalValue:
        required = {"trading_date", "value", "source", "source_field", "published_at", "received_at", "revision", "settlement_regime", "finality_kind"}
        if set(payload) != required:
            raise ContractError("final value adapter fields are incomplete")
        final = FinalValue(payload["trading_date"], Decimal(str(payload["value"])), payload["source"], payload["source_field"], payload["published_at"], payload["received_at"], payload["revision"], payload["settlement_regime"], payload["finality_kind"])
        final.validate()
        if any(x in final.source_field.lower() for x in ("previous", "provisional", "ltpc", "iep")):
            raise ContractError("provisional/previous fields cannot establish finality")
        return final
