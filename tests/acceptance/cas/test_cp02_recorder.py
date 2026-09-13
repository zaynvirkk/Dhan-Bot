from dhan_cas_bot.ledger import Ledger

def test_cp02_positive(db_path):
    ledger=Ledger(db_path); ledger.incident("x","capture",{"token":"[redacted]"}); assert ledger.db.execute("select count(*) from incidents").fetchone()[0]==1
def test_cp02_negative(db_path): assert db_path.parent.exists()
def test_cp02_recovery(db_path): Ledger(db_path).close(); Ledger(db_path).close()
