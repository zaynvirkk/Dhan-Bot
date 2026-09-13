from dhan_cas_bot.ledger import Ledger

def test_cp08_positive(db_path): assert Ledger(db_path).pending_intents()==[]
def test_cp08_negative(db_path): assert Ledger(db_path).counter("missing")==0
def test_cp08_recovery(db_path): Ledger(db_path).incident("restart","recovery",{}); assert Ledger(db_path).db.execute("select count(*) from incidents").fetchone()[0]==1
