#!/usr/bin/env python3
"""Read the allowlisted operational report; no broker calls or state writes."""
import argparse,json,sys
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from dhan_cas_bot.dashboard.collect import operations_view
from dhan_cas_bot.dashboard.data import freshness

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--json',action='store_true')
 parser.add_argument('--snapshot',default='/var/lib/sablestone-dhan-dashboard/snapshot.json')
 args=parser.parse_args();now=datetime.now(timezone.utc)
 value=operations_view(args.snapshot,now)
 current=value.get('status')=='AVAILABLE' and freshness(value.get('observed_at'),now,20)['fresh']
 report={'schema':1,'checked_at':now.isoformat(),'current':current,'operations':value}
 print(json.dumps(report,sort_keys=True))
 return 0 if current else 2
if __name__=='__main__':raise SystemExit(main())
