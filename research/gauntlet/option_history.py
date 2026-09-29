"""Batch exact-contract history across days, preserving point-in-time replay.

Downloading later bars is allowed; exposing them to a decision is not. Each
stored day is served separately by contracts.instrument_bars and then sliced
by core.snapshot. This reduces repeated requests, not the tested universe.
"""
import argparse
import hashlib
import json
from collections import defaultdict
from datetime import date,timedelta
from pathlib import Path
from .data import CACHE,candles,save
from .core import Bar

def day_path(key,day):
    return CACHE/'option_days'/hashlib.sha256(key.encode()).hexdigest()/(day+'.json')

def plan_ranges(jobs,max_days=28):
    grouped=defaultdict(set)
    for job in jobs:grouped[job['contract_key']].add(job['day'])
    plans=[]
    for key,days in sorted(grouped.items()):
        block=[]
        for day in sorted(days):
            if block and (date.fromisoformat(day)-date.fromisoformat(block[0])).days>=max_days:
                plans.append({'key':key,'days':block});block=[]
            block.append(day)
        if block:plans.append({'key':key,'days':block})
    return plans

def split_rows(rows,days):
    byday={day:{} for day in days}
    for row in rows:
        b=Bar.parse(row);day=b.start.date().isoformat()
        if day not in byday:continue
        existing=byday[day].get(row[0])
        if existing is not None and existing!=row:raise ValueError('conflicting duplicate option bar')
        byday[day][row[0]]=row
    return {day:[row for _,row in sorted(values.items())] for day,values in byday.items()}

def fetch_range(plan):
    key=plan['key'];days=plan['days']
    if all(day_path(key,d).exists() for d in days):return 0
    rows=candles(key,days[0],days[-1],len(key.split('|'))==3)
    split=split_rows(rows,days)
    for day,values in split.items():
        save(day_path(key,day),{'key':key,'day':day,'requested_start':days[0],
                              'requested_end':days[-1],'bars':values,'status':'DOWNLOADED' if values else 'EMPTY_RESPONSE'})
    return 1

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--limit',type=int,default=100);a=p.parse_args()
    jobs=json.loads((CACHE/'nonexpiry_jobs.json').read_text());plans=plan_ranges(jobs)
    save(CACHE/'option_range_plan.json',plans)
    print('contract_days',len(jobs),'batched_requests',len(plans),flush=True)
    count=0
    for plan in plans:
        if count>=a.limit:break
        count+=fetch_range(plan)
        if count and count%10==0:print('ranges_fetched',count,flush=True)
