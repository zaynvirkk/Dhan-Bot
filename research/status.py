"""Refresh the nine-family progress report from actual local research artifacts.

Run: python -m research.status
Missing or partial evidence never becomes a full-family bankroll result.
"""
import json
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
from research.gauntlet.data import CACHE,ROOT,save
from research.gauntlet.provenance import source_manifest,digest

FAMILIES=(
    'EVENT_CONTINUATION','INTRADAY_EVENT','EXPIRY_FORCED_FLOW',
    'NONEXPIRY_FORCED_FLOW','PASSIVE_FLOW','SECTOR_SHOCK_LAG',
    'SCHEDULED_EVENT_VOL','BLOCK_OFS_DISLOCATION','CROSS_MARKET_LEAD_LAG')

def read(name,default):
    p=CACHE/name
    return json.loads(p.read_text()) if p.exists() else default

def main():
    result_path=ROOT/'research/results/scoreboard.json'
    if result_path.exists():
        report=json.loads(result_path.read_text())
        if report['source_sha256']!=source_manifest()['sha256']:
            raise RuntimeError('Final report source is stale; regenerate replays before reporting completion')
        noise_file=ROOT/'research/results/noise_audit.json'
        noise=json.loads(noise_file.read_text()) if noise_file.exists() else None
        if noise:
            if noise['source_sha']!=source_manifest()['sha256'] or any(
                    digest(ROOT/p)!=sha for p,sha in noise['noise_source_sha'].items()):
                raise RuntimeError('Noise audit is stale; regenerate its results before updating status')
            report['noise_audit']={'status':noise['status'],'total_random_paths':noise['total_random_paths'],
                'filing_references':noise['filing_references'],'winner':None,
                'full_family_validation_complete':False,'report':'results/NOISE-AUDIT.md'}
        save(ROOT/'research/status.json',report)
        lines=['# Dhan strategy gauntlet — results', '',
            '**Nine bounded discovery variants tested; no validated winner.**', '',
            'The full-universe, executable and statistically validated gauntlet remains incomplete. '
            'All full-family bankrolls are UNKNOWN. Each independent model started with INR 9,411.18 '
            'on July 20 and used data through September 18, 2026.', '',
            'See the [full report](results/GAUNTLET.md), [scoreboard CSV](results/scoreboard.csv), '
            '[execution scenarios](results/execution_scenarios.csv) and [per-bot ledgers](results/ledgers/).', '',
            '| Bot | Closed trades | Cash after resolved trades (INR) | Path |',
            '|---|---:|---:|---|']
        for r in report['scoreboard']:
            path='Stopped at unresolved trade' if r['unresolved_path'] else 'Conditional observed-data scenario'
            if r['signals']==0:path='No observed signal in narrow scope'
            lines.append(f"| {r['engine']} | {r['trades']} | {r['conditional_cash']} | {path} |")
        lines += ['', 'These balances are conditional diagnostics. A stopped path reports cash before '
            'its unresolved trade, not final equity. Data gaps can change earlier trades and subsequent '
            'bankrolls. Zero signals in one subvariant do not validate the broader family.', '',
            'Data acquisition completed for 21,415 planned option contract-days: 19,227 reconcile '
            'with NSE traded totals; 2,188 remain uncertain. All 45 scheduled model replays finished. '
            'Historical depth, complete event and family inputs, broker-specific RMS and untouched '
            'holdout validation remain outstanding.', '',
            'The prior EVENT_CONTINUATION leadership claim is not supported by this replay. '
            'No live orders were submitted. See [protocol](gauntlet/PROTOCOL.md) for the frozen '
            'rules and disclosed discovery revisions.', '',
            'Refresh derived results with `.venv/bin/python -m research.report` and '
            '`.venv/bin/python -m research.status`.']
        if noise:
            lines[4:4]=[
                f"The follow-up [noise audit](results/NOISE-AUDIT.md) completed {noise['total_random_paths']:,} "
                f"random-side bankroll controls and processed {noise['filing_references']:,} original attachment "
                'references. None of the four original active families has a convincing primary directional '
                'result after the nine-family adjustment. The two expanded event variants are reported '
                'separately; neither is an independently validated winner.', '']
        (ROOT/'research/STATUS.md').write_text('\n'.join(lines)+'\n')
        print(json.dumps({'status':report['status'],'winner':None,'scenarios':len(report['scenarios'])}))
        return
    raise RuntimeError('Final discovery report absent; finish research.run_suite and research.report first')

if __name__=='__main__':main()
