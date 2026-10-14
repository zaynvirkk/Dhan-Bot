import json
from dhan_cas_bot.ledger import Ledger
from dhan_cas_bot.dashboard.performance import strategy_performance


def populate(tmp_path,complete=True):
    l=Ledger(tmp_path/'history.sqlite3');d=l.db
    d.execute('INSERT INTO lifecycles VALUES(?,?,?,?,?,?)',('private-life','2026-10-13','101','9411','CLOSED',json.dumps({'token':'secret','strategy':'CAS_LAG_V1','instrument':{'strike':'22700','option_type':'CE'}})))
    for side,price,stamp in [('BUY','10','2026-10-13T09:50:00+00:00'),('SELL','12','2026-10-13T09:50:05+00:00')]:
        ident='private-'+side
        d.execute('INSERT INTO intents VALUES(?,?,?,?,?,?,?,?,?,?,?)',(ident,'private-client'+side,'private-life',side,'101',65,price,'FILLED','0','{}',stamp))
        d.execute('INSERT INTO fills VALUES(?,?,?,?,?,?,?,?,?)',('private-fill'+side,'private-order'+side,ident,'101',65,price,'0',stamp,'{"token":"secret"}'))
        d.execute('INSERT INTO order_charges VALUES(?,?,?,?,?,?)',('private-order'+side,ident,'20',int(complete),stamp,'{"token":"secret"}'))
    return l


def test_per_strategy_result_uses_actual_turnover_and_complete_fees(tmp_path):
    l=populate(tmp_path);r=strategy_performance(l.db)[0]
    assert r['strategy']=='CAS_LAG_V1' and r['gross_pnl']=='130'
    assert r['reported_charges']=='40' and r['net_pnl']=='90'
    assert r['filled_closed']==1 and r['net_wins']==1
    assert r['trades'][0]['holding_seconds']=='5.0'
    assert 'private-' not in json.dumps(r) and 'secret' not in json.dumps(r)


def test_incomplete_charges_do_not_invent_final_net_profit(tmp_path):
    l=populate(tmp_path,False);r=strategy_performance(l.db)[0]
    assert r['gross_pnl']=='130' and r['net_pnl'] is None
    assert r['net_wins'] is None and r['charges_complete'] is False


def test_empty_lifecycle_is_not_a_losing_trade(tmp_path):
    l=Ledger(tmp_path/'empty.sqlite3')
    l.db.execute('INSERT INTO lifecycles VALUES(?,?,?,?,?,?)',('empty','2026-10-13','101','9411','CLOSED','{}'))
    assert strategy_performance(l.db)==[]


def test_funded_projection_and_exit_suffix_do_not_hide_actual_policy():
    from dhan_cas_bot.dashboard.data import runtime_view
    from datetime import datetime,timezone
    now=datetime.now(timezone.utc)
    r=runtime_view({'observed_at':now.isoformat(),'funded_strategies':['CAS_LAG_V1','private-secret'],
        'reason':'ORDINARY_PUBLISHED_PCR_TRAIL:TIME_EXIT'},now)
    assert r['funded_strategies']==['CAS_LAG_V1']
    assert 'deadline' in r['reason'].lower()
