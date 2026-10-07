"""Allowlisted projections of local evidence; never return raw broker payloads."""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re
import sqlite3
from urllib.parse import quote
from dhan_cas_bot.telemetry import METRICS, REASONS as TIMING_REASONS

UTC = timezone.utc
# The collector can spend 20s reading Dhan, then waits 15s before its next run.
# Allow that normal cycle plus scheduling/network margin, not a 15s flicker.
RUNTIME_TTL_SECONDS = 45
STATES = {'DISARMED', 'RECOVERING', 'ARMED_WAITING_SESSION', 'ARMED_WAITING_SIGNAL',
          'ENTRY_HALTED', 'NO_TRADE_DAY', 'SETTLEMENT_PENDING', 'POSITION_OPEN', 'ENTRY_PENDING', 'EXIT_PENDING',
          'WAITING_EXCHANGE_SESSION', 'RECONCILING_DIRECTIONAL_POSITION'}
STRATEGY_NAMES = {'CAS_LAG_V1', 'GAP_FADE_DOUBLE', 'NIFTY_SELLOFF_REBOUND_1510'}
STRATEGY_REASONS = {
    'INPUTS_NOT_RECEIVED', 'CALENDAR_UNAVAILABLE', 'EXCHANGE_CLOSED', 'CONTRACT_CALENDAR_UNAVAILABLE',
    'EXPIRY_SESSION_OUTSIDE_RESEARCH_SCOPE', 'OUTSIDE_STRATEGY_WINDOW', 'SPECIAL_SESSION_OUTSIDE_RESEARCH_SCOPE',
    'NEXT_SESSION_EXIT_UNAVAILABLE', 'SELLOFF_THRESHOLD_MET', 'SELLOFF_BELOW_THRESHOLD',
    'GAP_FADE_CONFIRMED', 'GAP_FADE_CONDITIONS_NOT_MET', 'COMPLETED_INPUT_MISSING_OR_INVALID',
    'NOT_CONFIGURED', 'STRATEGY_INPUTS_STALE', 'STRATEGY_INPUT_UNAVAILABLE', 'ENTRY_DEADLINE_MISSED',
    'ENTRY_NOT_PERMITTED', 'OPTION_MINUTES_UNAVAILABLE', 'OPTION_BOOK_UNAVAILABLE_OR_STALE',
    'FIXED_LIMIT_ALREADY_MISSED', 'NO_AFFORDABLE_LIQUID_CONTRACT', 'UNMANAGED_ACCOUNT_POSITION',
}
ORDER_STATES = {'PENDING_SEND', 'SEND_UNKNOWN', 'SENT', 'TRANSIT', 'PENDING', 'CLOSED',
                'TRIGGERED', 'REJECTED', 'CANCELLED', 'PART_TRADED', 'TRADED', 'FILLED',
                'EXPIRED', 'ABORTED'}
CHECK_FIELDS = {
    'dhan_auth': ('account_matches', 'derivatives_enabled', 'data_plan'),
    'dhan_account': ('orders', 'positions', 'trades', 'whitelist_resolved'),
    'egress': ('matches_expected',),
    'contract_metadata': ('expiry', 'instruments', 'freeze_quantity'),
    'upstox_feed': ('websocket_connected', 'index_seen', 'protobuf_frames', 'cas_status_seen', 'index_iep_seen', 'close_received_code', 'close_sent_code', 'keepalive_timeout'),
    'dhan_market_feed': ('websocket_connected', 'full_packets', 'book_verified', 'close_received_code', 'close_sent_code', 'keepalive_timeout'),
    'dhan_order_socket': ('websocket_connected', 'route_verified', 'close_received_code', 'close_sent_code', 'keepalive_timeout'),
}
REASONS = {
    'NO_EXECUTABLE_LAG_OR_REMAINING_ALLOWANCE': 'No contract passes the price, depth, fees and remaining capital checks.',
    'UNMANAGED_ACCOUNT_POSITION': 'An account position is not managed by this bot. New entries are blocked.',
    'CAS_LAG_V1': 'An auction-lag entry was submitted. Waiting for broker execution updates.',
    'FINAL_RESIDUAL': 'A confirmed-final-value entry was submitted. Waiting for broker execution updates.',
    'DIRECTION_REVERSAL': 'The auction direction reversed. The bot is reducing its position.',
    'CONTRACT_LAG_INVALIDATED': 'The contract lost its qualifying price discrepancy. The bot is reducing its position.',
    'LAG_CONVERGED': 'The option price caught up with the auction value. The bot is reducing its position.',
    'JOINT_REVERSAL': 'Both intrinsic value and bid reversed. The bot is reducing its position.',
    'TIME_EXIT': 'The exit deadline was reached. The bot is reducing its position.',
    'OPTION_BOOK_UNAVAILABLE': 'The option book is unavailable. The bot is handling the open position.',
    'RECOVERY_OR_SIGNAL_UNAVAILABLE': 'Signal or connection recovery is required. The bot is handling the open position.',
    'SIGNAL_UNAVAILABLE': 'No usable auction state is available.',
    'COLLECTION_STOPPED_NO_FINAL_INPUT': 'Auction collection stopped without a verified final value. The bot is reducing its position.',
    'CONFIRMED_FINAL_EXERCISE_VALUE_EXCEEDS_FINITE_SALE': 'The recorded final exercise value exceeds the supported sale proceeds. Settlement is pending.',
    'ACCOUNT_FUNDS_UNAVAILABLE': 'The broker cash request failed. New entries are blocked.',
    'RECOVERY_REQUIRED': 'The bot is reconciling broker state before considering entries.',
    'OFFICIAL_INDEX_IEP_UNAVAILABLE': 'Waiting for an official indicative index value.',
    'FOREIGN_CAS_DATE': 'The received auction event belongs to a different session.',
    'INVALID_ORDER_EVENT': 'An order event failed validation.',
    'ROUTE_PROBE': 'The order-route qualification has not completed.',
    'operator_disarmed_new_entries': 'New entries were disabled by the operator.',
    'GAP_FADE_DOUBLE': 'The gap-fade engine is handling this position. See orders and fills for execution.',
    'NIFTY_SELLOFF_REBOUND_1510': 'The rebound engine is handling this position. See orders and fills for execution.',
    'EXIT_LATCHED_WAITING_EXCHANGE_SESSION': 'An exit is due. Waiting for a verified open exchange session.',
    'EXIT_LATCHED_WAITING_CURRENT_BOOK': 'An exit is due. Waiting for a current option book.',
}


def utcnow():
    return datetime.now(UTC)


def timestamp(value):
    if not isinstance(value, str) or len(value) > 40:
        return None
    try:
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return dt.astimezone(UTC).isoformat() if dt.tzinfo else None
    except (ValueError, OverflowError):
        return None


def freshness(value, now, ttl):
    stamp = timestamp(value)
    age = (now - datetime.fromisoformat(stamp)).total_seconds() if stamp else None
    valid = age is not None and age >= -5
    return {'observed_at': stamp, 'age_seconds': max(0, int(age)) if valid else None,
            'fresh': bool(valid and age <= ttl)}


def money(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or abs(amount) >= Decimal('1e18'):
            return None
        return format(amount.quantize(Decimal('.01')), 'f')
    except (InvalidOperation, ValueError, TypeError):
        return None


def integer(value):
    if isinstance(value, bool):
        return None
    try:
        n = Decimal(str(value))
        return int(n) if n.is_finite() and n == n.to_integral_value() and abs(n) < 10**15 else None
    except (InvalidOperation, ValueError, TypeError):
        return None


def label(value):
    # These are instrument/order identifiers, not arbitrary provider messages.
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9 ._:/+()-]{1,96}', value):
        return None
    return value


def choice(value, allowed, default=None):
    return value if isinstance(value, str) and value in allowed else default


def read_json(path, limit=2_000_000):
    try:
        with Path(path).open('rb') as stream:
            raw = stream.read(limit + 1)
        if len(raw) > limit:
            return None
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError, RecursionError):
        return None


def runtime_view(raw, now):
    raw = raw or {}
    timing = freshness(raw.get('observed_at'), now, RUNTIME_TTL_SECONDS)
    authority = 'UNKNOWN'
    if timing['fresh']:
        if raw.get('writes') is False:
            authority = 'DISABLED'
        elif raw.get('writes') is True and type(raw.get('auto_live_armed')) is bool:
            authority = 'ENABLED' if raw['auto_live_armed'] else 'DISABLED'
    flags = {k: raw.get(k) if type(raw.get(k)) is bool else None for k in
             ('software_verified', 'current_account_funded', 'broker_route_verified',
              'official_cas_signal_seen', 'final_value_source_verified', 'auto_live_armed', 'writes')}
    prefix = str(raw.get('reason', '')).split(':')[0]
    return {**timing, **flags, 'authority': authority,
            'state': choice(raw.get('state'), STATES, 'UNKNOWN'),
            'reason': REASONS.get(prefix, 'No specific decision reason was recorded.'),
            'session': timestamp(str(raw.get('session', '')) + 'T00:00:00+05:30'),
            'books_observed': integer(raw.get('books_observed')),
            'contract_count': integer(raw.get('contract_count')),
            'clock_uncertainty_ms': integer(raw.get('clock_uncertainty_ms')),
            'monitoring_mode': choice(raw.get('monitoring_mode'), {'IDLE', 'ACTIVE'}, 'UNKNOWN'),
            'strategies': [s for s in raw.get('strategies', []) if isinstance(s, str) and s in STRATEGY_NAMES] if isinstance(raw.get('strategies'), list) else [],
            'strategy_evaluations': strategy_projection(raw.get('strategy_evaluations')),
            'expiry_today': raw.get('expiry_today') if type(raw.get('expiry_today')) is bool else None,
            'calendar_checked_at': timestamp(raw.get('calendar_checked_at')),
            'feed_health': feed_health_view(raw.get('feed_health')),
            'recorder_pending': integer(raw.get('recorder_pending')),
            'telemetry': telemetry_view(raw.get('telemetry')),
            'observation': observation_projection(raw.get('observation'))}


def strategy_projection(raw):
    result=[]
    for row in raw[:3] if isinstance(raw, list) else []:
        if not isinstance(row, dict) or choice(row.get('strategy'), STRATEGY_NAMES) is None:
            continue
        details={}
        for key in ('gap', 'fraction_filled', 'future_5m_return', 'open_return'):
            value=(row.get('details') or {}).get(key) if isinstance(row.get('details'), dict) else None
            if money(value) is not None:
                details[key]=str(Decimal(str(value)))
        result.append({'strategy':row['strategy'],
            'enabled':row.get('enabled') if type(row.get('enabled')) is bool else None,
            'state':choice(row.get('state'), {'UNKNOWN','WAITING','SIGNAL','NO_SIGNAL','NOT_APPLICABLE','DISABLED'},'UNKNOWN'),
            'reason':choice(str(row.get('reason','')).split(':')[0],STRATEGY_REASONS,'UNKNOWN'),
            'evaluated_at':timestamp(row.get('evaluated_at')), 'side':choice(row.get('side'), {'CE','PE'}),
            'spot':money(row.get('spot')), 'exit_at':timestamp(row.get('exit_at')), 'details':details,
            'last_execution_reason':choice(str(row.get('last_execution_reason','')).split(':')[0],STRATEGY_REASONS,'UNKNOWN')})
    return result


def observation_projection(raw):
    if not isinstance(raw, dict):
        return None
    watch = raw.get('watchlist')
    watch = watch if isinstance(watch, list) else []
    return {
        'phase': choice(raw.get('phase'), {'CTS_CLOSE', 'CAS_LM_START', 'CAS_M_STOP', 'CAS_STOP', 'UNKNOWN'}),
        'phase_at': timestamp(raw.get('phase_at')), 'iep_at': timestamp(raw.get('iep_at')),
        'ltp_at': timestamp(raw.get('ltp_at')), 'ltp_received_at': timestamp(raw.get('ltp_received_at')),
        'direction': choice(raw.get('direction'), {'CE', 'PE'}),
        'expiry': timestamp(str(raw.get('expiry', '')) + 'T00:00:00+05:30'),
        **{key: money(raw.get(key)) for key in ('reference', 'iep', 'final_value', 'ltp')},
        'watchlist': [{
            'security_id': label(row.get('security_id')),
            'option_type': choice(row.get('option_type'), {'CE', 'PE'}),
            'expiry': timestamp(str(row.get('expiry', '')) + 'T00:00:00+05:30'),
            'observed_at': timestamp(row.get('observed_at')),
            **{key: money(row.get(key)) for key in ('strike', 'bid', 'ask', 'one_lot_cash', 'conditional_intrinsic', 'last_price')},
            **{key: integer(row.get(key)) for key in ('lot_size', 'bid_quantity', 'ask_quantity', 'confirmations', 'volume', 'open_interest')},
        } for row in watch[:5] if isinstance(row, dict)],
    }


def feed_health_view(raw):
    raw = raw if isinstance(raw, dict) else {}
    result = {}
    for name in ('signal', 'market', 'order'):
        item = raw.get(name)
        if not isinstance(item, dict):
            continue
        result[name] = {'connected': item.get('connected') if type(item.get('connected')) is bool else None,
                        **{key: timestamp(item.get(key)) for key in ('last_received_at', 'last_processed_at', 'last_usable_at')},
                        **{key: integer(item.get(key)) for key in ('reconnects', 'pending_messages', 'queue_high_water', 'processed_messages')},
                        **{key: money(item.get(key)) for key in ('oldest_pending_ms', 'queue_delay_ms', 'processing_ms')},
                        'last_error': choice(item.get('last_error'), {'ContractError', 'OSError', 'EOFError', 'TimeoutError', 'ConnectionClosedError', 'InvalidHandshake', 'HTTPStatusError'})}
    return result


def telemetry_view(raw):
    raw = raw if isinstance(raw, dict) else {}
    latency, counts = raw.get('latency', {}), raw.get('decision_counts', {})
    latency = latency if isinstance(latency, dict) else {}
    counts = counts if isinstance(counts, dict) else {}
    return {'scope': 'current_process_rolling_512',
            'latency': {key: {field: money(value.get(field)) for field in ('p50', 'p95', 'p99')}
                        | {'samples': integer(value.get('samples'))}
                        for key, value in latency.items() if key in METRICS and isinstance(value, dict)},
            'decision_counts': {key: integer(value) for key, value in counts.items() if key in TIMING_REASONS}}


def shared_account(raw, now):
    """Re-allowlist the trader's read model at the sidecar boundary."""
    if not isinstance(raw, dict) or raw.get('schema') != 1:
        return None
    stamp = freshness(raw.get('observed_at'), now, 60)
    if not stamp['fresh']:
        return None
    account = raw.get('account')
    if raw.get('account_read_ok') is not True or not isinstance(account, dict):
        return {'account': None, 'account_read_ok': False}
    if account.get('observed_at') != raw.get('observed_at'):
        return None
    positions, orders = account.get('positions'), account.get('orders')
    if not isinstance(positions, list) or not isinstance(orders, list):
        return None
    clean = {'observed_at': stamp['observed_at']}
    for key in ('available_cash', 'realised_pnl', 'unrealised_pnl'):
        clean[key] = money(account.get(key))
    if clean['available_cash'] is None:
        return None
    for key in ('open_position_count', 'order_count'):
        clean[key] = integer(account.get(key))
    for key in ('positions_truncated', 'orders_truncated'):
        clean[key] = account.get(key) is True
    clean['positions'] = [{
        'symbol': label(row.get('symbol')), 'security_id': label(row.get('security_id')),
        'quantity': integer(row.get('quantity')), 'average_price': money(row.get('average_price')),
        'realised': money(row.get('realised')), 'unrealised': money(row.get('unrealised')),
        'product': choice(row.get('product'), {'MARGIN', 'INTRADAY', 'CNC'})
    } for row in positions[:100] if isinstance(row, dict)]
    clean['orders'] = [{
        'symbol': label(row.get('symbol')), 'security_id': label(row.get('security_id')),
        'quantity': integer(row.get('quantity')), 'filled_quantity': integer(row.get('filled_quantity')),
        'price': money(row.get('price')), 'side': choice(row.get('side'), {'BUY', 'SELL'}),
        'state': choice(row.get('state'), ORDER_STATES, 'UNKNOWN')
    } for row in orders[:100] if isinstance(row, dict)]
    return {'account': clean, 'account_read_ok': True}


def connections_view(raw, now):
    raw = raw or {}
    timing = freshness(raw.get('observed_at'), now, 900)
    result = []
    for name, fields in CHECK_FIELDS.items():
        item = raw.get('checks', {}).get(name, {}) if isinstance(raw.get('checks'), dict) else {}
        item = item if isinstance(item, dict) else {}
        status = choice(item.get('status'), {'PASS', 'FAIL', 'SKIP', 'NO_DATA'}, 'UNKNOWN')
        facts = {}
        for field in fields:
            v = item.get(field)
            if type(v) in (bool, int): facts[field] = v
            elif field == 'expiry': facts[field] = timestamp(str(v) + 'T00:00:00+05:30')
            elif field == 'data_plan': facts[field] = choice(v, {'Active', 'Inactive', 'Expired'}, 'UNKNOWN')
        error = item.get('error_type')
        result.append({'name': name, 'status': status,
                       'error_type': choice(error, {'ContractError', 'TimeoutError', 'HTTPStatusError', 'OSError', 'ConnectionClosedError'}),
                       'http_status': integer(item.get('http_status')), 'facts': facts})
    return {**timing, 'checks': result}


def position_view(row):
    return {'symbol': label(row.get('tradingSymbol')), 'security_id': label(str(row.get('securityId', ''))),
            'quantity': integer(row.get('netQty', row.get('netQuantity'))),
            'average_price': money(row.get('buyAvg', row.get('averagePrice'))),
            'realised': money(row.get('realizedProfit')), 'unrealised': money(row.get('unrealizedProfit')),
            'product': choice(row.get('productType'), {'MARGIN', 'INTRADAY', 'CNC'})}


def broker_order_view(row):
    return {'symbol': label(row.get('tradingSymbol')), 'security_id': label(str(row.get('securityId', ''))),
            'side': choice(row.get('transactionType'), {'BUY', 'SELL'}),
            'state': choice(row.get('orderStatus'), ORDER_STATES, 'UNKNOWN'),
            'quantity': integer(row.get('quantity')), 'filled_quantity': integer(row.get('filledQty', row.get('filledQuantity'))),
            'price': money(row.get('price'))}


def account_view(funds, positions, orders, now):
    cash = money(funds.spendable_cash)
    if cash is None:
        raise ValueError('available cash is not a finite amount')
    if not isinstance(positions, list) or not isinstance(orders, list) or any(not isinstance(p, dict) for p in positions + orders):
        raise ValueError('invalid account response')
    if len(positions) > 10000 or len(orders) > 10000:
        raise ValueError('account response exceeds monitor limit')
    projected = [position_view(p) for p in positions]
    if any(p['quantity'] is None for p in projected):
        raise ValueError('position quantity unavailable')
    def total(key):
        values = [p[key] for p in projected]
        return money(sum((Decimal(v) for v in values), Decimal('0'))) if values and all(v is not None for v in values) else None
    open_positions = [p for p in projected if p['quantity'] != 0]
    return {'observed_at': now.isoformat(), 'available_cash': cash,
            'realised_pnl': total('realised'), 'unrealised_pnl': total('unrealised'),
            'open_position_count': len(open_positions), 'positions': open_positions[:100],
            'order_count': len(orders), 'orders': [broker_order_view(o) for o in orders[-100:]][::-1],
            'positions_truncated': len(open_positions) > 100, 'orders_truncated': len(orders) > 100}


def ledger_view(path):
    """One SQLite read transaction, no schema initialization or broker methods."""
    out = {'available': False, 'orders': None, 'fills': None, 'incidents': None, 'counts': None}
    if not Path(path).is_file():
        return out
    try:
        with closing(sqlite3.connect('file:' + quote(str(Path(path).resolve()), safe='/') + '?mode=ro', uri=True, timeout=.2)) as db:
            db.row_factory = sqlite3.Row
            db.execute('PRAGMA query_only=ON')
            db.execute('BEGIN')
            # Bound the historical count work on a large or damaged ledger.
            budget = [0]
            def interrupt():
                budget[0] += 1
                return int(budget[0] > 2000)
            db.set_progress_handler(interrupt, 1000)
            counts = {table: db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] for table in ('intents', 'fills', 'incidents')}
            orders = []
            for row in db.execute('SELECT i.security_id,i.side,i.quantity,i.price,i.state,i.created_at,o.state AS broker_state FROM intents i LEFT JOIN orders o ON o.intent_id=i.intent_id ORDER BY i.created_at DESC LIMIT 100'):
                orders.append({'security_id': label(row['security_id']), 'side': row['side'] if row['side'] in {'BUY','SELL'} else None,
                               'quantity': integer(row['quantity']), 'price': money(row['price']),
                               'state': row['broker_state'] if row['broker_state'] in ORDER_STATES else (row['state'] if row['state'] in ORDER_STATES else 'UNKNOWN'),
                               'occurred_at': timestamp(row['created_at'])})
            fills = [{'security_id': label(r['security_id']), 'quantity': integer(r['quantity']), 'price': money(r['price']),
                      'fees': money(r['fees']), 'occurred_at': timestamp(r['occurred_at'])}
                     for r in db.execute('SELECT security_id,quantity,price,fees,occurred_at FROM fills ORDER BY occurred_at DESC LIMIT 100')]
            # Arbitrary incident payloads can contain credentials; never export them.
            incidents = [{'kind': 'Runtime incident', 'occurred_at': timestamp(r['created_at'])}
                         for r in db.execute('SELECT created_at FROM incidents ORDER BY created_at DESC LIMIT 30')]
            decision = db.execute("SELECT o.received_at,o.payload FROM intents i JOIN observations o ON o.identity='decision:'||i.intent_id ORDER BY i.created_at DESC LIMIT 1").fetchone()
            entry = None
            if decision and len(decision['payload']) <= 100_000:
                try:
                    raw = json.loads(decision['payload'])
                    inst = raw['book']['instrument']
                    entry = {'occurred_at': timestamp(decision['received_at']),
                             'strategy':choice(raw.get('strategy', 'CAS_LAG_V1'), STRATEGY_NAMES),
                             'security_id': label(inst.get('security_id')),
                             'strike': money(inst.get('strike')), 'option_type': choice(inst.get('option_type'), {'CE', 'PE'}),
                             'quantity': integer(raw.get('quantity')), 'limit': money(raw.get('limit')),
                             'reference': money((raw.get('reference') or {}).get('value')),
                             'confirmations': len(raw['history']) if isinstance(raw.get('history'), list) else None}
                except (ValueError, KeyError, TypeError, AttributeError):
                    entry = None
            return {'available': True, 'orders': orders, 'fills': fills, 'incidents': incidents, 'counts': counts, 'last_entry': entry}
    except (sqlite3.Error, OSError, ValueError):
        return out


def local_snapshot(state_dir, now=None):
    now = now or utcnow()
    root = Path(state_dir)
    return {'runtime': runtime_view(read_json(root/'status.json'), now),
            'connections': connections_view(read_json(root/'connections.json'), now),
            'ledger': ledger_view(root/'ledger.sqlite3')}
