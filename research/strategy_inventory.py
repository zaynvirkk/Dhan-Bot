"""Offline inventory joining every production name to retained research evidence.

Reads a sanitised operator snapshot, never configuration, credentials or a broker.
This validates coverage and compares existing scenarios; it is not a fresh backtest.
"""
import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timedelta
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path

from dhan_cas_bot.expanded_strategies import SPECS, RULES, READINESS, exit_policy
from dhan_cas_bot.release import source_digest
from dhan_cas_bot.session_strategies import CAS, GAP, REBOUND, STRATEGIES, Calendar, Bar, IST, evaluate as dispatch

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / 'research/results'
START = Decimal('9411.18')
PERIODS = ('validation', 'earlier', 'recent')
LABELS = {'LIVE_POSITIVE_SINGLE_SESSION_NOT_VALIDATED': 'One profitable live session; unvalidated',
          'MODEL_LOSES_IN_AT_LEAST_ONE_PERIOD': 'Lost in at least one primary period',
          'MODEL_UNRESOLVED': 'Unresolved historical inputs',
          'NO_MODELED_PROFIT_IN_PRIMARY_WINDOWS': 'No primary-window profit',
          'POSITIVE_BASE_PERIODS_REQUIRES_ROBUSTNESS_AND_FORWARD_EVIDENCE': 'Positive primary periods; too few trades',
          'PROFIT_IN_ONE_PERIOD_OR_THIN_SAMPLE': 'Only one profitable primary period'}


def read_csv(batch):
    return list(csv.DictReader((RESULTS / batch / 'scoreboard.csv').open()))


def cash(row):
    if not row or row.get('unknown'):
        return None
    value = row.get('final_bankroll')
    if value in (None, '', 'UNKNOWN'):
        return None
    result = Decimal(value)
    if not result.is_finite():
        raise ValueError('nonfinite research bankroll')
    return str(result)


def binding(name):
    if name == CAS:
        return 'CAS', 'AUCTION', 'EXPIRY', 'OFFICIAL_AUCTION', None, None
    family, style, scope, schedule = SPECS[name]
    if schedule == 'FRONTIER':
        batch, canonical = 'execution_frontier', name
    elif schedule in ('0930', '1510'):
        batch, canonical = 'broader', name
    elif schedule == 'INTRADAY':
        batch, canonical = 'intraday_challengers', name
    else:
        batch = 'readiness' if family in READINESS else 'multifeature90'
        canonical = name if name.startswith(('EXPIRY_', 'ORDINARY_')) else 'EXPIRY_' + name
    return family, style, scope, schedule, batch, canonical


def entry_window(name):
    if name == CAS:
        return 'Official CAS phase on same-day expiry; route window is separate'
    family, _, _, schedule, _, _ = binding(name)
    if schedule in ('0930', '1510', 'FRONTIER'):
        return '15:10; suffix 0930/1510 specifies NEXT-session exit'
    if family == 'OPEN_DRIVE':
        return '09:45–10:30, five-minute decisions'
    if family == 'GAP_FADE':
        return '09:45–11:30, five-minute decisions'
    if family == 'FIRST_LAST' or family == 'TREND1445':
        return '14:45'
    if family == 'AFTERNOON_COMPRESSION':
        return '13:30–14:45, five-minute decisions'
    if family == 'ORB30':
        return '09:46–12:00; completed opening range and confirmation required'
    if family in ('LATE_BREAK', 'LATE_FADE'):
        return '14:31–15:14; prior range and confirmation required'
    if family in ('OPTION_ACCEL', 'OPTION_ACCEL_OI'):
        return '14:45–15:30, frozen 14:45 strike'
    return '10:00–14:45 (intraday) / 10:00–15:10 (market); rule cadence applies'


def signature(name):
    # Legacy GAP/REBOUND dispatch to their separate evaluator, not SPECS.
    return ('LEGACY_DISPATCH', name) if name in (CAS, GAP, REBOUND) else SPECS[name]


def requirements(name):
    if name == CAS:
        return ['official indicative index/auction phase', 'same-day option depth', 'pre-CAS reference']
    family, _, _, schedule, _, _ = binding(name)
    needs = ['completed NIFTY bars', 'exchange calendar', 'exact contract metadata', 'current option depth/cash/route']
    if schedule not in ('0930', '1510', 'FRONTIER'):
        needs.append('completed futures bars/OI/volume as rule requires')
    if family in ('SECTOR_CATCHUP', 'SECTOR_CONFIRM'):
        needs.append('Bank and IT index bars')
    if family == 'IV_CHEAP_TREND':
        needs.extend(['receipt-timed current IV', 'VIX bars'])
    if family == 'GIFT_CATCHUP':
        needs.append('timestamped GIFT bars plus rule delay')
    if family in ('PCR_CONFIRM', 'PAIN_ESCAPE'):
        needs.append('completed delayed Upstox insight buckets')
    if family in ('PUBLISHED_PCR', 'PUBLISHED_PAIN', 'PRIOR_OI_WALL'):
        needs.append('complete prior-session NSE option chain')
    if family == 'INSTITUTIONAL_ALIGN':
        needs.append('FII/DII publications lagged two verified sessions')
    if family in ('CHAIN_UNWIND', 'SKEW_UNWIND', 'OPTION_ACCEL', 'OPTION_ACCEL_OI', 'PRIOR_OI_WALL'):
        needs.append('same absolute-strike option minutes/OI/volume')
    if family in ('NIFTY_TREND_ALIGNMENT', 'TREND_CONTINUATION') or (schedule == 'FRONTIER' and family == 'TREND_PULLBACK'):
        needs.append('prior-only 20-session trend')
    if family == 'NIFTY_DAY_CONTINUATION':
        needs.append('prior_trend publication currently required by shared branch although direction does not use it')
    return needs


def historical(batch, canonical, tables):
    if not batch:
        return {}, {}, {}
    rows = [r for r in tables[batch] if r['strategy'] == canonical]
    if not rows:
        raise ValueError('unmapped production strategy: ' + canonical)
    if batch == 'execution_frontier':
        rows = [r for r in rows if Decimal(r['allocation']) == Decimal('.95')]
        base = {r['period']: r for r in rows if r['scenario'] == 'rest3'}
        strict = {r['period']: r for r in rows if r['scenario'] == 'strict'}
    else:
        base = {r['period']: r for r in rows if r.get('quality') == 'reported' and r.get('scenario', 'primary') == 'primary'}
        strict = {r['period']: r for r in rows if r.get('quality') == 'strict' and r.get('scenario', 'primary') in ('primary', 'strict')}
    # The later unchanged rebound validation supersedes the favourable discovery
    # periods for qualification. Keep all three; do not hide the failed period.
    if canonical == REBOUND:
        validation = [r for r in tables['rebound_validation'] if r['provider'] == 'upstox']
        base = {r['period']: r for r in validation if r['scenario'] == 'primary'}
        strict = {r['period']: r for r in validation if r['scenario'] == 'strict'}
    stresses = {}
    for period, primary in base.items():
        stresses[period] = {}
        for key in ('delete_best', 'delay2', 'delay3', 'open_plus_1pct', 'slippage2', 'arrival_open', 'tight_limit'):
            if key in primary:
                stresses[period][key] = primary[key] or None
            else:
                candidates = [r for r in rows if r['period'] == period and r.get('scenario') == key and r.get('quality', 'reported') == 'reported']
                if len(candidates) == 1:
                    stresses[period][key] = cash(candidates[0])
        if canonical == REBOUND:
            for r in validation:
                if r['period'] == period and r['scenario'] not in ('primary', 'strict'):
                    stresses[period][r['scenario']] = cash(r)
    return base, strict, stresses


def rule_boundary_checks():
    """Exercise every minute-rule dispatch; fixtures prove no market outcome."""
    from dhan_cas_bot.expanded_strategies import evaluate as expanded
    from datetime import date
    def at(day, clock):
        return datetime.fromisoformat(day + 'T' + clock).replace(tzinfo=IST)
    calendar = Calendar(at('2026-10-15', '09:15'), at('2026-10-15', '15:40'),
                        at('2026-10-14', '09:15'), at('2026-10-14', '15:40'),
                        at('2026-10-16', '09:15'), at('2026-10-16', '15:40'), at('2026-10-15', '09:00'))
    cases = []
    for name in STRATEGIES:
        if name == CAS:
            continue
        family, _, scope, schedule, _, _ = binding(name)
        clock = '10:00'
        if schedule in ('0930', '1510', 'FRONTIER'): clock = '15:10'
        elif family in ('GAP_FADE', 'OPEN_DRIVE'): clock = '09:45'
        elif family in ('FIRST_LAST', 'TREND1445', 'OPTION_ACCEL', 'OPTION_ACCEL_OI'): clock = '14:45'
        elif family == 'AFTERNOON_COMPRESSION': clock = '13:30'
        elif family in ('LATE_BREAK', 'LATE_FADE'): clock = '14:35'
        elif family == 'ORB30': clock = '09:50'
        now = at('2026-10-15', clock)
        expiries = {date(2026, 10, 15)} if scope == 'EXPIRY' else {date(2026, 10, 19)}
        for mode in ('missing_inputs', 'future_bar_only'):
            future_at = now + timedelta(minutes=1)
            bars = {} if mode == 'missing_inputs' else {future_at: Bar(future_at, Decimal(25000), Decimal(25100), 100, 100)}
            result = dispatch(name, now, calendar, bars, bars, expiries, bar_at=now) if name in (GAP, REBOUND) else expanded(name, now, calendar, bars, bars, expiries, features={}, bar_at=now)
            if result.state != 'UNKNOWN' or result.side is not None:
                raise ValueError('missing/future-only data was not rejected: ' + name)
            cases.append({'strategy': name, 'fixture': mode, 'state': result.state, 'reason': result.reason})
    now = at('2026-10-15', '15:10')
    spot = {calendar.opens + timedelta(minutes=1): Bar(calendar.opens + timedelta(minutes=1), Decimal(25000), Decimal(25000), 0, 0),
            now: Bar(now, Decimal(25200), Decimal(25200), 0, 0)}
    without = expanded('NIFTY_DAY_CONTINUATION_1510', now, calendar, spot, {}, {date(2026, 10, 19)}, features={})
    with_unused = expanded('NIFTY_DAY_CONTINUATION_1510', now, calendar, spot, {}, {date(2026, 10, 19)},
                           features={'prior_trend': {'value': '0', 'received_at': now}})
    assert without.state == 'UNKNOWN' and with_unused.state == 'SIGNAL'
    return {'negative_case_count': len(cases), 'cases': cases, 'scope': 'Synthetic information-boundary checks, not profitable market observations',
            'unnecessary_trend_dependency': {'without_trend': without.state, 'with_unused_zero_trend': with_unused.state}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    live = json.loads(args.snapshot.read_text())
    names = live['scanned_names']
    if len(names) != len(set(names)) or set(names) != set(STRATEGIES):
        raise ValueError('live scanned registry differs from current complete registry')
    tables = {batch: read_csv(batch) for batch in ('intraday_challengers', 'broader', 'multifeature90', 'readiness', 'execution_frontier', 'rebound_validation')}
    all_scorecards = []
    for path in sorted(RESULTS.glob('**/scoreboard.csv')):
        all_scorecards.extend({'source': str(path.relative_to(ROOT)), **r} for r in csv.DictReader(path.open()))
    overlay_table = read_csv('profit_exits')
    evaluated = {r['strategy']: r for r in live['evaluations']}
    results = {r['strategy']: r for r in live['strategy_results']}
    groups = defaultdict(list)
    for name in names:
        groups[signature(name)].append(name)
    rows = []
    for name in names:
        family, style, scope, schedule, batch, canonical = binding(name)
        base, strict, stress = historical(batch, canonical, tables)
        balances = {p: cash(r) for p, r in base.items()}
        known = [Decimal(v) for v in balances.values() if v is not None]
        if name == CAS:
            verdict = 'LIVE_POSITIVE_SINGLE_SESSION_NOT_VALIDATED'
        elif len(known) != len(balances):
            verdict = 'MODEL_UNRESOLVED'
        elif any(v < START for v in known):
            verdict = 'MODEL_LOSES_IN_AT_LEAST_ONE_PERIOD'
        elif all(v == START for v in known):
            verdict = 'NO_MODELED_PROFIT_IN_PRIMARY_WINDOWS'
        elif all(v > START for v in known) and len(known) >= 2:
            verdict = 'POSITIVE_BASE_PERIODS_REQUIRES_ROBUSTNESS_AND_FORWARD_EVIDENCE'
        else:
            verdict = 'PROFIT_IN_ONE_PERIOD_OR_THIN_SAMPLE'
        eval_row = evaluated.get(name, {})
        eligible = live['runtime']['expiry_today'] if scope == 'EXPIRY' else not live['runtime']['expiry_today'] if scope == 'ORDINARY' else True
        overlay_name = canonical.rsplit('_', 1)[0] + '_NET50' if canonical else None
        overlays = [r for r in overlay_table if r['strategy'] == overlay_name and r['quality'] == 'reported']
        row = {'strategy': name, 'family': family, 'scope': scope, 'entry_window_ist': entry_window(name),
               'funded': name in live['funded'], 'session_eligible_today': eligible,
               'live_state': eval_row.get('state', live['runtime']['state'] if name == CAS else 'MISSING_EVALUATION'),
               'live_reason': eval_row.get('reason', 'CAS_REQUIRES_SAME_DAY_EXPIRY' if name == CAS and not eligible else 'UNKNOWN'),
               'evaluated_at': eval_row.get('evaluated_at'), 'rule': RULES.get(family, 'Official indicative-index residual/convergence rule'),
               'inputs': requirements(name), 'legacy_exit_policy': exit_policy(name) if name != CAS else {'policy': 'CAS convergence/invalidation/session backstop'},
               'exact_aliases': [n for n in groups[signature(name)] if n != name],
               'evidence_csv': f'research/results/{batch}/scoreboard.csv' if batch else None,
               'evidence_strategy': canonical, 'model_starting_cash': str(START),
               'model_base_bankrolls': balances, 'model_base_trades': {p: r.get('trades') for p, r in base.items()},
               'model_strict_bankrolls': {p: cash(r) for p, r in strict.items()},
               'model_stress_bankrolls': stress, 'related_net50_bankrolls': {r['period']: cash(r) for r in overlays},
               'live_execution': results.get(name), 'evidence_verdict': verdict,
               'exact_current_live_policy_backtest': False, 'new_funded_qualification': False}
        evidence_names = {name, canonical, *row['exact_aliases']}
        row['all_retained_evidence'] = [r for r in all_scorecards if (r.get('strategy') or r.get('engine')) in evidence_names]
        row['confidence'] = ('Highest relative; one live session only' if name == CAS else
                             'Lowest: actual loss plus losing models' if name == 'ORDINARY_PUBLISHED_PCR_TRAIL' else
                             'Research only: one fill per primary period' if name == 'TREND_PULLBACK_FAST' else
                             'Low: historical period failure' if verdict == 'MODEL_LOSES_IN_AT_LEAST_ONE_PERIOD' else
                             'Unknown: unresolved data' if verdict == 'MODEL_UNRESOLVED' else
                             'Research only: sparse or inconsistent evidence')
        if name == REBOUND:
            row['additional_validation_csv'] = 'research/results/rebound_validation/scoreboard.csv'
        rows.append(row)
    assert len(rows) == len(names) == 137
    assert all(r['evidence_csv'] for r in rows if r['strategy'] != CAS)
    assert len(groups) == 125
    assert {r['strategy'] for r in rows if r['funded']} == set(live['funded'])
    summary = {'observed_at': live['now'], 'generated_at': datetime.now().astimezone().isoformat(),
               'scanned_configurations': len(rows), 'distinct_families_including_cas': len({r['family'] for r in rows}),
               'distinct_dispatch_specifications': len(groups), 'duplicate_alias_names': len(rows) - len(groups),
               'funded': live['funded'], 'cash': live['cash'], 'today_orders': live['today_orders'],
               'open_positions': live['open_positions'], 'pending_orders': live['pending_orders'],
               'next_nifty_expiry': live['instrument_expiry'], 'expiry_today': live['runtime']['expiry_today'],
               'live_states_excluding_cas': dict(Counter(r['state'] for r in live['evaluations'])),
               'live_reasons_excluding_cas': dict(Counter(r['reason'] for r in live['evaluations'])),
               'evidence_verdicts': dict(Counter(r['evidence_verdict'] for r in rows)),
               'missing_live_evaluations': [r['strategy'] for r in rows if r['live_state'] == 'MISSING_EVALUATION'],
               'new_funded_qualifiers': [], 'current_source_digest': source_digest(ROOT),
               'auditor_sha256': sha256(Path(__file__).read_bytes()).hexdigest(),
               'interpretation': 'Inventory and existing-scenario audit, not a fresh backtest or exact live-policy fill proof.'}
    summary['current_profit_policy'] = live.get('profit_policy')
    summary['live_health'] = {'api_errors': live['api_errors'],
                            'account_snapshot_fresh': live['runtime']['account_snapshot_fresh'],
                            'services': {k: v['ActiveState'] for k, v in live['services'].items()},
                            'feeds': live['runtime']['feed_health'], 'inputs': live['runtime']['input_health'],
                            'route_verified': live['runtime']['broker_route_verified']}
    paths = sorted(RESULTS.glob('**/scoreboard.csv'))
    summary['evidence_sha256'] = {str(p.relative_to(ROOT)): sha256(p.read_bytes()).hexdigest() for p in paths}
    args.output.mkdir(parents=True, exist_ok=True)
    outside = defaultdict(list)
    for path in sorted(RESULTS.glob('**/scoreboard.csv')):
        for row in csv.DictReader(path.open()):
            name = row.get('strategy') or row.get('engine')
            if name and name not in names:
                outside[name].append({'source': str(path.relative_to(ROOT)), **row})
    external = []
    original = {'EVENT_CONTINUATION', 'INTRADAY_EVENT', 'EXPIRY_FORCED_FLOW', 'NONEXPIRY_FORCED_FLOW',
                'PASSIVE_FLOW', 'SECTOR_SHOCK_LAG', 'SCHEDULED_EVENT_VOL', 'BLOCK_OFS_DISLOCATION', 'CROSS_MARKET_LEAD_LAG'}
    for name, evidence in sorted(outside.items()):
        kind = ('ALTERNATIVE_EXIT_OVERLAY' if name.endswith(('_NET25', '_NET50', '_NET75')) else
                'ORIGINAL_GAUNTLET_NO_FULL_PRODUCTION_PATH' if name in original else
                'STOCK_RESEARCH_NO_PRODUCTION_PATH' if any(k in name for k in ('CASH', 'CALL5')) else
                'MULTILEG_RESEARCH_NO_PRODUCTION_PATH' if any(k in name for k in ('STRADDLE', 'STRANGLE')) else
                'CONTROL_OR_OTHER_UNIMPLEMENTED_RESEARCH')
        external.append({'strategy': name, 'kind': kind, 'sources': sorted({r['source'] for r in evidence}),
                         'new_entry_production_path': False, 'retained_records': evidence})
    summary['additional_research_identifiers_not_scanned'] = len(external)
    summary['additional_research_categories'] = dict(Counter(r['kind'] for r in external))
    (args.output / 'research_not_deployed.json').write_text(json.dumps(external, indent=2) + '\n')
    with (args.output / 'research_not_deployed.csv').open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=['strategy', 'kind', 'new_entry_production_path', 'sources'])
        writer.writeheader()
        for row in external:
            writer.writerow({k: '; '.join(v) if isinstance(v, list) else v for k, v in row.items() if k != 'retained_records'})
    rechecks = {p.stem: json.loads(p.read_text())['summary'] for p in args.output.glob('recheck_*.json')}
    summary['cached_execution_rechecks'] = rechecks
    summary['scenarios_reexecuted'] = sum(r['scenarios_reexecuted'] for r in rechecks.values())
    summary['different_reexecuted_paths'] = sum(r['different'] for r in rechecks.values())
    boundary = rule_boundary_checks()
    summary['synthetic_information_boundary_cases'] = boundary['negative_case_count']
    (args.output / 'information_boundaries.json').write_text(json.dumps(boundary, indent=2) + '\n')
    for row in rows:
        periods = row['model_base_bankrolls']
        strict = row['model_strict_bankrolls']
        checks = {'positive_all_base_periods': len(periods) >= 2 and all(v is not None and Decimal(v) > START for v in periods.values()),
                  'positive_all_strict_periods': len(strict) == len(periods) and len(strict) >= 2 and all(v is not None and Decimal(v) > START for v in strict.values()),
                  'untouched_forward_validation': False,
                  'exact_current_live_quote_policy_replay': row['exact_current_live_policy_backtest']}
        row['qualification_checks'] = checks
        row['qualification_blockers'] = [k for k, v in checks.items() if v is not True]
        row['new_funded_qualification'] = all(v is True for v in checks.values())
    summary['new_funded_qualifiers'] = [r['strategy'] for r in rows if r['new_funded_qualification']]
    (args.output / 'audit.json').write_text(json.dumps({'summary': summary, 'rows': rows}, indent=2) + '\n')
    fields = ['strategy', 'family', 'confidence', 'funded', 'session_eligible_today', 'live_state', 'live_reason', 'entry_window_ist',
              'earlier_model_cash', 'recent_model_cash', 'validation_model_cash', 'evidence_verdict', 'exact_aliases',
              'evidence_csv', 'evidence_strategy', 'exact_current_live_policy_backtest']
    with (args.output / 'strategies.csv').open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader()
        for row in rows:
            flat = {k: row.get(k) for k in fields}
            flat.update({p + '_model_cash': row['model_base_bankrolls'].get(p) for p in PERIODS})
            flat['exact_aliases'] = ', '.join(row['exact_aliases'])
            writer.writerow(flat)
    lines = ['# Complete production-strategy inventory — 15 October 2026', '',
             f'Live snapshot: {summary["observed_at"]}. All **137** configured names checked, including **136** minute-rule evaluations and CAS.', '',
             '**This is a fresh inventory/evidence audit and cached execution recheck, not 137 new end-to-end live-policy backtests.** Existing candle-model results do not certify the exact deployed policy, current profit-ratchet overlay, real historical spreads, queues or fills.', '',
             'The main research windows are 23 March–20 June and 21 June–18 September 2026, each 90 calendar days. Additional rebound/frontier validation is 23 December 2025–22 March 2026. These are reused historical windows, not the latest rolling 90 days or untouched future observations.', '',
             f'The names represent **{len(groups)} dispatch specifications** across **{summary["distinct_families_including_cas"]} family labels**. Twelve names are exact aliases. Exit variations and families share signals and capital; they are not independent discoveries.', '',
             f'Funded: {", ".join(live["funded"])}. Cash INR {live["cash"]}; orders today {live["today_orders"]}; open positions {live["open_positions"]}. Next NIFTY expiry {live["instrument_expiry"]}.', '',
             '## Coverage and qualification', '',
             'Every non-CAS name is bound to a retained research scoreboard. Every other scoreboard record under the same name or exact alias is also attached in audit.json; the headline categories use the selected primary batch and do not erase older positive results. Unknown data and zero-fill paths are not profits. The later rebound failure and all three frontier periods are included. All model paths start at INR 9,411.18 independently.', '',
             'No additional funded qualifier is established. CAS has real positive net receipts from one expiry, not a validated repeatable edge. All remaining configurations stay observation-only.', '',
             f'Re-executed **{summary["scenarios_reexecuted"]:,}** cached candle-execution scenarios against current kernels; **{summary["different_reexecuted_paths"]}** changed paths. These reuse saved signals and tapes and include unresolved scenarios; they are not independent new observations. Underlying input hashes were checked. Original source-bound reports were not patched to bypass their stale-source guards. NIFTY scenario noise controls were not rerun; the separate event-engine refresh below reran its own controls.', '',
             f'Every one of the 136 minute-rule dispatches rejects missing inputs and future-only bars: **{boundary["negative_case_count"]} synthetic negative cases**. This proves software boundaries, not profits.', '',
             '| Evidence category | Configurations |', '| --- | ---: |',
             *[f'| {LABELS[label]} | {count} |' for label, count in summary['evidence_verdicts'].items()], '',
             '## All configurations', '',
             'Cash columns below are retained reported-candle scenario outputs, not money earned live. UNKNOWN means an unresolved path. Blank validation means that batch did not have a third period.', '',
             '| Configuration | Funding | Today | Earlier model | Recent model | Additional validation | Evidence verdict |',
             '| --- | --- | --- | ---: | ---: | ---: | --- |']
    for row in rows:
        balances = row['model_base_bankrolls']
        values = [balances.get(p) or ('UNKNOWN' if p in balances else '—') for p in ('earlier', 'recent', 'validation')]
        lines.append('| ' + ' | '.join([row['strategy'], 'Funded' if row['funded'] else 'Observe', row['live_state'], *values, LABELS[row['evidence_verdict']]]) + ' |')
    lines += ['', '## Important source and execution distinctions', '',
              '- Twelve unprefixed expiry names are exact aliases of their EXPIRY-prefixed names. Both labels retain the same model result rather than earning two pieces of evidence.',
              '- TREND_PULLBACK_FAST has positive baseline cash in both reused windows but only one modeled filled trade per window. This is a thin research lead, not a robust qualifier.',
              '- TREND1445_TRAIL has an older positive expiry result: 9,411.18 → 31,436.13 over October–March, from only two modeled trades (one win, one loss). Removing its best trade leaves 5,143.23. The newer primary windows had no fills. Its earlier positive result is included in all_retained_evidence; NO_MODELED_PROFIT_IN_PRIMARY_WINDOWS does not mean it never made a modeled profit.',
              '- NIFTY_SELLOFF_REBOUND_1510 failed its later 90-day validation and alternative entry execution scenario. Its earlier attractive results are not the final qualification result.',
              '- Current live exits overlay NET_PROFIT_RATCHET_V1 where recorded. Related NET50 research results are in audit.json; they are not certified exact replicas of every live variant.',
              '- The intraday, multifeature and readiness report guards detect old source receipts after the optional liquidation-hook change. Fresh path-by-path rechecks preserve the old files and reproduce the cached scenarios; stale Monte Carlo source receipts are not promoted to current significance evidence.',
              '- The production NIFTY_DAY_CONTINUATION branch currently asks for prior_trend even though this rule does not use trend to choose direction. This is an unnecessary input dependency, not evidence of alpha.',
              '- _0930 overnight suffixes describe the next-session exit, not a morning entry. Fixed observation windows remain part of the tested hypotheses.',
              '- Original company-event, passive-flow, block/OFS, scheduled-volatility and full cross-market/stock strategies are not implemented by this NIFTY-only registry. Similar labels are not substitutes for their missing catalyst and execution paths.',
              '- No broker order, activation, restart or production-policy change is performed by this auditor.', '',
              '## Live operational check', '',
              'Snapshot health: account reconciliation fresh=' + str(summary['live_health']['account_snapshot_fresh'])
              + '; broker API errors=' + str(summary['live_health']['api_errors'])
              + '; connected sockets=' + str([k for k, v in summary['live_health']['feeds'].items() if v['connected']])
              + '; current completed spot/futures=' + str({k: summary['live_health']['inputs'].get(k, {}).get('current_complete') for k in ('spot', 'future')})
              + '; option-history readiness=' + str(summary['live_health']['inputs'].get('options'))
              + '. Exact receipt timestamps and errors are retained in audit.json. Socket connectivity is not funded route qualification.', '',
              '## Research identifiers outside the live registry', '',
              f'Also inventoried **{len(external)}** research identifiers without their own scanned production entry path: ' + json.dumps(summary['additional_research_categories'], sort_keys=True) + '. These include exit overlays and controls, not that many independent additional bots.', '',
              'The original nine gauntlet families are all retained in this external inventory. NIFTY option-acceleration, sector-co-movement and GIFT rules are limited proxies, not complete implementations of full-universe forced-flow, event, passive-flow or cross-market strategies.', '',
              'OI_SQUEEZE_CASH5 is another historical research lead outside the NIFTY registry: 9,411.18 → 10,342.25 / 10,949.47 across the two reported windows, with 8/9 modeled fills. Its recent best-trade-deletion result falls to 8,552.35 and strict source reconciliation remains UNKNOWN. It is not a funded qualifier.', '',
              'The original EVENT_CONTINUATION and INTRADAY_EVENT engines were freshly replayed over 21 June–18 September (90 calendar days), including 18 reference/compiled parity cases and 1,998 matched random-side paths. Economic paths match the retained research. EVENT_CONTINUATION has five modeled round trips and UNKNOWN terminal wealth; INTRADAY_EVENT has four modeled round trips and conditional cash 3,453.01. Both full-family bankrolls and strict paths remain UNKNOWN due to coverage gaps. Neither qualifies or has a production entry path. Fresh timestamped receipts are archived under event90_refresh; original historical receipt files were preserved.', '',
              '[Fresh event replay verification](event90_refresh/verification.json)', '',
              '[All additional research identifiers](research_not_deployed.csv) · [Their retained scoreboard records](research_not_deployed.json)', '',
              '[Machine-readable full inputs, costs/evidence and scenario details](audit.json) · [All 137 rows as CSV](strategies.csv)', '']
    (args.output / 'REPORT.md').write_text('\n'.join(lines))
    print(json.dumps(summary, sort_keys=True))


if __name__ == '__main__':
    main()
