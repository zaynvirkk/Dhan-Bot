"""Allowlisted projections of local evidence; never return raw broker payloads."""
from __future__ import annotations

from contextlib import closing
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re
import sqlite3
from urllib.parse import quote
from dhan_cas_bot.telemetry import METRICS, REASONS as TIMING_REASONS
from dhan_cas_bot.session_strategies import STRATEGIES
from dhan_cas_bot.expanded_strategies import SPECS,RULES
from dhan_cas_bot.seconds_strategies import RULES as SECONDS_RULES

UTC = timezone.utc
# The collector can spend 20s reading Dhan, then waits 15s before its next run.
# Allow that normal cycle plus scheduling/network margin, not a 15s flicker.
RUNTIME_TTL_SECONDS = 45
STATES = {'DISARMED', 'RECOVERING', 'ARMED_WAITING_SESSION', 'ARMED_WAITING_SIGNAL',
          'ENTRY_HALTED', 'NO_TRADE_DAY', 'SETTLEMENT_PENDING', 'POSITION_OPEN', 'ENTRY_PENDING', 'EXIT_PENDING',
          'WAITING_EXCHANGE_SESSION', 'RECONCILING_DIRECTIONAL_POSITION'}
STRATEGY_NAMES = set(STRATEGIES)
STRATEGY_REASONS = {
    'INPUTS_NOT_RECEIVED', 'CALENDAR_UNAVAILABLE', 'EXCHANGE_CLOSED', 'CONTRACT_CALENDAR_UNAVAILABLE',
    'EXPIRY_SESSION_OUTSIDE_RESEARCH_SCOPE', 'OUTSIDE_STRATEGY_WINDOW', 'SPECIAL_SESSION_OUTSIDE_RESEARCH_SCOPE',
    'NEXT_SESSION_EXIT_UNAVAILABLE', 'SELLOFF_THRESHOLD_MET', 'SELLOFF_BELOW_THRESHOLD',
    'GAP_FADE_CONFIRMED', 'GAP_FADE_CONDITIONS_NOT_MET', 'COMPLETED_INPUT_MISSING_OR_INVALID',
    'NOT_CONFIGURED', 'STRATEGY_INPUTS_STALE', 'STRATEGY_INPUT_UNAVAILABLE', 'ENTRY_DEADLINE_MISSED',
    'ENTRY_NOT_PERMITTED', 'OPTION_MINUTES_UNAVAILABLE', 'OPTION_BOOK_UNAVAILABLE_OR_STALE',
    'FIXED_LIMIT_ALREADY_MISSED', 'NO_AFFORDABLE_LIQUID_CONTRACT', 'UNMANAGED_ACCOUNT_POSITION',
    'CONFLICTING_UNRANKED_SIGNALS','NO_POSITIVE_ESTIMATED_EDGE',
}
STRATEGY_REASONS.update({'EXPANDED_RULE_CONFIRMED','EXPANDED_RULE_NOT_MET','REQUIRES_EXPIRY_SESSION',
    'FUNDED_STRATEGY_DISABLED',
    'MISSING_COMPLETED_BAR','MISSING_OHLC_RANGE','MISSING_VWAP_INPUTS','ZERO_FUTURE_VOLUME','ZERO_VOLUME_BASE',
    'MISSING_FUTURE_OI','MISSING_SAME_STRIKE_OPTION','MISSING_CHAIN_NEIGHBOURS','MISSING_CHAIN_OI',
    'MISSING_OPTION_OI','INVALID_OPEN_REFERENCE','SOURCE_NOT_YET_AVAILABLE','MISSING_CURRENT_IV',
    'MISSING_PCR_INSIGHT','MISSING_MAX_PAIN_INSIGHT','MISSING_PRIOR_WALL','ZERO_PRIOR_WALL_OI','MISSING_PRIOR_OPTION_OI',
    'MISSING_IV','MISSING_INSIGHTS','MISSING_PRIOR_CHAIN','MISSING_INSTITUTIONS','MISSING_PRIOR_TREND'})
STRATEGY_REASONS.update({'SECONDS_SETUP_DETECTED','SECONDS_WARMUP','SECONDS_RULE_NOT_MET',
    'SECONDS_EDGE_BELOW_COSTS','SECONDS_SIGNAL_CHANGED','FUTURES_FEED_UNAVAILABLE',
    'EVENT_FEED_UNAVAILABLE','NO_FRESH_EVENT','OPTIONS_FEED_UNAVAILABLE',
    'SECONDS_SIGNAL_EXPIRED','SECONDS_OPTION_IDENTITY_MISMATCH','SECONDS_SPREAD_TOO_WIDE',
    'SECONDS_DEPTH_TOO_THIN','SECONDS_ENTRY_OUTSIDE_BAND','SECONDS_TARGET_UNAVAILABLE',
    'SECONDS_UNAFFORDABLE','SECONDS_NET_EDGE_TOO_SMALL'})
SHOCK_REASONS={'SHOCK_CONFIRMED','SHOCK_RULE_NOT_MET','SHOCK_COMPLETED_BAR_UNAVAILABLE',
    'SHOCK_WARMUP','SHOCK_NONCONTIGUOUS_BARS','SHOCK_INVALID_BAR','SHOCK_BASELINE_UNAVAILABLE',
    'SHOCK_VOLUME_UNAVAILABLE','SHOCK_COOLDOWN','SHOCK_BAR_CONFLICT','SHOCK_RECONNECT_INVALIDATED',
    'SHOCK_INVALID_BOOK','SHOCK_SPREAD_TOO_WIDE','SHOCK_EXPIRY_CUTOFF','SHOCK_IV_UNAVAILABLE',
    'SHOCK_SCENARIO_BELOW_FLOOR'}
STRATEGY_REASONS.update(SHOCK_REASONS)
SHOCK_EXITS={'SHOCK_UNDERLYING_INVALIDATED','SHOCK_PREMIUM_STOP','SHOCK_PROFIT_FLOOR',
    'SHOCK_NO_MOMENTUM','SHOCK_MAX_EXPOSURE'}
REASONS_SHOCK={'SHOCK_UNDERLYING_INVALIDATED':'The underlying move reversed through its recorded invalidation rule.',
    'SHOCK_PREMIUM_STOP':'Executable liquidation reached the 40% entry-cash loss trigger.',
    'SHOCK_PROFIT_FLOOR':'Executable profit fell below the saved shock profit floor.',
    'SHOCK_NO_MOMENTUM':'The position passed 45 minutes without the required observed gain.',
    'SHOCK_MAX_EXPOSURE':'The position reached its maximum holding time or session exit deadline.'}
ORDER_STATES = {'PENDING_SEND', 'SEND_UNKNOWN', 'SENT', 'TRANSIT', 'PENDING', 'CLOSED',
                'TRIGGERED', 'REJECTED', 'CANCELLED', 'PART_TRADED', 'TRADED', 'FILLED',
                'EXPIRED', 'ABORTED'}
CHECK_FIELDS = {
    'dhan_auth': ('account_matches', 'derivatives_enabled', 'data_plan'),
    'dhan_account': ('orders', 'positions', 'open_positions', 'trades', 'whitelist_resolved'),
    'egress': ('matches_expected',),
    'contract_metadata': ('expiry', 'instruments', 'freeze_quantity'),
    'upstox_feed': ('websocket_connected', 'index_seen', 'protobuf_frames', 'cas_status_seen', 'index_iep_seen', 'close_received_code', 'close_sent_code', 'keepalive_timeout'),
    'dhan_market_feed': ('websocket_connected', 'full_packets', 'book_verified', 'close_received_code', 'close_sent_code', 'keepalive_timeout'),
    'dhan_order_socket': ('websocket_connected', 'route_verified', 'close_received_code', 'close_sent_code', 'keepalive_timeout'),
}
REASONS = {
    'ACCOUNT_REFRESH_REQUIRED':'Waiting for a fresh reconciled broker account before new entries.',
    'POSITION_CLOSED':'The strategy position is closed. Monitoring for another qualifying setup.',
    'ENTRY_CANCELLED_NO_FILL':'The strategy entry finished without a fill. No position was opened.',
    'SECONDS_PREMIUM_STOP':'The seconds strategy hit its quote-based premium stop.',
    'SECONDS_TARGET_REPRICED':'The option reached the recorded repricing reference.',
    'SECONDS_INPUT_LOST':'Fresh futures input was lost; the seconds strategy is reducing its position.',
    'SECONDS_DIRECTION_FAILED':'Futures moved against the seconds strategy; the bot is reducing its position.',
    'NO_EXECUTABLE_LAG_OR_REMAINING_ALLOWANCE': 'No contract passes the price, depth, fees and remaining capital checks.',
    'UNMANAGED_ACCOUNT_POSITION': 'An account position is not managed by this bot. New entries are blocked.',
    'CAS_LAG_V1': 'An auction-lag entry was submitted. Waiting for broker execution updates.',
    'FINAL_RESIDUAL': 'A confirmed-final-value entry was submitted. Waiting for broker execution updates.',
    'DIRECTION_REVERSAL': 'The auction direction reversed. The bot is reducing its position.',
    'CONTRACT_LAG_INVALIDATED': 'The contract lost its qualifying price discrepancy. The bot is reducing its position.',
    'LAG_CONVERGED': 'The option price caught up with the auction value. The bot is reducing its position.',
    'JOINT_REVERSAL': 'Both intrinsic value and bid reversed. The bot is reducing its position.',
    'TIME_EXIT': 'The exit deadline was reached. The bot is reducing its position.',
    'NET_PROFIT_FLOOR': 'Executable net profit fell through its recorded profit floor. The bot is reducing the position.',
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


REASONS.update(REASONS_SHOCK)
REASONS['ROUTE_OUTCOME_UNKNOWN']='The route-check request has no confirmed broker outcome. New entries are blocked while reconciliation continues.'


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
              'official_cas_signal_seen', 'final_value_source_verified', 'auto_live_armed', 'writes', 'account_snapshot_fresh','exchange_session_open')}
    parts = str(raw.get('reason', '')).split(':')
    prefix = parts[0]
    reason=REASONS.get(parts[-1]) if prefix in STRATEGY_NAMES and len(parts)>1 else None
    if prefix in STRATEGY_NAMES and parts[-1]=='HOLDING':reason='The bot is holding this strategy position and checking its recorded profit, loss and session exit rules.'
    return {**timing, **flags, 'authority': authority,
            'route_attempts_used': integer(raw.get('route_attempts_used')),
            'route_attempt_limit': integer(raw.get('route_attempt_limit')),
            'state': choice(raw.get('state'), STATES, 'UNKNOWN'),
            'reason': reason or REASONS.get(prefix, 'No specific decision reason was recorded.'),
            'session': timestamp(str(raw.get('session', '')) + 'T00:00:00+05:30'),
            'books_observed': integer(raw.get('books_observed')),
            'contract_count': integer(raw.get('contract_count')),
            'market_subscription_count':integer(raw.get('market_subscription_count')),
            'market_subscription_target_count':integer(raw.get('market_subscription_target_count')),
            'market_subscription_error':choice(raw.get('market_subscription_error'),{'TimeoutError','OSError','ConnectionClosedError','ConnectionClosedOK'}),
            'clock_uncertainty_ms': integer(raw.get('clock_uncertainty_ms')),
            'monitoring_mode': choice(raw.get('monitoring_mode'), {'IDLE', 'ACTIVE'}, 'UNKNOWN'),
            'strategies': [s for s in raw.get('strategies', []) if isinstance(s, str) and s in STRATEGY_NAMES] if isinstance(raw.get('strategies'), list) else [],
            'funded_strategies': [s for s in raw['funded_strategies'] if isinstance(s,str) and s in STRATEGY_NAMES] if isinstance(raw.get('funded_strategies'),list) else None,
            'strategy_evaluations': strategy_projection(raw.get('strategy_evaluations')),
            'input_health':input_health_projection(raw.get('input_health'),now),
            'future_input':future_input_view(raw.get('future_input')),
            'replay_capture':capture_view(raw.get('replay_capture')),
            'strategy_selection':selection_projection(raw.get('strategy_selection')),
            'execution_feedback':execution_feedback_projection(raw.get('execution_feedback')),
            'minute_source':choice(raw.get('minute_source'),{'UPSTOX_COMPLETED_I1_STREAM','REST_BOOTSTRAP_OR_GAP_REPAIR','NOT_OBSERVED'}),
            'expiry_today': raw.get('expiry_today') if type(raw.get('expiry_today')) is bool else None,
            'calendar_checked_at': timestamp(raw.get('calendar_checked_at')),
            'feed_health': feed_health_view(raw.get('feed_health')),
            'runtime_revision':integer(raw.get('runtime_revision')),
            'source_commit':raw.get('source_commit') if re.fullmatch('[0-9a-f]{40}',str(raw.get('source_commit',''))) else None,
            'recorder_pending': integer(raw.get('recorder_pending')),
            'recorder_failed':raw.get('recorder_failed') if type(raw.get('recorder_failed')) is bool else None,
            'telemetry': telemetry_view(raw.get('telemetry')),
            'observation': observation_projection(raw.get('observation'))}


def future_input_view(raw):
    if not isinstance(raw,dict):return None
    return {'connected':raw.get('connected') is True,'current':raw.get('current') is True,
        'age_ms':money(raw.get('age_ms')),'maximum_age_ms':integer(raw.get('maximum_age_ms')),
        'reason':choice(raw.get('reason'),{'CURRENT','FUTURES_STALE','FUTURES_DISCONNECTED','FUTURES_WARMUP','FUTURES_PACKET_REJECTED'},'UNKNOWN')}


def capture_view(raw):
    if not isinstance(raw,dict):return None
    return {'state':choice(raw.get('state'),{'WAITING','RECORDING','CAP_REACHED','DISK_RESERVE','QUEUE_OVERFLOW','WRITE_FAILED'},'UNKNOWN'),
        'observed_at':timestamp(raw.get('observed_at')),
        **{k:integer(raw.get(k)) for k in ('receipts','compressed_bytes','pending')}}


def input_health_projection(raw,now):
    if not isinstance(raw,dict):return None
    result={**freshness(raw.get('observed_at'),now,90),'decision_bar_at':timestamp(raw.get('decision_bar_at'))}
    safe_error=lambda v:v if isinstance(v,str) and re.fullmatch('[A-Za-z][A-Za-z0-9_]{0,48}',v) else 'UNKNOWN' if v else None
    for name in ('spot','future'):
        row=raw.get(name) or {}
        if not isinstance(row,dict):row={}
        result[name]={'rows':integer(row.get('rows')),'missing_minutes':integer(row.get('missing_minutes')),
            'latest_completed':timestamp(row.get('latest_completed')),'first_missing':timestamp(row.get('first_missing')),
            'current_complete':row.get('current_complete') if type(row.get('current_complete')) is bool else None,
            'error':safe_error(row.get('error'))}
    row=raw.get('options') or {}
    result['options']={k:integer(row.get(k)) for k in ('requested','ready','loaded','failed')} if isinstance(row,dict) else {}
    row=raw.get('auxiliary') or {}
    result['auxiliary']={'running':row.get('running') if type(row.get('running')) is bool else None,
        'received_at':timestamp(row.get('received_at')),'error':safe_error(row.get('error'))} if isinstance(row,dict) else {}
    result['error']=safe_error(raw.get('error'))
    return result


def selection_projection(raw):
    if not isinstance(raw,dict):return None
    rows=[]
    for row in raw.get('candidates',[])[:256] if isinstance(raw.get('candidates'),list) else []:
        if not isinstance(row,dict) or row.get('strategy') not in STRATEGY_NAMES:continue
        numeric={k:(money(row.get(k)) if k in ('limit','friction_cash','incremental_friction_cash','estimated_net_profit','estimated_profit_per_minute')
                    else str(Decimal(str(row[k]))) if money(row.get(k)) is not None else None) for k in
                 ('limit','friction_cash','incremental_friction_cash','estimated_net_profit','estimated_profit_per_minute','holding_minutes','scoring_minutes','return_standard_error','entry_fill_rate','mean_entry_fill_fraction')}
        rows.append({**numeric,'strategy':row['strategy'],'side':choice(row.get('side'),{'CE','PE'}),
                     'quantity':integer(row.get('quantity')),'filled_closed':integer(row.get('filled_closed')),
                     'cost_basis':choice(row.get('cost_basis'),{'PRIOR_FILLED_ORDERS','CONSERVATIVE_FALLBACK'}),
                     'estimated_buy_orders':integer(row.get('estimated_buy_orders')),
                     'estimated_sell_orders':integer(row.get('estimated_sell_orders')),
                     'sessions':integer(row.get('sessions')),
                     'closed_entry_opportunities':integer(row.get('closed_entry_opportunities')),
                     'filled_entry_opportunities':integer(row.get('filled_entry_opportunities'))})
    return {'evaluated_at':timestamp(raw.get('evaluated_at')),
            'mode':choice(raw.get('mode'),{'WAITING','MEASURED_CASH_PER_MINUTE','EXPERIMENTAL_EXECUTION_QUALITY','QUALIFIED_AUCTION','DECLARED_CONTINUATION_SCENARIO'},'WAITING'),
            'reason':choice(raw.get('reason'),{'SELECTED','CONFLICTING_UNRANKED_SIGNALS','NO_POSITIVE_ESTIMATED_EDGE','NO_EXECUTABLE_SIGNAL','SCENARIO_ONLY_NOT_EXPECTED_RETURN'},'NO_EXECUTABLE_SIGNAL'),
            'scenario_multiple':money(raw.get('scenario_multiple')),
            'entry_cash':money(raw.get('entry_cash')),'budget':money(raw.get('budget')),
            'selected':choice(raw.get('selected'),STRATEGY_NAMES),'candidates':rows}


def execution_feedback_projection(raw):
    if not isinstance(raw,dict):return []
    result=[]
    for name,row in list(raw.items())[:256]:
        if name not in STRATEGY_NAMES or not isinstance(row,dict):continue
        numeric={key:str(Decimal(str(row[key]))) if money(row.get(key)) is not None else None for key in
                 ('entry_fill_rate','mean_entry_fill_fraction','mean_estimated_net_return','return_standard_error')}
        for key in ('entry_fill_rate','mean_entry_fill_fraction'):
            if numeric[key] is not None and not 0<=Decimal(numeric[key])<=1:numeric[key]=None
        result.append({'strategy':name,**numeric,**{key:integer(row.get(key)) for key in
                      ('filled_closed','sessions','closed_entry_opportunities','filled_entry_opportunities')}})
    return result


def condition_projection(raw):
    result=[]
    allowed={'gap_size','gap_fill','persistence','futures_direction','selloff',
             'shock_size','shock_abnormal','extension','future_direction','volume_ratio'}
    for row in raw[:10] if isinstance(raw,list) else []:
        if not isinstance(row,dict) or row.get('key') not in allowed:
            continue
        clean={'key':row['key'],'state':choice(row.get('state'),{'PASS','FAIL','UNKNOWN'},'UNKNOWN'),
               **{k:str(Decimal(str(row[k]))) if money(row.get(k)) is not None else None
                  for k in ('value','minimum','maximum')},
               'expected':choice(row.get('expected'),{'RISING','FALLING'})}
        if clean['key']!='persistence' and clean['value'] is None:
            clean['state']='UNKNOWN'
        result.append(clean)
    return result


def strategy_projection(raw):
    result=[]
    for row in raw[:256] if isinstance(raw, list) else []:
        if not isinstance(row, dict) or choice(row.get('strategy'), STRATEGY_NAMES) is None:
            continue
        details={}
        for key in ('gap', 'fraction_filled', 'future_5m_return', 'open_return','spot_15m','future_15m',
                    'future_vwap','future_oi_5m','future_5m','basis_change','bank_15m','it_15m','gift_15m',
                    'trend_30m','pullback_10m','move_15m','volume_ratio','opening_high','opening_low',
                    'compressed_high','compressed_low','compression_high','compression_low','box_high','box_low',
                    'efficiency','first_half_hour_return','premium_return','premium_return_3m','oi_change','own_oi',
                    'opposite_oi','opposite_return','strike','anchor_spot','prior_oi_wall','iv','realized_vol_30m',
                    'vix_15m','pcr_change_5m','pcr_change','known_max_pain','fii_net_change','dii_net','prior_trend_20d',
                    'warmup_seconds','future_move_2s','response_beta','target_price','impulse_threshold',
                    'eligible_contracts','fitted_contracts','breakout_direction','flow_candidates','curvature_candidates',
                    'spread_ratio','bid_quantity','ask_quantity','required_depth','entry_cash','exit_fee_reserve',
                    'cash_budget','net_at_target','minimum_net_edge','spot_5m','prior_abs_r5',
                    'pre_break_high','pre_break_low','breakout_boundary','extension','baseline_comparisons','volume_windows'):
            value=(row.get('details') or {}).get(key) if isinstance(row.get('details'), dict) else None
            if money(value) is not None:
                details[key]=money(value) if key=='target_price' else str(Decimal(str(value)))
        if isinstance(row.get('details'),dict) and type(row['details'].get('persistent')) is bool:
            details['persistent']=row['details']['persistent']
        spec=SPECS.get(row['strategy'])
        result.append({'strategy':row['strategy'],
            'family':spec[0] if spec else 'GAP_FADE' if row['strategy']=='GAP_FADE_DOUBLE' else row['strategy'],
            'scope':spec[2] if spec else 'ORDINARY' if row['strategy']=='GAP_FADE_DOUBLE' else 'ANY',
            'exit_policy':'SHOCK_EXIT_V1' if row['strategy']=='VOLATILITY_SHOCK_V1' else spec[1] if spec else 'SECONDS_V1' if row['strategy'] in SECONDS_RULES else 'DOUBLE',
            'entry_rule':'Completed 5-minute shock, persistent range breakout, futures direction and volume; live-book affordability and scenario ranking.' if row['strategy']=='VOLATILITY_SHOCK_V1' else RULES.get(spec[0]) if spec else SECONDS_RULES.get(row['strategy']),
            'filled_closed':integer(row.get('filled_closed')),
            'ranking_available':row.get('ranking_available') if type(row.get('ranking_available')) is bool else False,
            'mean_estimated_net_return':str(Decimal(str(row['mean_estimated_net_return']))) if money(row.get('mean_estimated_net_return')) is not None else None,
            'enabled':row.get('enabled') if type(row.get('enabled')) is bool else None,
            'funded_enabled':row.get('funded_enabled') if type(row.get('funded_enabled')) is bool else None,
            'state':choice(row.get('state'), {'UNKNOWN','INPUT_UNAVAILABLE','WAITING','SIGNAL','NO_SIGNAL','NOT_APPLICABLE','DISABLED'},'UNKNOWN'),
            'reason':choice(str(row.get('reason','')).split(':')[0],STRATEGY_REASONS,'UNKNOWN'),
            'evaluated_at':timestamp(row.get('evaluated_at')), 'side':choice(row.get('side'), {'CE','PE'}),
            'spot':money(row.get('spot')), 'exit_at':timestamp(row.get('exit_at')), 'details':details,
            'conditions':condition_projection(row.get('conditions')), 'next_check_at':timestamp(row.get('next_check_at')),
            'bar_at':timestamp((row.get('details') or {}).get('bar_at')),
            'source_received_at':timestamp((row.get('details') or {}).get('source_received_at')),
            'shock_candidates':shock_candidate_projection(row.get('shock_candidates')),
            'candidate_assessed_at':timestamp(row.get('candidate_assessed_at')),
            'last_execution_reason':choice(str(row.get('last_execution_reason','')).split(':')[0],STRATEGY_REASONS),
            'execution_blocking_reason':choice(str(row.get('execution_blocking_reason','')).split(':')[0],STRATEGY_REASONS)})
    return result


def shock_candidate_projection(raw):
    result=[]
    for row in raw[:60] if isinstance(raw,list) else []:
        if not isinstance(row,dict):continue
        try:expiry=date.fromisoformat(row['expiry']).isoformat()
        except (KeyError,TypeError,ValueError):expiry=None
        result.append({'security_id':label(row.get('security_id')),'expiry':expiry,
            'reason':choice(row.get('reason'),STRATEGY_REASONS|{'READY','OPTION_LIMIT_OUTSIDE_BAND'},'UNKNOWN'),
            **{k:money(row.get(k)) for k in ('strike','budget','limit','entry_cash','exit_fee_reserve','scenario_multiple')},
            'quantity':integer(row.get('quantity')),'scenario_only':True})
    return result


def daily_monitor_view(raw, now):
    if not isinstance(raw, dict) or raw.get('mode') != 'READ_ONLY' or raw.get('writes_to_broker') is not False:
        return None
    timing = freshness(raw.get('observed_at'), now, 90)
    rows = strategy_projection(raw.get('strategy_evaluations'))
    if not timing['fresh']:
        rows = [{**r, 'state':'UNKNOWN', 'reason':'STRATEGY_INPUTS_STALE', 'side':None,
                 'conditions':[{**c,'state':'UNKNOWN'} for c in r.get('conditions',[])]} for r in rows]
    return {**timing, 'mode':'READ_ONLY', 'writes_to_broker':False,
            'strategies':['GAP_FADE_DOUBLE','NIFTY_SELLOFF_REBOUND_1510'],
            'strategy_evaluations':rows, 'last_decisions':strategy_projection(raw.get('last_decisions')),
            'calendar_checked_at':timestamp(raw.get('calendar_checked_at')),
            'session_open':timestamp(raw.get('session_open')), 'session_close':timestamp(raw.get('session_close')),
            'exchange_open':raw.get('exchange_open') if type(raw.get('exchange_open')) is bool else None,
            'spot_at':timestamp(raw.get('spot_at')),
            **{key:money(raw.get(key)) for key in ('spot','opening','previous_close')},
            **{key:integer(raw.get(key)) for key in ('spot_bars','future_bars')}}


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


def transport_event_view(raw):
    if not isinstance(raw,list):return []
    result=[]
    for row in raw[-16:]:
        if not isinstance(row,dict) or row.get('kind') not in {'CONNECTED','DISCONNECTED','ERROR'}:continue
        result.append({'kind':row['kind'],'at':timestamp(row.get('at')),
            'error_type':choice(row.get('error_type'),{'ContractError','OSError','EOFError','TimeoutError',
                'ConnectionClosedError','ConnectionClosedOK','InvalidHandshake','HTTPStatusError','DhanFeedDisconnect'}),
            **{k:integer(row.get(k)) for k in ('attempt','close_received_code','close_sent_code','provider_disconnect_code')},
            'keepalive_timeout':row.get('keepalive_timeout') if type(row.get('keepalive_timeout')) is bool else None})
    return result


def feed_health_view(raw):
    raw = raw if isinstance(raw, dict) else {}
    result = {}
    for name in ('signal', 'market', 'order', 'future'):
        item = raw.get(name)
        if not isinstance(item, dict):
            continue
        result[name] = {'connected': item.get('connected') if type(item.get('connected')) is bool else None,
                        **{key: timestamp(item.get(key)) for key in ('last_received_at', 'last_processed_at', 'last_usable_at')},
                        **{key: integer(item.get(key)) for key in ('reconnects', 'pending_messages', 'queue_high_water', 'processed_messages')},
                        **{key: money(item.get(key)) for key in ('oldest_pending_ms', 'queue_delay_ms', 'processing_ms')},
                        'last_error': choice(item.get('last_error'), {'ContractError', 'OSError', 'EOFError', 'TimeoutError', 'ConnectionClosedError', 'InvalidHandshake', 'InvalidMessage', 'HTTPStatusError'}),
                        'transport_events':transport_event_view(item.get('transport_events'))}
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
        'state': choice(row.get('state'), ORDER_STATES, 'UNKNOWN'),
        'purpose':choice(row.get('purpose'),{'ROUTE_CHECK','STRATEGY_ORDER'},'UNKNOWN')
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
            elif field == 'data_plan': facts[field] = choice('Inactive' if v == 'Deactive' else v, {'Active', 'Inactive', 'Expired'}, 'UNKNOWN')
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


def order_purposes(db):
    """Private ID lookup for projection only. Never serialize this mapping."""
    return {r[0]:('ROUTE_CHECK' if r[1]=='route-probe' else 'STRATEGY_ORDER') for r in
        db.execute("SELECT o.order_id,i.lifecycle_id FROM orders o JOIN intents i ON i.intent_id=o.intent_id ORDER BY i.created_at DESC LIMIT 100")}


def broker_order_view(row, purpose=None):
    return {'symbol': label(row.get('tradingSymbol')), 'security_id': label(str(row.get('securityId', ''))),
            'side': choice(row.get('transactionType'), {'BUY', 'SELL'}),
            'state': choice(row.get('orderStatus'), ORDER_STATES, 'UNKNOWN'),
            'quantity': integer(row.get('quantity')), 'filled_quantity': integer(row.get('filledQty', row.get('filledQuantity'))),
            'price': money(row.get('price')), 'purpose':choice(purpose,{'ROUTE_CHECK','STRATEGY_ORDER'},'UNKNOWN')}


def account_view(funds, positions, orders, now, *, purposes=None):
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
            'order_count': len(orders), 'orders': [broker_order_view(o,(purposes or {}).get(str(o.get('orderId','')))) for o in orders[-100:]][::-1],
            'positions_truncated': len(open_positions) > 100, 'orders_truncated': len(orders) > 100}


def last_signal_views(db):
    """Historical qualifying signals, with only recorded execution outcomes."""
    if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='metadata'").fetchone():
        return []
    def metadata(key):
        row=db.execute('SELECT value FROM metadata WHERE key=?',(key,)).fetchone()
        try:
            value=json.loads(row['value']) if row and len(row['value'])<=100_000 else {}
            return value if isinstance(value,dict) else {}
        except (ValueError,TypeError):
            return {}
    check_reasons=STRATEGY_REASONS|{'READY','ONE_LOT_UNAFFORDABLE','OPTION_LIQUIDITY_BELOW_POLICY',
        'OPTION_LIMIT_OUTSIDE_BAND','OPTION_DEPTH_BELOW_ONE_LOT'}
    result=[]
    seen=set()
    for record in db.execute("SELECT key,value FROM metadata WHERE key LIKE 'directional-signal:%' AND key NOT LIKE '%:assessment' AND key NOT LIKE '%:consumed' ORDER BY key DESC LIMIT 512"):
        match=re.fullmatch(r'directional-signal:(\d{4}-\d{2}-\d{2}):([A-Z0-9_]{1,96})(?::[a-zA-Z0-9_-]{1,96})?',record['key'])
        if not match or match[2] not in STRATEGY_NAMES or match[2] in seen or len(record['value'])>100_000:
            continue
        try:
            raw=json.loads(record['value'])
            if not isinstance(raw,dict) or raw.get('strategy')!=match[2] or raw.get('state')!='SIGNAL':
                continue
            stamp=timestamp(raw.get('evaluated_at'))
            side=choice(raw.get('side'),{'CE','PE'})
            if stamp is None or side is None:
                continue
            consumed=metadata(record['key']+':consumed')
            assessment=metadata(record['key']+':assessment')
            checks=consumed.get('candidate_checks',assessment.get('candidate_checks',[]))
            projected=[]
            for item in checks[:5] if isinstance(checks,list) else []:
                if not isinstance(item,dict):
                    continue
                projected.append({'security_id':label(item.get('security_id')),
                    'reason':choice(item.get('reason'),check_reasons,'UNKNOWN'),
                    **{field:money(item.get(field)) for field in ('strike','budget','limit','one_lot_cash')},
                    **{field:integer(item.get(field)) for field in ('lot_size','minute_volume','open_interest','quantity')}})
            result.append({'strategy':match[2],'evaluated_at':stamp,'side':side,
                'outcome':choice(consumed.get('reason'),{'ENTRY_DEADLINE_MISSED','DECISION_COMMITTED','PRIOR_REBOUND_EXITED_TODAY'},'UNKNOWN'),
                'blocking_reason':choice(consumed.get('blocking_reason',assessment.get('reason')),STRATEGY_REASONS,'UNKNOWN'),
                'candidate_checks':projected})
            seen.add(match[2])
        except (ValueError,TypeError,AttributeError):
            continue
    return result


def cash_reconciliation(db):
    """Reported order charges are separate from individual execution fills."""
    records=list(db.execute("SELECT f.order_id,f.intent_id,f.quantity,f.price,f.occurred_at,i.side,i.lifecycle_id FROM fills f JOIN intents i ON i.intent_id=f.intent_id WHERE i.lifecycle_id IN (SELECT lifecycle_id FROM lifecycles WHERE state='CLOSED' ORDER BY rowid DESC LIMIT 256) LIMIT 100001"))
    if not records or len(records)>100000:return None
    quantities={}
    for r in records:
        quantities[r['lifecycle_id']]=quantities.get(r['lifecycle_id'],0)+(r['quantity'] if r['side']=='BUY' else -r['quantity'])
    records=[r for r in records if quantities[r['lifecycle_id']]==0]
    if not records:return None
    buy=sell=Decimal(0)
    for row in records:
        if money(row['price']) is None or row['quantity']<=0:return {'status':'UNAVAILABLE'}
        amount=Decimal(row['price'])*row['quantity']
        if row['side']=='BUY':buy+=amount
        elif row['side']=='SELL':sell+=amount
        else:return {'status':'UNAVAILABLE'}
    order_ids={r['order_id'] for r in records};confirmed={};charges=Decimal(0)
    if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='order_charges'").fetchone():
        for row in db.execute('SELECT order_id,fees,complete FROM order_charges'):
            if row['order_id'] not in order_ids:continue
            if money(row['fees']) is None or Decimal(row['fees'])<0:return {'status':'UNAVAILABLE'}
            charges+=Decimal(row['fees'])
            if row['complete']==1:confirmed[row['order_id']]=True
    complete=len(confirmed)==len(order_ids)
    return {'status':'REPORTED_CHARGES_COMPLETE' if complete else 'CHARGES_PENDING',
        'scope':'RECENT_CLOSED_BOT_TRADES','last_trade_at':max(timestamp(r['occurred_at']) or '' for r in records),
        'closed_trades':len({r['lifecycle_id'] for r in records}),'executed_orders':len(order_ids),
        'orders_with_complete_charges':len(confirmed),'gross_pnl':money(sell-buy),
        'reported_charges':money(charges) if complete else None,
        'net_after_reported_charges':money(sell-buy-charges) if complete else None}


def active_trade_views(db):
    """Recorded policy and actual fills, never a claim about a current stop quote."""
    result=[]
    for row in db.execute("SELECT lifecycle_id,security_id,payload FROM lifecycles WHERE state!='CLOSED' ORDER BY rowid DESC LIMIT 8"):
        try:
            if len(row['payload'])>100_000:continue
            payload=json.loads(row['payload']);policy=payload.get('signal',{}).get('details',{})
            strategy=choice(payload.get('strategy'),STRATEGY_NAMES)
            if strategy is None or not isinstance(policy,dict):continue
            fills=list(db.execute('SELECT i.side,f.quantity,f.price FROM fills f JOIN intents i ON i.intent_id=f.intent_id WHERE i.lifecycle_id=?',(row['lifecycle_id'],)))
            buys=[f for f in fills if f['side']=='BUY'];units=sum(f['quantity'] for f in buys)
            quantity=sum(f['quantity']*(1 if f['side']=='BUY' else -1) for f in fills)
            entry=sum((Decimal(f['price'])*f['quantity'] for f in buys),Decimal(0))/units if units else None
            latch=db.execute('SELECT value FROM metadata WHERE key=?',('directional-exit:'+row['lifecycle_id'],)).fetchone()
            trigger=json.loads(latch['value']) if latch else {}
            protection=payload.get('profit_exit') or {}
            guard_row=db.execute('SELECT value FROM metadata WHERE key=?',('profit-exit:'+row['lifecycle_id'],)).fetchone()
            guard=json.loads(guard_row['value']) if guard_row else {}
            net_protection=None
            if protection.get('version')=='NET_PROFIT_RATCHET_V1':
                net_protection={'version':'NET_PROFIT_RATCHET_V1','retain':money(protection.get('retain')),
                    'peak':money(guard.get('peak')),'floor':money(guard.get('floor')),
                    'triggered':guard.get('triggered') is True}
            shock=None
            if strategy=='VOLATILITY_SHOCK_V1':
                saved=db.execute('SELECT value FROM metadata WHERE key=?',('shock-exit:'+row['lifecycle_id'],)).fetchone()
                observed=json.loads(saved['value']) if saved else {}
                shock={**{k:money(observed.get(k)) for k in ('entry_cash','actual_average_entry','peak_net_profit','minimum_net_profit','floor','net_liquidation_profit')},
                    'observed_at':timestamp(observed.get('observed_at')),'first_fill_at':timestamp(observed.get('first_fill_at')),
                    'trailing_armed':observed.get('trailing_armed') is True,'quote_executable':observed.get('quote_executable') is True}
            result.append({'strategy':strategy,'security_id':label(row['security_id']),
                'quantity':integer(quantity),'entry_price':money(entry),
                'trailing':policy.get('exit_trail') is True,'stop_fraction':money(policy.get('exit_stop')),
                'target_known':'exit_target' in policy,'target_multiple':money(policy.get('exit_target')),
                'exit_due':timestamp(payload.get('exit_at')),
                'exit_trigger':choice(trigger.get('reason'),{'TIME_EXIT','PREMIUM_TARGET','TRAILING_STOP','PREMIUM_STOP','NET_PROFIT_FLOOR'}|SHOCK_EXITS),
                'trigger_due':timestamp(trigger.get('due')),'net_protection':net_protection,'shock':shock})
        except (ValueError,TypeError,KeyError,AttributeError,InvalidOperation):continue
    return result


def recorded_decisions(db, strategies, now, session_bounds=None):
    """Today's allowlisted decision receipts, using indexed identity ranges.

    A waiting-minute snapshot must not erase a completed check on page reload.
    These are observations, not evidence that an order would have filled.
    """
    from zoneinfo import ZoneInfo
    ist = ZoneInfo('Asia/Kolkata')
    day = now.astimezone(ist).date().isoformat()
    result = []
    for name in dict.fromkeys(s for s in strategies[:256] if s in STRATEGY_NAMES):
        prefix = f'strategy-evaluation:{name}:{day}'
        query=("SELECT received_at,payload,identity FROM observations WHERE identity>=? AND identity<? "
            "AND kind='STRATEGY_EVALUATION' AND identity NOT LIKE '%:WAITING' "
            "AND identity NOT LIKE '%:NOT_APPLICABLE' AND identity NOT LIKE '%:DISABLED' ")
        if name in SECONDS_RULES and session_bounds:
            # Seconds identities use the evaluation's timezone. Query UTC and
            # IST separately so after-close warnings cannot consume the limit.
            rows=[]
            for zone in (UTC,ist):
                start,end=(v.astimezone(zone) for v in session_bounds)
                offset=start.isoformat()[-6:]
                rows.extend(db.execute(query+"AND identity LIKE ? ORDER BY identity DESC LIMIT 257",
                    (f'strategy-evaluation:{name}:'+start.isoformat(),
                     f'strategy-evaluation:{name}:'+end.isoformat(),'%'+offset+':%')))
            rows=sorted(rows,key=lambda r:r['identity'],reverse=True)[:257]
        else:
            rows=list(db.execute(query+"ORDER BY identity DESC LIMIT 257",(prefix,prefix+'\uffff')))
        records = []
        for row in rows[:256]:
            if len(row['payload']) > 100_000:
                continue
            try:
                raw = json.loads(row['payload'])
                clean = strategy_projection([raw])
                received = timestamp(row['received_at'])
                if not clean or clean[0]['strategy'] != name or not received:
                    continue
                sample = clean[0]
                at = timestamp(sample['evaluated_at'])
                if (sample['state'] not in {'SIGNAL', 'NO_SIGNAL', 'UNKNOWN'} or not at
                        or datetime.fromisoformat(at).astimezone(ist).date().isoformat() != day
                        or datetime.fromisoformat(at) > now or datetime.fromisoformat(received) > now):
                    continue
                records.append({**sample, 'received_at': received})
            except (ValueError, TypeError, AttributeError, RecursionError):
                continue
        result.append({'strategy': name, 'truncated': len(rows) > 256,
                       'records': sorted(records, key=lambda r: (r['evaluated_at'], r['received_at']))})
    return {'status': 'AVAILABLE', 'date': day, 'observed_at': now.isoformat(), 'strategies': result}


def recorded_session_bounds(db,now):
    from zoneinfo import ZoneInfo
    day=now.astimezone(ZoneInfo('Asia/Kolkata')).date().isoformat()
    prefix='market-calendar:'+day
    row=db.execute("SELECT payload FROM observations WHERE identity>=? AND identity<? AND kind='MARKET_CALENDAR' ORDER BY identity DESC LIMIT 1",(prefix,prefix+'\uffff')).fetchone()
    try:
        raw=json.loads(row['payload']) if row and len(row['payload'])<=100000 else {}
        opened,closed=(datetime.fromisoformat(raw[k]) for k in ('opens','closes'))
        if opened.tzinfo and closed.tzinfo and opened<closed and opened.astimezone(ZoneInfo('Asia/Kolkata')).date().isoformat()==day:return opened,closed
    except (ValueError,TypeError,KeyError):pass
    return None


def route_check_view(db, now):
    from zoneinfo import ZoneInfo
    ist=ZoneInfo('Asia/Kolkata')
    row=db.execute("SELECT i.intent_id,i.created_at,i.state AS intent_state,o.state,o.payload FROM intents i LEFT JOIN orders o ON o.intent_id=i.intent_id WHERE i.lifecycle_id='route-probe' ORDER BY i.created_at DESC LIMIT 1").fetchone()
    if not row:return None
    at=timestamp(row['created_at'])
    if not at or datetime.fromisoformat(at)>now or datetime.fromisoformat(at).astimezone(ist).date()!=now.astimezone(ist).date():return None
    reason=None;error={}
    if row['state'] is None and row['intent_state']=='SEND_UNKNOWN':
        saved=db.execute('SELECT response FROM attempts WHERE intent_id=? ORDER BY sent_at DESC LIMIT 1',(row['intent_id'],)).fetchone()
        try:raw=json.loads(saved['response']) if saved and len(saved['response'])<10000 else {}
        except (ValueError,TypeError):raw={}
        if not isinstance(raw,dict):raw={}
        reason='HTTP_OUTCOME_UNKNOWN' if raw.get('error')=='HTTPStatusError' else 'OUTCOME_UNKNOWN'
        status=integer(raw.get('http_status'))
        error={'http_status':status if status is not None and 100<=status<=599 else None,
            'broker_error_code':raw.get('broker_error_code') if isinstance(raw.get('broker_error_code'),str) and re.fullmatch(r'[A-Za-z0-9_-]{1,48}',raw['broker_error_code']) else None,
            'broker_reason':choice(raw.get('broker_reason'),{'INVALID_IP','ACCESS_TOKEN','RATE_LIMIT','PRICE_BAND','OPEN_INTEREST','INVALID_INPUT'})}
    if row['state']=='REJECTED':
        reason='BROKER_REJECTED'
        try:
            raw=json.loads(row['payload']) if len(row['payload'])<=100_000 else {}
            text=str(raw.get('omsErrorDescription','')).lower()
            if 'open interest' in text and ('below' in text or 'limit' in text):reason='LOW_OPEN_INTEREST'
        except (ValueError,TypeError,AttributeError):pass
    return {'state':choice(row['state'] or row['intent_state'],ORDER_STATES,'UNKNOWN'),'reason':reason,'occurred_at':at,**error}


def ledger_view(path, *, strategies=(), now=None):
    """One SQLite read transaction, no schema initialization or broker methods."""
    now = now or utcnow()
    out = {'available': False, 'orders': None, 'fills': None, 'incidents': None, 'counts': None,
           'decision_history': {'status': 'UNAVAILABLE'}}
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
            for row in db.execute('SELECT i.security_id,i.side,i.quantity,i.price,i.state,i.created_at,i.lifecycle_id,o.order_id,o.state AS broker_state FROM intents i LEFT JOIN orders o ON o.intent_id=i.intent_id ORDER BY i.created_at DESC LIMIT 100'):
                orders.append({'security_id': label(row['security_id']), 'side': row['side'] if row['side'] in {'BUY','SELL'} else None,
                               'quantity': integer(row['quantity']), 'price': money(row['price']),
                               'state': row['broker_state'] if row['broker_state'] in ORDER_STATES else (row['state'] if row['state'] in ORDER_STATES else 'UNKNOWN'),
                               'occurred_at': timestamp(row['created_at']),
                               'purpose':'ROUTE_CHECK' if row['lifecycle_id']=='route-probe' else 'STRATEGY_ORDER'})
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
            from .performance import strategy_performance
            return {'available': True, 'orders': orders, 'fills': fills, 'incidents': incidents, 'counts': counts, 'last_entry': entry,
                    'strategy_performance':strategy_performance(db),
                    'last_signals':last_signal_views(db),'cash_reconciliation':cash_reconciliation(db),
                    'active_trades':active_trade_views(db),
                    'route_check':route_check_view(db,now),
                    'decision_history':recorded_decisions(db,strategies,now,recorded_session_bounds(db,now))}
    except (sqlite3.Error, OSError, ValueError):
        return out


def local_snapshot(state_dir, now=None):
    now = now or utcnow()
    root = Path(state_dir)
    runtime = runtime_view(read_json(root/'status.json'), now)
    return {'runtime': runtime,
            'connections': connections_view(read_json(root/'connections.json'), now),
            'ledger': ledger_view(root/'ledger.sqlite3', strategies=runtime['strategies'], now=now)}


def seconds_view(raw, now):
    """Separate paper economics can never become broker balance or authority."""
    from dhan_cas_bot.seconds_strategies import NAMES
    if not isinstance(raw,dict) or raw.get('mode')!='SIMULATION' or raw.get('writes_to_broker') is not False:return None
    rows=[]
    for r in raw.get('results',[])[:5] if isinstance(raw.get('results'),list) else []:
        if not isinstance(r,dict) or r.get('strategy') not in NAMES:continue
        rows.append({'strategy':r['strategy'],**{k:money(r.get(k)) for k in ('cash','net')},
            **{k:integer(r.get(k)) for k in ('signals','entries','closed','missed')},
            'open_position':r.get('open_position') is True,
            'last_result':choice(r.get('last_result'),{'NO_MODEL_TRADE','MODEL_MISS','MODEL_CLOSED',
                'SIMULATED_POSITION','SIMULATED_ENTRY_PENDING','SIMULATED_EXIT_PENDING','EXIT_LIMIT_MISS',
                'ARRIVAL_QUOTE_UNAVAILABLE','LIMIT_OR_SIGNAL_MISS','MODEL_UNAFFORDABLE',
                'OPEN_MODEL_POSITION_QUOTE_UNAVAILABLE','MODEL_EXECUTION_CHECK_FAILED'})})
    timing=freshness(raw.get('observed_at'),now,10)
    evaluations=[r for r in strategy_projection(raw.get('evaluations')) if r['strategy'] in NAMES]
    if not timing['fresh']:
        evaluations=[{**r,'state':'UNKNOWN','reason':'STRATEGY_INPUTS_STALE','side':None} for r in evaluations]
    event=raw.get('event_feed') if isinstance(raw.get('event_feed'),dict) else {}
    return {**timing,'mode':'SIMULATION','writes_to_broker':False,'results':rows,'evaluations':evaluations,
        'feed_connected':raw.get('feed_connected') if type(raw.get('feed_connected')) is bool else None,
        'future_current':raw.get('future_current') if type(raw.get('future_current')) is bool else None,
        'options_observed':integer(raw.get('options_observed')),'delay_seconds':money(raw.get('delay_seconds')),
        'initial_bankroll':money(raw.get('initial_bankroll')),
        'status':choice(raw.get('status'),{'UNAVAILABLE'},'AVAILABLE'),
        'reason':choice(raw.get('reason'),{'SESSION_TOKEN_UNAVAILABLE','STARTING_CASH_UNAVAILABLE',
            'PAPER_HISTORY_UNAVAILABLE','CONTRACT_METADATA_UNAVAILABLE','MARKET_ANCHOR_UNAVAILABLE','OBSERVER_FAILED'}),
        'event_feed_state':choice(event.get('state'),{'CONNECTED','UNAVAILABLE'},'UNAVAILABLE'),
        'quote_sample_interval_ms':integer(raw.get('quote_sample_interval_ms')),
        'quote_archive_within_cap':raw.get('quote_archive_within_cap') if type(raw.get('quote_archive_within_cap')) is bool else None}
