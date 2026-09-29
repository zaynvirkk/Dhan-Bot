"""Audited, derived noise diagnostics. Does not promote conditional cash to equity."""
import csv,json,hashlib
from collections import Counter
from datetime import datetime,timezone
from decimal import Decimal as D
from research.gauntlet.data import CACHE,ROOT,save
from research.gauntlet.provenance import source_manifest,digest
from research.gauntlet.replay import SOURCES
from research.noise.compile import NOISE
from research.noise import paths,direction,filings,content,universe
from research import report as base_report

OUT=ROOT/'research/results'

def read(file):return json.loads(file.read_text())
def money(x):return 'UNKNOWN' if x is None else f'{D(x):,.2f}'
def percent(x):return '—' if x is None else f'{x*100:.3f}%'

def run():
    noise=read(NOISE/'noise_summary.json');direct=read(NOISE/'direction.json')
    docs=read(NOISE/'filings.json');extension=read(NOISE/'content_summary.json')
    assert set(x['engine'] for x in noise['engines'])==set(SOURCES)
    assert direct['script_sha']==digest(direction.__file__)
    assert all(digest(CACHE/p)==sha for p,sha in direct['input_hashes'].items())
    assert docs['classifier_sha']==digest(filings.__file__)
    assert docs['universe_sha']==digest(universe.__file__)
    assert docs['total']==len(docs['records'])==3413
    assert dict(Counter(x['status'] for x in docs['records']))==docs['counts']
    assert all(x['classifier_sha']==docs['classifier_sha'] for x in docs['records'])
    for document in docs['records']:
        key=hashlib.sha256(document['url'].encode()).hexdigest()
        raw=NOISE/'filings_raw'/(key+('.zip' if document['url'].lower().endswith('.zip') else '.pdf'))
        text=NOISE/'filings_text'/(key+'.txt')
        if document.get('raw_sha'):assert digest(raw)==document['raw_sha']
        if document.get('text_sha'):assert digest(text)==document['text_sha']
    core_sha=source_manifest()['sha256'];rows=[];all_paths=[];parity_cases=0
    for n in noise['engines']:
        engine=n['engine'];full=read(NOISE/(engine+'_noise.json'))
        assert full['source_sha']==core_sha and full['runner_sha']==digest(paths.__file__)
        assert full['compiled_sha']==digest(NOISE/(engine+'_compiled.json'))
        assert full['parity_passed']
        for seed,sha in full['parity_reference_sha'].items():
            f=CACHE/'results'/('v5_'+engine+'_1_high'+('' if seed=='None' else '_random_'+seed)+'.json')
            assert digest(f)==sha
        parity_cases+=len(full['parity_reference_sha'])
        assert direct['engines'][engine]['source_sha']==digest(CACHE/SOURCES[engine])
        base=full['baseline'];p=full['paths']
        if full['random_paths']:
            assert full['random_paths']==999 and [r['seed'] for r in p]==list(range(999))
        for r in p:
            assert (r['terminal_conditional_cash'] is None)==r['stopped']
        all_paths.extend(p)
        row={'engine':engine,'baseline_closed_trades':base['trades'],'baseline_targets':base['targets'],
            'baseline_last_resolved_cash':base['last_resolved_cash'],
            'baseline_terminal_conditional_cash':base['terminal_conditional_cash'],
            'baseline_stopped':base['stopped'],'baseline_coverage_gaps':base['gaps'],
            'full_family_bankroll':None,'random_paths':len(p),'unresolved_random_paths':full['unresolved_random_paths'],
            'random_rank_bounds':full['rank_bounds'],'random_terminal_percentiles':full['random_terminal_percentiles'],
            'random_profitable_completed_paths':full['random_profitable_paths'],
            'distinct_completed_control_balances':len({p['terminal_conditional_cash'] for p in full['paths'] if not p['stopped']}),
            'strict_path':{k:v for k,v in full['strict'].items() if k!='ledger'},
            'strict_stop':full['strict']['ledger'][-1] if full['strict']['ledger'] else None,
            'direction':direct['engines'][engine]['metrics']['15'],
            'primary_holm_p':direct['engines'][engine]['primary_holm_p'],
            'verdict':'NO_DEMONSTRATED_EDGE' if p else 'NO_SAMPLE_IN_BOUNDED_VARIANT',
            'scope':base_report.SCOPES[engine]}
        row['direction']={k:v for k,v in row['direction'].items() if k not in ('rows','day_means')}
        rows.append(row)
    assert len(all_paths)==3996 and parity_cases==29
    with (OUT/'noise_paths.csv').open('w',newline='') as handle:
        fields=['engine','seed','stopped','gaps','terminal_conditional_cash','last_resolved_cash','trades','wins','targets','drawdown']
        w=csv.DictWriter(handle,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(all_paths)
    with (OUT/'directional_noise.csv').open('w',newline='') as handle:
        fields=['engine','horizon_minutes','observations','independent_dates','mean_signed_underlying_return','ci95_low','ci95_high','raw_p','primary_holm_p','gap_count']
        w=csv.DictWriter(handle,fieldnames=fields);w.writeheader()
        for engine,x in direct['engines'].items():
            for horizon,m in x['metrics'].items():
                ci=m.get('ci') or [None,None]
                w.writerow(dict(zip(fields,[engine,horizon,m['observations'],m['days'],m.get('mean_signed_return'),*ci,m['p'],x['primary_holm_p'] if horizon=='15' else None,len(m['gaps'])])))
    content_paths=[]
    for x in extension['engines']:
        assert x['reference_parity_passed'] and x['content_script_sha']==digest(content.__file__)
        assert x['runner_sha']==digest(paths.__file__) and x['filings_sha']==digest(NOISE/'filings.json')
        assert x['input_sha']==digest(NOISE/'content_event_candidates.json')
        assert x['compiled_sha']==digest(NOISE/(x['engine']+'_content_compiled.json'))
        path_file=NOISE/(x['engine']+'_content_paths.json')
        assert x['paths_sha']==digest(path_file)
        controls=read(path_file)
        assert x['random_paths']==len(controls)==999
        assert [p['seed'] for p in controls]==list(range(999))
        assert all((p['terminal_conditional_cash'] is None)==p['stopped'] for p in controls)
        content_paths.extend(controls)
        ref_file=NOISE/(x['engine']+'_content_reference.json')
        assert x['reference_sha']==digest(ref_file)
        ref=read(ref_file);base_report.audit_ledger(ref)
        old=base_report.OUT
        try:base_report.OUT=OUT/'content';base_report.write_ledger(ref)
        finally:base_report.OUT=old
    assert len(content_paths)==1998
    with (OUT/'content_noise_paths.csv').open('w',newline='') as handle:
        fields=['engine','seed','stopped','gaps','terminal_conditional_cash','last_resolved_cash','trades','wins','targets','drawdown']
        w=csv.DictWriter(handle,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(content_paths)
    save(OUT/'filing_coverage.json',{'total_references':docs['total'],'counts':docs['counts'],
        'metadata_inventory':read(NOISE/'metadata_scope_audit.json'),
        'references':[{'url':x['url'],'status':x['status'],'categories':x.get('categories',[]),
            'events':x['events'],'error':x.get('error'),'raw_sha':x.get('raw_sha'),
            'text_sha':x.get('text_sha'),'unreadable_members':x.get('unreadable_members',[])} for x in docs['records']],
        'classifier_sha':docs['classifier_sha'],'universe_sha':docs['universe_sha']})
    before={s['id']:s for s in read(CACHE/'event_candidates.json')}
    after={s['id']:s for s in read(NOISE/'content_event_candidates.json')}
    changes=[]
    for sid in sorted(set(before)|set(after)):
        a=before.get(sid,{});b=after.get(sid,{})
        if (a.get('materiality'),a.get('event_id'))==(b.get('materiality'),b.get('event_id')):continue
        changes.append({'id':sid,'old_quality':a.get('materiality'),'new_quality':b.get('materiality'),
            'old_event_id':a.get('event_id'),'new_event_id':b.get('event_id')})
    save(OUT/'content_candidate_changes.json',{'before':len(before),'after':len(after),'changes':changes})
    result={'status':'COMPLETED_BOUNDED_NOISE_AUDIT','generated_at':datetime.now(timezone.utc).isoformat(),
        'start_cash':'9411.18','period':['2026-07-20','2026-09-18'],'source_sha':core_sha,
        'noise_source_sha':{str(p.relative_to(ROOT)):digest(p) for p in sorted((ROOT/'research/noise').glob('*.py'))},
        'protocol_sha':digest(ROOT/'research/noise/PROTOCOL.md'),'random_paths':3996,
        'content_random_paths':1998,'total_random_paths':5994,
        'original_reference_parity_cases':parity_cases,'content_reference_parity_cases':2,
        'scoreboard':rows,'filing_counts':docs['counts'],'filing_references':docs['total'],
        'content_variants':extension['engines'],'full_family_winner':None,
        'untouched_holdout_completed':False,'actual_execution_verified':False}
    save(OUT/'noise_audit.json',result)
    lines=['# Nine-bot noise audit — 20 September 2026','',
        '**No demonstrated profitable, repeatable winner.** The active frozen variants lose money in the conditional bar replay and do not show convincing directional performance in the primary noise test. The five zero-signal subvariants have no statistical sample; they are not proven good or bad. Full-family bankrolls remain UNKNOWN.','',
        'Every original bot starts independently with INR 9,411.18 on July 20; data ends September 18, 2026. This is the already examined discovery period. The original 45 execution scenarios remain in [GAUNTLET.md](GAUNTLET.md); this audit adds **3,996 original-variant random-side bankroll paths**, **9,999 day-block randomizations and bootstraps per directional test**, and two original-attachment event replays with **1,998 additional random-side controls** (5,994 total). No broker orders were submitted.','',
        '## Original frozen variants','',
        '| Bot | Closed trades | Conditional cash / unresolved balance | Random controls matching or beating it | Verdict |',
        '|---|---:|---:|---:|---|']
    for r in rows:
        rank=r['random_rank_bounds'];value=money(r['baseline_last_resolved_cash'])
        if r['baseline_stopped']:value+=' before unresolved trade'
        comparison='Not rankable' if r['baseline_stopped'] else 'No sample'
        if rank:comparison=f"{rank['lower']*100:.1f}%" if rank['lower']==rank['upper'] else f"{rank['lower']*100:.1f}–{rank['upper']*100:.1f}%"
        lines.append(f"| {r['engine']} | {r['baseline_closed_trades']} | {value} | {comparison} | {r['verdict']} |")
    lines+=['',
        'These balances are **model diagnostics, not certified ending account equity**. Missing contract history and broker eligibility can change earlier decisions and every subsequent bankroll. Event continuation stops at an unresolved holding/exit; its last resolved balance is not a terminal return. The separate strict replay stops at the first data uncertainty and also leaves the full result unknown. No-signal cash is only cash in that narrow tested variant.','',
        'The thousands of controls reuse the same historical observations; they do not create thousands of independent trades. The original four active baselines contain only 23 closed trades and zero 2x target exits. Repeated controls can have identical outcomes, especially where only two trades were affordable.','',
        'The random controls use the same underlying and decision times, but choose CE/PE randomly. Each control compounds its own whole-lot bankroll and reruns contract affordability, fixed pre-dispatch limits, liquidity caps, fees and exits. Original forced-flow contract identity is preserved for an unchanged side; a flipped side uses the same ordinary option selector. This tests a specified counterfactual, not an exactly exchangeable pure direction null. Unknown paths stay unresolved. Rank bounds count all unresolved controls as below/above the baseline; they are **not population significance p-values**.','',
        '## Direct signal-versus-noise check','',
        'Primary horizon was fixed at 15 minutes before these calculations. Entry reference is the underlying open one full minute after signal time. All intervening bars must exist. Returns are signed by CE/PE direction, averaged within each trading day, then equally across dates. These are underlying price returns, not option P&L. Days are the sampling blocks; residual serial dependence across days remains a limitation.','',
        '| Bot | Signals / dates | Mean signed underlying return | 95% day-bootstrap interval | Raw p | Holm p (nine families) |',
        '|---|---:|---:|---:|---:|---:|']
    for r in rows:
        m=r['direction']
        if m['p'] is None:continue
        lines.append(f"| {r['engine']} | {m['observations']} / {m['days']} | {percent(m['mean_signed_return'])} | {percent(m['ci'][0])} to {percent(m['ci'][1])} | {m['p']:.4f} | {r['primary_holm_p']:.4f} |")
    lines+=['',
        'No primary test rejects the conditional sign-symmetry null at 5%. This is absence of convincing evidence for these signals, not proof that every related strategy is noise. The 5/30-minute sensitivity results are exported without choosing the best horizon. The Holm adjustment covers the nine named primary families; it cannot erase the earlier hypothesis/threshold search or turn this discovery sample into a holdout.','',
        '## Original filing-content extension','',
        f"Processed all **{docs['total']:,} collected relevant attachment references** (including malformed/missing references) rather than selecting documents by subsequent returns. Results: "+', '.join(f'{k}: {v:,}' for k,v in sorted(docs['counts'].items()))+'.',
        '',
        'The extractor reads original NSE PDFs and bounded PDF/XML ZIP members, preserving dissemination time and hashes. The predeclared category classifier covers results, business acquisitions, order wins, guidance, regulatory actions and management changes. A text category match is not a validated judgment of economic materiality. The collection includes the 33 additional subject categories frozen after the input inventory; remaining unselected administrative/reposted categories remain outside this variant. Missing, ambiguous, scanned or corrupt content remains UNKNOWN. Original attachment URLs plus dissemination times are the publication-vintage assumption; later archive replacement cannot be ruled out by today’s download alone.','',
        '| Content variant | Price candidates | Qualifying category candidates | Closed trades | Last resolved cash | Random rank | Path |',
        '|---|---:|---:|---:|---:|---:|---|']
    for x in extension['engines']:
        b=x['baseline'];rank=x['rank_bounds']
        comparison='Not rankable' if rank is None else f"{rank['lower']*100:.1f}–{rank['upper']*100:.1f}%"
        lines.append(f"| {x['engine']} | {x['signals']} | {x['materiality_counts'].get('QUALIFYING_TEXT',0)} | {b['trades']} | {money(b['last_resolved_cash'])} | {comparison} | {'Unresolved; not terminal equity' if b['stopped'] else 'Conditional only'} |")
    lines+=['','These two additional replays use unchanged price/execution thresholds. They are an information-coverage extension, not independent validation. Full chronological [content ledgers](content/ledgers/) retain losses, rejections and uncertainties.','',
        '## Tested scope and remaining requirements','',
        '| Bot | Actual implemented scope |','|---|---|']
    for r in rows:lines.append(f"| {r['engine']} | {r['scope']} |")
    lines+=['',
        'The remaining work is substantive data/validation work: resolve 2,188 uncertain option contract-days; obtain full family inputs for other index changes, scheduled events, block/OFS cases, external markets and BSE/MCX coverage; establish historical broker RMS and near-expiry delivery-margin eligibility; acquire timestamped indicative-index and bid/ask/depth data where those signals require it; validate unchanged rules on an untouched period. This report does not label that work complete.','',
        'Minute OHLCV cannot establish 1/3/5-second latency, displayed liquidity or queue fills. The seven-day stock expiry buffer changes the original near-expiry opportunity set; it is a declared conservative scope restriction, not proof that every nearer contract was prohibited. Dhan publishes pre-expiry delivery-margin requirements and expiry-day fresh stock-option restrictions in its [RMS policy](https://dhan.co/risk-management-policy/). NSE offers [historical order/trade data](https://www.nseindia.com/static/market-data/eod-historical-data-subscription); neither a current quote nor a daily CAS summary reconstructs those historical execution states.','',
        '## Reproducibility','',
        f'The accelerated simulator passed **{parity_cases} exact original baseline/seeded-reference comparisons**, plus **two content-variant comparisons** with the original full replay. Cash chronology and whole-lot execution were checked again when exporting the content ledgers. Source/input hashes are embedded in the JSON result; raw licensed market history remains in the ignored private cache. Fixtures validate software behavior, never profitability.','',
        '- [Machine-readable result](noise_audit.json)',
        '- [All 3,996 control paths](noise_paths.csv)',
        '- [All 1,998 content-variant control paths](content_noise_paths.csv)',
        '- [Directional tests and horizon sensitivities](directional_noise.csv)',
        '- [Every filing reference, classification and failure](filing_coverage.json)',
        '- [Every candidate classification/selection change](content_candidate_changes.json)',
        '- [Frozen audit protocol](../noise/PROTOCOL.md)','',
        'Run `.venv/bin/python -m research.noise.report` after completing the commands in [README.md](../README.md).']
    (OUT/'NOISE-AUDIT.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({'status':result['status'],'random_paths':5994,'filing_references':docs['total'],'winner':None}))

if __name__=='__main__':run()
