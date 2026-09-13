from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import pytest

from dhan_cas_bot.domain import FundsSnapshot


class FakeBroker:
    account_id = "TEST"

    def __init__(self, *, fill: bool = False):
        self.fill = fill
        self.requests = []
        self._orders = []
        self._trades = []
        self._positions = []

    async def submit_order(self, request):
        self.requests.append(request)
        order_id = f"O{len(self.requests)}"
        self._orders.append({"orderId": order_id, "correlationId": request["correlationId"], "orderStatus": "TRADED" if self.fill else "CANCELLED"})
        if self.fill:
            self._trades.append({"tradeId": f"T{len(self._trades)+1}", "orderId": order_id, "tradedQuantity": request["quantity"], "tradedPrice": request["price"], "fees": "20"})
        return self._orders[-1]

    async def order(self, order_id):
        return next((x for x in self._orders if x["orderId"] == order_id), None)

    async def orders(self): return list(self._orders)
    async def trades(self): return list(self._trades)
    async def positions(self): return list(self._positions)
    async def funds(self): return FundsSnapshot(datetime.now(timezone.utc), Decimal("9411.18"), Decimal("9411.18"), Decimal("9411.18"), Decimal("0"), self.account_id)


@pytest.fixture
def fake_broker():
    return FakeBroker()


@pytest.fixture
def db_path(tmp_path: Path):
    return tmp_path / "ledger.sqlite3"
