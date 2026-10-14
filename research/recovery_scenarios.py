"""Underlying recovery analogues; deliberately not an option-profit forecast."""
import argparse,hashlib,json,math
from collections import defaultdict
from datetime import datetime,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

IST=ZoneInfo('Asia/Kolkata')


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--at',required=True);p.add_argument('--cutoff',required=True)
    p.add_argument('--move',type=float,required=True);p.add_argument('--spot',type=float,required=True)
    p.add_argument('--as-of',required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();source=Path('artifacts/private/gauntlet/multifeature90/indexes/NIFTY.json')
    raw=source.read_bytes();by=defaultdict(dict)
    for row in json.loads(raw)['bars']:
        stamp=datetime.fromisoformat(row[0]).astimezone(IST)
        by[stamp.date()][stamp]=row
    threshold=a.move/a.spot;records=[];missing=0
    for day,rows in sorted(by.items()):
        if day.isoformat()>=a.as_of:continue
        origin=datetime.fromisoformat(day.isoformat()+'T'+a.at).replace(tzinfo=IST)
        cutoff=datetime.fromisoformat(day.isoformat()+'T'+a.cutoff).replace(tzinfo=IST)
        baseline=rows.get(origin-timedelta(minutes=1))
        old15=rows.get(origin-timedelta(minutes=16));old30=rows.get(origin-timedelta(minutes=31))
        required=[origin+timedelta(minutes=i) for i in range(int((cutoff-origin).total_seconds()/60))]
        if not baseline or not old15 or not old30 or any(t not in rows for t in required):missing+=1;continue
        close=float(baseline[4]);hit=max(float(rows[t][2]) for t in required)/close-1>=threshold
        records.append({'hit':hit,'ret15':close/float(old15[4])-1,'ret30':close/float(old30[4])-1})
    def summary(records):
        n=len(records);k=sum(r['hit'] for r in records)
        if not n:return {'sessions':0,'fraction':None}
        z=1.96;fraction=k/n;den=1+z*z/n
        centre=(fraction+z*z/(2*n))/den
        half=z*math.sqrt(fraction*(1-fraction)/n+z*z/(4*n*n))/den
        return {'sessions':n,'reached_underlying_rebound':k,'fraction':fraction,
            'rough_wilson95':[centre-half,centre+half]}
    out={'parameters':vars(a)|{'output':str(a.output)},'input_sha256':hashlib.sha256(raw).hexdigest(),
        'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'target_return':threshold,'missing_sessions':missing,'all':summary(records),
        '15m_down_30m_up':summary([r for r in records if r['ret15']<0 and r['ret30']>0]),
        'limits':'Underlying high touches only, not executable option profits. No IV/theta/queue model or regime calibration; interval is descriptive, not a predictive confidence bound.'}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps(out))


if __name__=='__main__':main()
