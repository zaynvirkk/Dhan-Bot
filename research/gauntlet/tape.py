"""Reconcile trade-candle absence with official end-of-day traded quantity.

EOD is used only to audit archive completeness. It never supplies decision
prices, direction, quantity or a profitable fill. Missing no-trade minutes use
the last known price/OI, or previous session's published values before open.
"""
import json,sqlite3
from datetime import datetime,timedelta
from decimal import Decimal as D
from .data import CACHE
from .core import Bar

DB=CACHE/'contract_audit.sqlite'

def build_audit():
    from .contracts import exchange_contracts
    u=json.loads((CACHE/'universe.json').read_text())
    with sqlite3.connect(DB) as db:
        db.execute('CREATE TABLE IF NOT EXISTS contracts(day TEXT,id TEXT,close TEXT,oi INTEGER,lot INTEGER,lots INTEGER,tx INTEGER,PRIMARY KEY(day,id))')
        db.execute('CREATE TABLE IF NOT EXISTS loaded(day TEXT PRIMARY KEY)')
        done={r[0] for r in db.execute('SELECT day FROM loaded')}
        for day,v in sorted(u.items()):
            if '_error' in v or day in done:continue
            rows=exchange_contracts(day)
            db.executemany('INSERT OR REPLACE INTO contracts VALUES(?,?,?,?,?,?,?)',[(day,r['FinInstrmId'],r['ClsPric'],int(r['OpnIntrst'] or 0),int(r['NewBrdLotQty'] or 1),int(r['TtlTradgVol'] or 0),int(r['TtlNbOfTxsExctd'] or 0)) for r in rows])
            db.execute('INSERT INTO loaded VALUES(?)',(day,));db.commit()
        print('audited exchange sessions',db.execute('SELECT count(*) FROM loaded').fetchone()[0],flush=True)

def record(key,day):
    if not DB.exists():return None
    with sqlite3.connect('file:'+str(DB)+'?mode=ro',uri=True) as db:
        return db.execute('SELECT close,oi,lot,lots,tx FROM contracts WHERE day=? AND id=?',(day,key.split('|')[1])).fetchone()

def normalize(key,day,rows):
    from .contracts import previous_session
    official=record(key,day)
    if official is None:return rows,{'status':'UNKNOWN_OFFICIAL_VOLUME'}
    known_units=sum(int(r[5]) for r in rows)
    expected=int(official[2])*int(official[3])
    if known_units!=expected:
        return rows,{'status':'UNKNOWN_VOLUME_MISMATCH','reported_units':known_units,'official_units':expected}
    bytime={r[0]:r for r in rows}
    if len(bytime)!=len(rows):raise ValueError('duplicate option timestamp')
    previous=record(key,previous_session(day))
    price=D(previous[0]) if previous else None;oi=int(previous[1]) if previous else 0
    start=datetime.fromisoformat(day+'T09:15:00+05:30')
    end=datetime.fromisoformat(day+('T15:40:00+05:30' if day>='2026-08-03' else 'T15:30:00+05:30'))
    result=[];filled=0
    while start<end:
        row=bytime.get(start.isoformat())
        if row is not None:
            bar=Bar.parse(row);price=bar.close;oi=bar.oi;result.append(row)
        elif price is not None and price>0:
            result.append([start.isoformat(),str(price),str(price),str(price),str(price),0,oi]);filled+=1
        start+=timedelta(minutes=1)
    return result,{'status':'EXACT_DAILY_VOLUME_RECONCILED','filled_no_trade_minutes':filled,'official_units':expected,
        'assumption':'Historical OI as reported; carried through verified no-trade minutes.'}

if __name__=='__main__':build_audit()
