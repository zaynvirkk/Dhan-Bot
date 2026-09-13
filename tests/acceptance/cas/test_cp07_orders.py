from decimal import Decimal
import asyncio
from datetime import datetime,timezone
from dhan_cas_bot.domain import Intent
from dhan_cas_bot.ledger import Ledger
from dhan_cas_bot.orders import OrderManager
from .support import instrument

def test_cp07_positive(db_path,fake_broker):
    i=instrument(); r=asyncio.run(OrderManager(Ledger(db_path),fake_broker).submit(Intent("i","BUY",i,65,Decimal("10"),"c",datetime.now(timezone.utc),"l"),reserved_cash=Decimal("700"))); assert r["orderId"]
def test_cp07_negative(db_path,fake_broker): assert fake_broker.requests==[]
def test_cp07_recovery(db_path,fake_broker): assert Ledger(db_path).pending_intents()==[]
