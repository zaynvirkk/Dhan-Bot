from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from datetime import date, datetime

from .domain import ContractError, OptionType


@dataclass(frozen=True)
class FinalValue:
    trading_date: str
    value: Decimal
    source: str
    source_field: str
    published_at: str
    received_at: str
    revision: str
    settlement_regime: str
    finality_kind: str

    def validate(self) -> None:
        if self.source not in {"NSE", "NSE_CLEARING"} or self.source_field not in {"official_settlement_value", "closing_index_value"} or not self.value.is_finite() or self.value <= 0 or self.finality_kind not in {"FINAL", "OFFICIAL_SETTLEMENT"}:
            raise ContractError("final input is not verified")
        published = datetime.fromisoformat(self.published_at.replace("Z","+00:00"))
        received = datetime.fromisoformat(self.received_at.replace("Z","+00:00"))
        date.fromisoformat(self.trading_date)
        if not published.tzinfo or not received.tzinfo or published > received or not self.revision or self.settlement_regime not in {"CASH", "NSE_CAS_2026"}:
            raise ContractError("invalid final input provenance")


def exercise_intrinsic(option_type: OptionType, strike: Decimal, final_value: Decimal) -> Decimal:
    return max(final_value - strike, Decimal("0")) if option_type is OptionType.CE else max(strike - final_value, Decimal("0"))


def compare_sale_and_exercise(*, sale_proceeds: Decimal, exercise_value: Decimal, sale_costs: Decimal, exercise_costs: Decimal) -> str:
    if min(sale_proceeds, exercise_value, sale_costs, exercise_costs) < 0:
        raise ContractError("settlement amounts cannot be negative")
    return "SALE" if sale_proceeds - sale_costs >= exercise_value - exercise_costs else "EXERCISE"
