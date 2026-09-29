"""Hash the completed research dataset, excluding authentication/account files."""
import hashlib
import json
from datetime import datetime, timezone
from research.gauntlet.data import CACHE, ROOT, save

FOLDERS=('public','upstox','option_days','underlying','futures','dhan_history',
         'nonexpiry_reconciled')
FILES=('universe.json','keys.json','cash_closes.json','ban_lists.json',
       'event_candidates.json','event_gaps.json','leadlag_candidates.json','leadlag_models.json',
       'nonexpiry_jobs.json','nonexpiry_candidates.json','nonexpiry_scan.json',
       'nonexpiry_reconciliation.json','expiry_candidates.json','expiry_scan.json',
       'passive_candidates.json','passive_scan.json','scheduled_candidates.json','scheduled_scan.json',
       'ofs_candidates.json','ofs_scan.json','cross_broker_audit.json',
       'forced_cross_broker_conditions.json')

def main():
    suite=json.loads((CACHE/'suite_progress.json').read_text())
    if suite['status']!='COMPLETED_DISCOVERY_SWEEP':
        raise RuntimeError('Snapshot after all model runs finish')
    paths=[p for folder in FOLDERS for p in (CACHE/folder).rglob('*') if p.is_file()]
    paths += [CACHE/name for name in FILES]
    manifest={}
    for p in sorted(paths):
        h=hashlib.sha256()
        with p.open('rb') as f:
            for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
        manifest[str(p.relative_to(CACHE))]={'sha256':h.hexdigest(),'bytes':p.stat().st_size}
    body=json.dumps(manifest,sort_keys=True,separators=(',',':')).encode()
    result={'created_at':datetime.now(timezone.utc).isoformat(),
            'meaning':'Post-run dataset snapshot; not a claim of an atomic per-run market-data lock.',
            'sha256':hashlib.sha256(body).hexdigest(),'files':manifest}
    save(CACHE/'dataset_snapshot.json',result)
    summary={k:v for k,v in result.items() if k!='files'}
    summary.update(file_count=len(manifest),bytes=sum(v['bytes'] for v in manifest.values()))
    save(ROOT/'research/results/dataset_snapshot.json',summary)
    print(json.dumps(summary))

if __name__=='__main__':main()
