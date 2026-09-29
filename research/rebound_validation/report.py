"""Verify saved ledgers and write a fail-closed deployment decision."""
import csv
import hashlib
import json
from collections import Counter
from datetime import datetime
from math import ceil
from pathlib import Path

from dhan_cas_bot.risk import FeeSchedule
from research.gauntlet.core import D
from research.gauntlet.data import ROOT, CACHE, save
from .data import OUT, STORE, NAME, PERIODS
from .fees import schedule
from .replay import START, source_hash


def verify_row(r, dated=False):
    cash = D(r['cash_before'])
    qty = r['quantity']
    lot = r['lot']
    freeze = r['freeze']
    assert qty > 0 and qty % lot == 0
    assert datetime.fromisoformat(r['entry_at']) > datetime.fromisoformat(r['signal_at'])
    assert D(r['entry']) <= D(r['limit'])
    buy = D(r['entry'])*qty
    f = schedule(r['day']) if dated else FeeSchedule()
    assert D(r['limit'])*qty+f.buy(D(r['limit'])*qty, ceil(qty/freeze)) <= cash*D('.95')
    assert sum(p['quantity'] for p in r['exit_parts']) == qty
    fees = f.buy(buy, ceil(qty/freeze))
    sell = D(0)
    for p in r['exit_parts']:
        assert p['quantity'] > 0 and p['quantity'] % lot == 0
        assert datetime.fromisoformat(p['at']) >= datetime.fromisoformat(r['entry_at'])
        assert p['at'][:10] < r['expiry']
        turn = D(p['price'])*p['quantity']
        sell += turn
        f = schedule(p['at'][:10]) if dated else FeeSchedule()
        fees += f.sell(turn, ceil(p['quantity']/freeze))
    assert fees == D(r['fees'])
    assert cash-buy+sell-fees == D(r['cash_after'])
    assert D(r['cash_after'])-cash == D(r['pnl'])


def verify_inputs(hashes):
    for name, digest in hashes.items():
        p = ROOT/name
        assert hashlib.sha256(p.read_bytes()).hexdigest() == digest, name


def main():
    registration = json.loads((OUT/'registration.json').read_text())
    assert registration['protocol_sha256'] == hashlib.sha256((ROOT/'research/rebound_validation/PROTOCOL.md').read_bytes()).hexdigest()
    all_runs = []
    verified = 0
    for provider in ('upstox', 'dhan'):
        x = json.loads((OUT/(provider+'.json')).read_text())
        assert x['source_sha256'] == source_hash(), 'stale '+provider
        verify_inputs(x['input_hashes'])
        for r in x['runs']:
            cash = START
            prior_exit = ''
            for row in r['ledger']:
                assert D(row['cash_before']) == cash
                if row['status'] == 'RESOLVED':
                    assert row['day'] > prior_exit
                    verify_row(row, r.get('fee_model') == 'dated')
                    cash = D(row['cash_after'])
                    prior_exit = row['exit_at'][:10]
                    verified += 1
            if r['unknown']:
                assert r['final_bankroll'] is None
            else:
                assert D(r['final_bankroll']) == cash.quantize(D('.01'))
        all_runs += x['runs']
    controls = json.loads((OUT/'controls.json').read_text())
    assert controls['source_sha256'] == source_hash(), 'stale controls'
    verify_inputs(controls['input_hashes'])
    for r in controls['results']:
        assert len(r['paths']) == 999
        better = sum(p['final_bankroll'] is not None and D(p['final_bankroll']) >= D(r['observed']) for p in r['paths'])
        assert better == r['at_least_observed']
        assert sum(p['final_bankroll'] is None for p in r['paths']) == r['unknown']
    up = {(r['period'], r['scenario']): r for r in all_runs if r['provider'] == 'upstox'}
    dh = {(r['period'], r['scenario']): r for r in all_runs if r['provider'] == 'dhan'}
    fields = ['provider', 'period', 'scenario', 'final_bankroll', 'unknown', 'model_drawdown']
    with (OUT/'scoreboard.csv').open('w') as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        w.writeheader(); w.writerows(all_runs)
    save(OUT/'ledger.json', {'runs': all_runs})
    lines = ['# Rebound deployment qualification — 27 September 2026', '',
             '**Decision: NO LIVE QUALIFIER. Do not deploy the rebound strategy with funded authority.**', '',
             'The unchanged selloff signal fails its registered additional 90-day validation and an alternative',
             'entry-price scenario. The original favorable results remain reproducible but do not establish',
             'a repeatable execution edge. No live orders, deployment, cloud changes or spending occurred.', '',
             'Each period starts independently at INR 9,411.18. Additional validation is 23 December 2025–',
             '22 March 2026 (61 sessions); discovery periods are 23 March–20 June (59) and 21 June–',
             '18 September (63). The additional period is previously unscored strategy history; some',
             'underlying bars existed as prior warm-up. It is not prospective evidence.', '',
             '| Execution scenario | Additional validation | Earlier discovery | Recent discovery |',
             '|---|---:|---:|---:|']
    for sc in ('primary', 'delay3', 'slippage2', 'open_plus_1pct', 'dated_fees', 'delete_best', 'strict'):
        lines.append('| '+sc+' | '+' | '.join(up[p,sc]['final_bankroll'] or 'UNKNOWN' for p in PERIODS)+' |')
    lines += ['', '## What changed and what failed', '',
              'V2 monitors every completed option minute through the effective derivatives close (15:30',
              'before 3 August, 15:40 thereafter), including late triggers and pending orders carried',
              'across the closed session. This correction leaves both original base balances unchanged.',
              'The signal threshold, contract order and sizing were not optimized.', '',
              'The earlier open-plus-1% scenario fills the 29 May call that the adverse-high model rejects.',
              'That trade loses INR 6,959.89; final cash is INR 8,255.83. A pessimistic price on each',
              'accepted trade is therefore not a conservative bound on strategy returns: it can also',
              'remove losing trades. This execution sensitivity is a material failure of qualification.', '',
              'The added validation has twelve selloff dates, three modeled fills, one win and two losses.',
              'Nine dates cannot afford a qualifying lot under the known price/volume rules. Dated fees',
              'raise the validation balance only slightly; they do not rescue the result.', '',
              '## Noise controls', '',
              '999 seeded CE-entry date assignments per period match 15:10, exact calendar days to expiry',
              'and a prior-only 20-session volatility tercile. All dates are selected without option',
              'outcomes; signals face the same whole-lot cash and occupied-position rules. These are',
              'conditional randomization diagnostics, not independent market samples or causal proof.', '',
              '| Period | Controls at least as good | Unresolved | Smoothed tail | Adjusted upper (144 tried variants) |',
              '|---|---:|---:|---:|---:|']
    for r in controls['results']:
        lines.append(f"| {r['period']} | {r['at_least_observed']}/999 | {r['unknown']} | {r['tail_upper']:.3f} | {r['adjusted_144_upper']:.3f} |")
    lines += ['', 'Random assignment assumes comparison within the stated matching groups is meaningful;',
              'it does not eliminate all regime dependence. Failed profit gates stand independently of',
              'these control scores. No significance or live-profit claim is made.', '',
              '## Independent Dhan reconstruction', '',
              '| Period | Dhan base | Dhan dated fees | First unresolved boundary |',
              '|---|---:|---:|---|']
    for p in PERIODS:
        r = dh[p, 'primary']
        lines.append(f"| {p} | {r['final_bankroll'] or 'UNKNOWN'} | {dh[p,'dated_fees']['final_bankroll'] or 'UNKNOWN'} | {r['unknown'] or 'none'} |")
    lines += ['', 'Signal dates remain based on the frozen Upstox underlying tape. This is an independent',
              'option-path reconstruction, not an independent market sample.', '',
              'Dhan rolling observations are matched to actual timestamp, strike and prior-published',
              'expiry mapping. Different strike streams are never treated as one contract. Returned',
              'observations outside the requested calendar day are retained in raw receipts and excluded',
              'from that day’s reconstruction. Non-near expiries have only ATM ±3 coverage; remaining',
              'holes are UNKNOWN. Duplicate disagreements stop reconstruction. Daily official volume,',
              'tick and high/low audits remain separate from the conditional scenario.', '',
              'Neither broker supplies historical executable order-book receipts here. The result is',
              'not repaired merely because a second vendor produces a similar profit number.', '',
              '## Operational evidence and remaining work', '',
              'The read-only cloud check confirms the VM is running the old CAS revision with live',
              'authority disabled in configuration and mandate, and the broker read-only interlock enabled.',
              'It reports RECOVERING; cached-token',
              'profile/funds/positions/orders/trades/IP reads return HTTP 400 DH-906. No daemon restart',
              'or credential persistence was performed. These operational gaps remain unresolved.', '',
              'Because the research gate failed, the conditional production integration and funded',
              'deployment steps were not executed. Full-session handling is tested in the research',
              'replay; it is not an installed overnight trading strategy. No prospective shadow fills',
              'are claimed from Sunday checks. A future candidate needs new predeclared validation,',
              'actual market-hours observations and a separately approved concrete deployment.', '',
              '## Verification and sources', '',
              f'{verified} resolved scenario trade rows pass cash, whole-lot, fee, limit, chronology and expiry checks.',
              'All raw inputs are hashed; original broader-experiment files remain unchanged.',
              '[Registration](registration.json), [scoreboard](scoreboard.csv), [ledger](ledger.json),',
              '[controls](controls.json), [cloud check](cloud_check.json), [fresh API check](api_check.json),',
              '[software checks](software_tests.json), [protocol](../../rebound_validation/PROTOCOL.md).', '',
              'Fee revisions: [NSE FA73061](https://nsearchives.nseindia.com/content/circulars/FA73061.pdf)',
              'and [NSE FATAX73524](https://nsearchives.nseindia.com/content/circulars/FATAX73524.pdf).',
              'The dated scenario uses their effective dates with conservative component rounding;',
              'it remains a fee model, not an actual broker invoice. Production and parent fee policy',
              'were not modified. [Dhan rolling-data limits](https://dhanhq.co/docs/v2/expired-options-data/).', '',
              'Source SHA-256: `'+source_hash()+'`', '']
    (OUT/'REPORT.md').write_text('\n'.join(lines))
    save(OUT/'verification.json', {'source_sha256': source_hash(), 'verified_trade_rows': verified,
                                  'control_paths': sum(len(r['paths']) for r in controls['results']),
                                  'decision': 'NO_LIVE_QUALIFIER', 'funded_authority': False})
    print('Verified', verified, 'trades; NO_LIVE_QUALIFIER')


if __name__ == '__main__':
    main()
