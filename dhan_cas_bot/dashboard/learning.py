"""Read-only daily outcome reviews and durable, explicitly observed cash history."""
from collections import defaultdict
from datetime import datetime
from decimal import Decimal as D
import json
import os
from pathlib import Path
import tempfile
from zoneinfo import ZoneInfo

from dhan_cas_bot.session_strategies import STRATEGIES

IST = ZoneInfo('Asia/Kolkata')
EXIT_REASONS = {'SECONDS_INPUT_LOST', 'SECONDS_DIRECTION_FAILED', 'SECONDS_PREMIUM_STOP',
    'SECONDS_TARGET_REPRICED', 'NET_PROFIT_FLOOR', 'TIME_EXIT', 'PREMIUM_TARGET',
    'PREMIUM_STOP', 'TRAILING_STOP', 'DIRECTION_REVERSAL', 'LAG_CONVERGED',
    'CONTRACT_LAG_INVALIDATED', 'JOINT_REVERSAL', 'RECOVERY_OR_SIGNAL_UNAVAILABLE'}


def money(value):
    return format(D(value).quantize(D('.01')), 'f')


def day_at(value):
    at = datetime.fromisoformat(value)
    if at.tzinfo is None:
        raise ValueError('dated receipt required')
    return at.astimezone(IST).date().isoformat()


def session_reviews(db, now):
    db.row_factory = __import__('sqlite3').Row
    trades = defaultdict(list)
    attempts = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    lifecycle_rows = list(db.execute('SELECT * FROM lifecycles ORDER BY rowid DESC LIMIT 5001'))
    for row in lifecycle_rows[:5000]:
        payload = json.loads(row['payload'])
        strategy = payload.get('strategy', 'CAS_LAG_V1')
        if row['lifecycle_id'] == 'route-probe' or strategy not in STRATEGIES:
            continue
        intents = list(db.execute('SELECT * FROM intents WHERE lifecycle_id=? ORDER BY created_at', (row['lifecycle_id'],)))
        fills = list(db.execute('SELECT f.*,i.side FROM fills f JOIN intents i ON i.intent_id=f.intent_id WHERE i.lifecycle_id=? ORDER BY f.occurred_at', (row['lifecycle_id'],)))
        for intent in intents:
            if intent['side'] != 'BUY':
                continue
            dispatched = db.execute('SELECT 1 FROM attempts WHERE intent_id=? LIMIT 1', (intent['intent_id'],)).fetchone()
            if not dispatched:
                continue
            entry_day = day_at(intent['created_at'])
            attempts[entry_day][strategy][0] += 1
            attempts[entry_day][strategy][1] += int(any(f['intent_id'] == intent['intent_id'] for f in fills))
        buys, sells = ([f for f in fills if f['side'] == side] for side in ('BUY', 'SELL'))
        units = sum(f['quantity'] for f in buys)
        if row['state'] != 'CLOSED' or units <= 0 or units != sum(f['quantity'] for f in sells):
            continue
        debit = sum((D(f['price'])*f['quantity'] for f in buys), D(0))
        credit = sum((D(f['price'])*f['quantity'] for f in sells), D(0))
        charges = list(db.execute('SELECT c.order_id,c.fees,c.complete FROM order_charges c JOIN intents i ON i.intent_id=c.intent_id WHERE i.lifecycle_id=?', (row['lifecycle_id'],)))
        filled_orders = {f['order_id'] for f in fills}
        complete = {c['order_id'] for c in charges} == filled_orders and all(c['complete'] for c in charges)
        fees = sum((D(c['fees']) for c in charges), D(0))
        gross = credit-debit
        exit_state = db.execute('SELECT value FROM metadata WHERE key=?', ('directional-exit:'+row['lifecycle_id'],)).fetchone()
        reason = json.loads(exit_state[0]).get('reason') if exit_state else None
        if not reason:
            # Older auction lifecycles may lack a directional latch. Do not
            # invent a successful target exit from a positive realised price.
            reason = 'NOT_RECORDED'
        if reason not in EXIT_REASONS:
            reason = 'NOT_RECORDED'
        instrument = payload.get('instrument') or {}
        trades[day_at(sells[-1]['occurred_at'])].append({'strategy': strategy,
            'entry_at': buys[0]['occurred_at'], 'exit_at': sells[-1]['occurred_at'],
            'quantity': units, 'side': instrument.get('option_type') if instrument.get('option_type') in {'CE','PE'} else None,
            'strike': money(instrument['strike']) if instrument.get('strike') else None,
            'entry_price': money(debit/units), 'exit_price': money(credit/units),
            'gross_pnl': money(gross), 'net_pnl': money(gross-fees) if complete else None,
            'charges_complete': complete, 'exit_reason': reason,
            'holding_seconds': str((datetime.fromisoformat(sells[-1]['occurred_at'])-datetime.fromisoformat(buys[0]['occurred_at'])).total_seconds())})
    days = []
    for day in sorted(set(trades)|set(attempts), reverse=True):
        rows = trades[day]
        complete = bool(rows) and all(r['charges_complete'] for r in rows)
        gross = sum((D(r['gross_pnl']) for r in rows), D(0))
        entry_attempts = sum(a[0] for a in attempts[day].values())
        filled_entries = sum(a[1] for a in attempts[day].values())
        days.append({'date': day, 'closed_trades': len(rows), 'entry_attempts': entry_attempts,
            'filled_entries': filled_entries, 'unfilled_entries': entry_attempts-filled_entries,
            'gross_pnl': money(gross), 'net_pnl': money(sum((D(r['net_pnl']) for r in rows), D(0))) if complete else None,
            'charges_complete': complete, 'input_loss_exits': sum(r['exit_reason']=='SECONDS_INPUT_LOST' for r in rows),
            'strategies': [{'strategy': k, 'entry_attempts': a[0], 'filled_entries': a[1]} for k,a in attempts[day].items()],
            'findings':([{'code':'INPUT_LOSS_EXITS','count':sum(r['exit_reason']=='SECONDS_INPUT_LOST' for r in rows)}] if any(r['exit_reason']=='SECONDS_INPUT_LOST' for r in rows) else [])
                +([{'code':'FINAL_CHARGES_PENDING'}] if rows and not complete else [])
                +([{'code':'REALIZED_NET_LOSS'}] if complete and sum(D(r['net_pnl']) for r in rows)<0 else []),
            'trades': rows})
    return {'schema': 1, 'status': 'AVAILABLE', 'observed_at': now.isoformat(),
        'coverage': 'LATEST_5000_LIFECYCLES' if len(lifecycle_rows)>5000 else 'RECORDED_LIFECYCLES', 'days': days}


def remember_cash(path, report, now):
    from .data import freshness
    path = Path(path)
    if path.is_symlink() or (path.exists() and path.stat().st_size > 4*1024*1024):
        raise ValueError('cash memory unavailable; preserve evidence')
    data = json.loads(path.read_text()) if path.exists() else {'schema': 1, 'days': []}
    if data.get('schema') != 1 or not isinstance(data.get('days'), list):
        raise ValueError('cash memory invalid; preserve evidence')
    account = report.get('account') or {}
    if report.get('account_read_ok') is not True or not freshness(account.get('observed_at'), now, 60)['fresh']:
        return data
    try:
        cash = D(account['available_cash'])
        if not cash.is_finite() or cash < 0:
            return data
    except (KeyError, ValueError, ArithmeticError):
        return data
    at = account['observed_at']
    day = day_at(at)
    row = next((r for r in data['days'] if r['date'] == day), None)
    if row is None:
        row = {'date': day, 'first_at': at, 'first_cash': money(cash)}
        data['days'].append(row)
    if row.get('last_at') and datetime.fromisoformat(at) <= datetime.fromisoformat(row['last_at']):
        return data
    row.update(last_at=at, last_cash=money(cash), cash_change=money(cash-D(row['first_cash'])))
    # Separate this observation difference from realised strategy net P&L.
    data['observed_at'] = now.isoformat()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.cash-memory-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(data, stream, allow_nan=False)
            stream.flush(); os.fsync(stream.fileno())
        os.chmod(temporary, 0o640)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return data


def archive_reviews(path, result):
    """Keep earlier outcomes even after the bounded ledger projection moves on."""
    path=Path(path)
    if path.is_symlink() or (path.exists() and path.stat().st_size>8*1024*1024):
        raise ValueError('review archive unavailable; preserve evidence')
    previous=json.loads(path.read_text()) if path.exists() else {'schema':1,'days':[]}
    if previous.get('schema')!=1 or not isinstance(previous.get('days'),list):
        raise ValueError('review archive invalid; preserve evidence')
    days={r['date']:r for r in previous['days']}
    for row in result['days']:
        # A truncated window cannot replace a complete historical day's total.
        if result.get('coverage')=='LATEST_5000_LIFECYCLES' and row['date']==min(r['date'] for r in result['days']):
            if row['date'] in days:continue
        old=days.get(row['date'])
        if old and old.get('closed_trades',0)>0 and row.get('closed_trades')==0:
            days[row['date']]={**old,**({'health':row['health']} if 'health' in row else {})}
        else:days[row['date']]=row
    value={**result,'days':[days[k] for k in sorted(days,reverse=True)]}
    from .collect import atomic_json
    atomic_json(path,value)
    return value


def diagnostic_history(root, result):
    """Retain compact findings before the short raw health history expires."""
    by_day={r['date']:r for r in result['days']}
    for path in root.glob('session-audit-????-??-??.jsonl'):
        if path.is_symlink() or path.stat().st_size>16*1024*1024:continue
        date=path.name[14:24]
        # Read the append-only prefix; the last partial line may still be in flight.
        rows=[]
        for line in path.read_text().splitlines():
            try:rows.append(json.loads(line))
            except ValueError:continue
        if not rows:continue
        errors=set()
        for r in rows:
            for name,f in r.get('feeds',{}).items():
                for e in f.get('transport_events',[]):
                    if e.get('kind')=='ERROR':errors.add((name,e.get('at')))
        row=by_day.setdefault(date,{'date':date,'closed_trades':0,'entry_attempts':0,'filled_entries':0,
            'unfilled_entries':0,'gross_pnl':'0.00','net_pnl':None,'charges_complete':False,
            'input_loss_exits':0,'strategies':[],'trades':[],'findings':[]})
        row['health']={'samples':len(rows),'first_at':rows[0]['at'],'last_at':rows[-1]['at'],
            'recovering_samples':sum(r.get('state')=='RECOVERING' for r in rows),
            'transport_errors':len(errors),'coverage':'SAMPLED_DIAGNOSTICS',
            'releases':sorted({r['funded_source'] for r in rows if r.get('funded_source')})}
    return {**result,'days':[by_day[k] for k in sorted(by_day,reverse=True)]}


def build_learning(config, output, report, now):
    import sqlite3
    root = Path(output).parent
    try:
        with sqlite3.connect('file:'+str(Path(config['state_dir'])/'ledger.sqlite3')+'?mode=ro', uri=True, timeout=.2) as db:
            result = session_reviews(db, now)
        result=diagnostic_history(root,result)
        result=archive_reviews(root/'session-memory.json',result)
        result['cash_observations'] = remember_cash(root/'learning-cash.json', report, now)
        result['lessons'] = json.loads(Path(__file__).with_name('lessons.json').read_text())
        return result
    except (OSError, ValueError, TypeError, sqlite3.Error):
        try:
            old=json.loads((root/'learning.json').read_text())
            if old.get('schema')==1 and isinstance(old.get('days'),list):
                return {**old,'status':'STALE','failed_at':now.isoformat()}
        except (OSError,ValueError,TypeError):pass
        return {'schema': 1, 'status': 'UNAVAILABLE', 'observed_at': now.isoformat(), 'days': [], 'lessons': []}
