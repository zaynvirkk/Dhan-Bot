from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
import json

from .domain import CasPhase, ContractError, Mandate
from .ledger import Ledger
from .orders import Broker, OrderManager
from .risk import Allocation, FeeSchedule


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
        self.status = RuntimeStatus(software_verified=software_verified, auto_live_armed=mandate.live_order_authority, state="ARMED_WAITING_SESSION" if mandate.live_order_authority else "DISARMED")

    async def recover(self) -> dict[str, Any]:
        self.status.state = "RECOVERING"
        result = await self.orders.reconcile()
        self.status.state = "ARMED_WAITING_SIGNAL" if self.mandate.live_order_authority else "DISARMED"
        return result

    async def refresh_account(self) -> None:
        funds = await self.broker.funds()
        self.status.current_account_funded = funds.spendable_cash > 0 and funds.broker_account == self.mandate.account_id

    def permit_entry(self) -> bool:
        return bool(self.status.software_verified and self.status.current_account_funded and self.status.broker_route_verified and self.status.official_cas_signal_seen and self.status.auto_live_armed and self.status.state not in {"DISARMED", "SETTLEMENT_PENDING"})

    def disarm_new_entries(self) -> None:
        self.status.auto_live_armed = False
        self.status.state = "ENTRY_HALTED"
        self.status.reason = "operator_disarmed_new_entries"

    def arm(self) -> None:
        if not self.mandate.live_order_authority:
            raise ContractError("standing mandate does not authorize live writes")
        self.status.auto_live_armed = True
        self.status.state = "ARMED_WAITING_SIGNAL"
