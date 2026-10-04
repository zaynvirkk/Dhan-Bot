"""Observer correctness and credential isolation; no broker calls."""
from copy import deepcopy
from datetime import date, datetime, timezone
from decimal import Decimal as D
import json
from types import SimpleNamespace

from dhan_cas_bot.domain import Instrument, Level, OptionBook, OptionType, Segment
from dhan_cas_bot.observation_view import observation_view
from dhan_cas_bot.dashboard.data import observation_projection, runtime_view, ledger_view
from dhan_cas_bot.ledger import Ledger

NOW = datetime(2026, 10, 6, 9, 52, tzinfo=timezone.utc)


def engine():
    return SimpleNamespace(observations=[], reference=None, books={}, streaks={}, status=None,
                           last_signal_timestamp=-1, final_value=None)


def test_observer_missing_data_is_not_zero_or_signal():
    view = observation_projection(observation_view(engine(), []))
    assert view['iep'] is None and view['reference'] is None and view['direction'] is None
    assert view['watchlist'] == [] and view['expiry'] is None


def test_observer_shows_retained_inputs_without_evaluating_or_mutating_engine():
    e = engine()
    e.reference=SimpleNamespace(value=D('24000'))
    e.observations=[(D('24070'),'a'),(D('24060'),'b')]
    e.last_signal_timestamp=int(NOW.timestamp()*1000)
    instruments=[]
    for i in range(8):
        inst=Instrument(str(i),'NIFTY',Segment.NSE_FNO,date(2026,10,6),OptionType.CE,D(24000+i*50),65,D('.05'),1800)
        instruments.append(inst)
        e.books[str(i)]=OptionBook(inst,(Level(D('9'),65),),(Level(D('10'),65),),'epoch',int(NOW.timestamp()*1e9))
    e.streaks={'1':list(e.observations)}
    before=deepcopy(e.__dict__)
    raw=observation_view(e,instruments)
    assert e.__dict__==before
    assert raw['direction']=='CE' and len(raw['watchlist'])==5
    first=raw['watchlist'][0]
    assert first['security_id']=='1' and first['conditional_intrinsic']=='10'
    assert D(first['one_lot_cash'])>D(650) and first['confirmations']==2
    assert 'candidate' not in raw  # Quotes and confirmation do not establish entry permission.
    clean=observation_projection(raw)
    assert clean['iep']=='24060.00' and clean['iep_at']==NOW.isoformat()
    assert clean['watchlist'][0]['conditional_intrinsic']=='10.00'


def test_observer_empty_book_and_reconnect_clear_stale_values():
    e=engine()
    inst=Instrument('1','NIFTY',Segment.NSE_FNO,date(2026,10,6),OptionType.PE,D(24000),65,D('.05'),1800)
    e.books={'1':OptionBook(inst,(),(),'epoch',int(NOW.timestamp()*1e9))}
    raw=observation_view(e,[inst])
    assert raw['watchlist'][0]['one_lot_cash'] is None
    e.books.clear()
    assert observation_view(e,[inst])['watchlist']==[]


def test_projection_rejects_payloads_and_unknown_fields():
    secret='token-that-must-never-escape'
    raw={'phase':secret,'direction':secret,'iep':'NaN','reference':True,'headers':secret,
         'watchlist':[{'security_id':secret+'@','strike':'Infinity','bid':secret,'quantity':secret,'raw':secret}]*50}
    result=observation_projection(raw)
    assert secret not in json.dumps(result)
    assert result['iep'] is None and result['reference'] is None and len(result['watchlist'])==5
    assert observation_projection(None) is None
    assert observation_projection({'watchlist':secret})['watchlist']==[]


def test_runtime_reason_maps_rules_without_exposing_arbitrary_errors():
    good=runtime_view({'reason':'LAG_CONVERGED'},NOW)
    assert 'caught up' in good['reason']
    private=runtime_view({'reason':'private broker payload: token'},NOW)
    assert 'private' not in private['reason'] and private['observation'] is None


def test_ledger_entry_projection_is_bounded_and_never_returns_raw_payload(tmp_path):
    ledger=Ledger(tmp_path/'ledger.sqlite3')
    inst={'security_id':'123','strike':'24000','option_type':'CE'}
    payload={'book':{'instrument':inst,'private':'secret'},'reference':{'value':'23980'},
             'quantity':65,'limit':'10','history':[['24020','private_identity'],['24030','private_identity2']]}
    ledger.observe('decision:one','ENTRY_DECISION',payload)
    ledger.db.execute("INSERT INTO intents VALUES(?,?,?,?,?,?,?,?,?,?,?)",('one','private_client','life','BUY','123',65,'10','SENT','700','{}',NOW.isoformat()))
    ledger.db.commit()
    view=ledger_view(tmp_path/'ledger.sqlite3')
    assert view['available'] and view['last_entry']['quantity']==65
    assert view['last_entry']['confirmations']==2 and view['last_entry']['limit']=='10.00'
    assert 'private' not in json.dumps(view) and 'secret' not in json.dumps(view)
    ledger.db.close()
