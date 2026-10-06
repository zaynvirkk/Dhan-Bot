from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
import json

from .domain import CasPhase, ContractError, Mandate
from .ledger import Ledger
from .orders import Broker, OrderManager
from .risk import Allocation, FeeSchedule
from .telemetry import Telemetry


@dataclass
class RuntimeStatus:
    software_verified: bool = False
    current_account_funded: bool = False
    broker_route_verified: bool = False
    official_cas_signal_seen: bool = False
    final_value_source_verified: bool = False
    auto_live_armed: bool = False
    profitability_status: str = "UNKNOWN"
    state: str = "DISARMED"
    reason: str = ""

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


class AutoLive:
    def __init__(self, ledger: Ledger, broker: Broker, mandate: Mandate, *, software_verified: bool = False):
        mandate.validate()
        if mandate.account_id != broker.account_id:
            raise ContractError("mandate and broker account differ")
        self.ledger = ledger
        self.broker = broker
        self.mandate = mandate
        self.orders = OrderManager(ledger, broker)
        self.telemetry = Telemetry()
        ledger.telemetry = self.telemetry
        self.account_refresh = None
        self.enabled_strategies = frozenset({"CAS_LAG_V1"})
        self.status = RuntimeStatus(software_verified=software_verified, auto_live_armed=mandate.live_order_authority, state="ARMED_WAITING_SESSION" if mandate.live_order_authority else "DISARMED")

    async def recover(self) -> dict[str, Any]:
        self.status.state = "RECOVERING"
        result = await self.orders.reconcile()
        self.reconciled = result
        self.status.state = "ARMED_WAITING_SIGNAL" if self.mandate.live_order_authority else "DISARMED"
        return result

    async def refresh_account(self) -> None:
        self.status.current_account_funded = False
        try:
            funds = await self.broker.funds()
            self.status.current_account_funded = funds.spendable_cash > 0 and funds.broker_account == self.mandate.account_id
        except Exception as exc:
            # Funds qualify new premium debits. A failed funds endpoint must
            # not skip management of an already broker-reconciled long.
            self.status.reason = "ACCOUNT_FUNDS_UNAVAILABLE:"+type(exc).__name__

    def permit_entry(self, *, settlement_add=False, strategy="CAS_LAG_V1") -> bool:
        if strategy not in self.enabled_strategies or strategy not in {"CAS_LAG_V1", "GAP_FADE_DOUBLE", "NIFTY_SELLOFF_REBOUND_1510"}:
            return False
        if self.account_refresh is not None and not self.account_refresh.fresh:
            self.account_refresh.request()
            return False
        blocked = {"DISARMED", "RECOVERING"}
        if not settlement_add:
            blocked.add("SETTLEMENT_PENDING")
        signal_ready = self.status.official_cas_signal_seen if strategy == "CAS_LAG_V1" else True
        return bool(self.mandate.live_order_authority and self.mandate.allocated_capital > 0 and self.status.software_verified and self.status.current_account_funded and self.status.broker_route_verified and signal_ready and self.status.auto_live_armed and not self.ledger.metadata("disarmed", False) and self.status.state not in blocked)

    def disarm_new_entries(self) -> None:
        self.status.auto_live_armed = False
        self.status.state = "ENTRY_HALTED"
        self.status.reason = "operator_disarmed_new_entries"
        self.ledger.put_metadata("disarmed", True)

    def arm(self) -> None:
        if not self.mandate.live_order_authority:
            raise ContractError("standing mandate does not authorize live writes")
        self.status.auto_live_armed = True
        self.ledger.put_metadata("disarmed", False)
        self.status.state = "ARMED_WAITING_SIGNAL"
