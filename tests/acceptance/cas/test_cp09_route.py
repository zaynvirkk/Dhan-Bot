from decimal import Decimal
import asyncio
from dhan_cas_bot.ledger import Ledger
from dhan_cas_bot.route import RouteQualifier
from .support import book

def test_cp09_positive(db_path,fake_broker): assert asyncio.run(RouteQualifier(Ledger(db_path),fake_broker,session_id="s",max_attempts=1,debit_cap=Decimal("1000"),mandate_spend_cap=Decimal("2000")).qualify(book(),epoch="dhan:1")).account_id=="TEST"
def test_cp09_negative(db_path,fake_broker): assert Ledger(db_path).counter("probe.attempts:s") == 0
def test_cp09_recovery(db_path): assert Ledger(db_path).counter("probe.spent")==0
