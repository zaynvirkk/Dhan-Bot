from dhan_cas_bot.cli import selftest
from dhan_cas_bot.ledger import Ledger

def test_cp00_positive(): assert selftest()["software_verified"]
def test_cp00_negative(): assert selftest()["writes"] is False
def test_cp00_recovery(db_path): Ledger(db_path).close(); assert db_path.exists()
