"""Bounded monitor samples, separate from the trading ledger and its outcomes."""
from copy import deepcopy
from datetime import datetime
from zoneinfo import ZoneInfo
import json

from .data import REASONS, STATES, choice, freshness, integer, money, timestamp, strategy_projection

IST = ZoneInfo('Asia/Kolkata')
MAX_EVENTS = 240
MAX_DAYS = 31
MAX_DETAIL_BYTES = 1_400_000


def family_samples(rows):
    """Retain one decision per family; full variant inputs stay in the ledger."""
    groups={}
    priority={'SIGNAL':5,'UNKNOWN':4,'NO_SIGNAL':3,'WAITING':2,'NOT_APPLICABLE':1,'DISABLED':0}
    for row in strategy_projection(rows):
        family=row.get('family') or row['strategy']
        prior=groups.get(family)
        if prior is None or priority.get(row['state'],0)>priority.get(prior['state'],0):
            groups[family]={key:row[key] for key in ('strategy','family','state','reason','evaluated_at','side','enabled','scope')}
    return list(groups.values())


def monitor_sample(report, now):
    rt = report.get('runtime') or {}
    current = freshness(rt.get('observed_at'), now, 45)['fresh'] and rt.get('fresh') is True
    observer = report.get('daily_monitor') or {}
    observer_current = observer.get('mode') == 'READ_ONLY' and observer.get('fresh') is True and freshness(observer.get('observed_at'), now, 90)['fresh']
    obs = rt.get('observation') or {}
    feeds = rt.get('feed_health') or {}
    return {
        'at': now.isoformat(), 'source_at': timestamp(rt.get('observed_at')),
        'source_current': current,
        'state': choice(rt.get('state'), STATES, 'UNKNOWN') if current else 'UNKNOWN',
        'authority': choice(rt.get('authority'), {'ENABLED', 'DISABLED'}, 'UNKNOWN') if current else 'UNKNOWN',
        'mode': choice(rt.get('monitoring_mode'), {'IDLE', 'ACTIVE'}, 'UNKNOWN') if current else 'UNKNOWN',
        'reason': choice(rt.get('reason'), set(REASONS.values())),
        'books': integer(rt.get('books_observed')) if current else None,
        'ltp': money(obs.get('ltp')) if current else None,
        'ltp_at': timestamp(obs.get('ltp_at')),
        'iep': money(obs.get('iep')) if current else None,
        'iep_at': timestamp(obs.get('iep_at')),
        'phase': choice(obs.get('phase'), {'CTS_CLOSE', 'CAS_LM_START', 'CAS_M_STOP', 'CAS_STOP', 'UNKNOWN'}),
        'strategies': family_samples(rt.get('strategy_evaluations')) if current else [],
        'daily_monitor': strategy_projection(observer.get('strategy_evaluations')) if observer_current else [],
        'daily_monitor_current': observer_current,
        'feeds': {key: feeds.get(key, {}).get('connected') if current and type(feeds.get(key, {}).get('connected')) is bool else None
                  for key in ('signal', 'market', 'order')},
    }


def advance_history(previous, report, now):
    if previous is not None and (previous.get('schema') != 1 or not isinstance(previous.get('days'), list)
                                 or not isinstance(previous.get('events'), list)
                                 or not timestamp(previous.get('started_at'))):
        raise ValueError('invalid monitoring history')
    value = deepcopy(previous) if previous else {
        'schema': 1, 'status': 'AVAILABLE', 'started_at': now.isoformat(), 'days': [], 'events': [],
    }
    sample = monitor_sample(report, now)
    last = value['events'][-1] if value['events'] else None
    elapsed = (now - datetime.fromisoformat(last['at'])).total_seconds() if last else None
    changed = last and any(sample.get(key) != last.get(key) for key in ('state', 'authority', 'reason', 'mode', 'phase', 'feeds', 'source_current', 'strategies', 'daily_monitor', 'daily_monitor_current'))
    # Sample each minute and on state changes (coalesced to at most every 5s).
    # Market quotes alone never turn this into an unbounded tick archive.
    if last and (elapsed < 5 or (elapsed < 60 and not changed)):
        return value
    day = now.astimezone(IST).date().isoformat()
    summary = next((row for row in value['days'] if row['date'] == day), None)
    if summary is None:
        summary = {'date': day, 'first_at': sample['at'], 'last_at': sample['at'], 'samples': 0,
                   'unknown_samples': 0, 'gaps': 0, 'states': [], 'last_state': 'UNKNOWN'}
        value['days'].append(summary)
    summary['last_at'] = sample['at']
    summary['samples'] += 1
    summary['unknown_samples'] += int(not sample['source_current'])
    summary['gaps'] += int(elapsed is not None and elapsed > 90)
    summary['last_state'] = sample['state']
    if sample['state'] not in summary['states']:
        summary['states'].append(sample['state'])
    value['days'] = value['days'][-MAX_DAYS:]
    oldest = value['days'][0]['date']
    value['events'] = [row for row in (value['events'] + [sample])[-MAX_EVENTS:]
                       if datetime.fromisoformat(row['at']).astimezone(IST).date().isoformat() >= oldest]
    # Enlarging the production strategy set must not turn monitoring snapshots
    # into unreadable >2MB files. Day totals and durable ledger decisions stay;
    # trim only the already bounded recent monitor samples.
    sizes=[len(json.dumps(row)) for row in value['events']]
    total=sum(sizes)
    while len(value['events'])>1 and total>MAX_DETAIL_BYTES:
        total-=sizes.pop(0);value['events'].pop(0)
        value['detail_truncated']=True
    value['last_recorded_at'] = sample['at']
    return value
