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

UTC = timezone.utc
STATES = {'DISARMED', 'RECOVERING', 'ARMED_WAITING_SESSION', 'ARMED_WAITING_SIGNAL',
          'ENTRY_HALTED', 'NO_TRADE_DAY', 'SETTLEMENT_PENDING', 'POSITION_OPEN'}
ORDER_STATES = {'PENDING_SEND', 'SEND_UNKNOWN', 'SENT', 'TRANSIT', 'PENDING', 'CLOSED',
                'TRIGGERED', 'REJECTED', 'CANCELLED', 'PART_TRADED', 'TRADED', 'FILLED',
                'EXPIRED', 'ABORTED'}
CHECK_FIELDS = {
    'dhan_auth': ('account_matches', 'derivatives_enabled', 'data_plan'),
    'dhan_account': ('orders', 'positions', 'trades', 'whitelist_resolved'),
    'egress': ('matches_expected',),
    'contract_metadata': ('expiry', 'instruments', 'freeze_quantity'),
    'upstox_feed': ('websocket_connected', 'index_seen', 'protobuf_frames', 'cas_status_seen', 'index_iep_seen'),
    'dhan_market_feed': ('websocket_connected', 'full_packets', 'book_verified'),
    'dhan_order_socket': ('websocket_connected', 'route_verified'),
}
REASONS = {
    'ACCOUNT_FUNDS_UNAVAILABLE': 'The broker cash request failed. New entries are blocked.',
    'RECOVERY_REQUIRED': 'The bot is reconciling broker state before considering entries.',
    'OFFICIAL_INDEX_IEP_UNAVAILABLE': 'Waiting for an official indicative index value.',
    'FOREIGN_CAS_DATE': 'The received auction event belongs to a different session.',
    'INVALID_ORDER_EVENT': 'An order event failed validation.',
    'ROUTE_PROBE': 'The order-route qualification has not completed.',
    'operator_disarmed_new_entries': 'New entries were disabled by the operator.',
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
    timing = freshness(raw.get('observed_at'), now, 15)
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
            'clock_uncertainty_ms': integer(raw.get('clock_uncertainty_ms'))}


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
            return {'available': True, 'orders': orders, 'fills': fills, 'incidents': incidents, 'counts': counts}
    except (sqlite3.Error, OSError, ValueError):
        return out


def local_snapshot(state_dir, now=None):
    now = now or utcnow()
    root = Path(state_dir)
    return {'runtime': runtime_view(read_json(root/'status.json'), now),
            'connections': connections_view(read_json(root/'connections.json'), now),
            'ledger': ledger_view(root/'ledger.sqlite3')}
