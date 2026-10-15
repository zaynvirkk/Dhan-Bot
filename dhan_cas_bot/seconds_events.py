"""Read-only official filing observations; publication is never receipt time."""
import asyncio
from csv import DictReader
from datetime import datetime, timezone
from io import StringIO
import re

import httpx

from .session_strategies import IST

MEMBERS='https://archives.nseindia.com/content/indices/ind_nifty50list.csv'
FILINGS='https://www.nseindia.com/api/corporate-announcements'
SUBJECTS=('financial results','acquisition','buyback','merger','de-merger','demerger',
          'change in management','regulatory','litigation','fraud','default','dividend')


def member_symbols(text):
    symbols={str(r.get('Symbol','')).strip() for r in DictReader(StringIO(text))}
    if not 40<=len(symbols)<=60 or any(not re.fullmatch('[A-Z0-9&-]{1,32}',s) for s in symbols):
        raise ValueError('invalid current NIFTY membership')
    return symbols


def latest_event(rows, members, received):
    if not isinstance(rows,list) or len(rows)>20000:raise ValueError('invalid filing feed')
    accepted=[]
    for row in rows:
        if not isinstance(row,dict) or row.get('symbol') not in members:continue
        subject=str(row.get('desc','')).lower()
        if not any(s in subject for s in SUBJECTS):continue
        try:
            published=datetime.strptime(row['an_dt'],'%d-%b-%Y %H:%M:%S').replace(tzinfo=IST)
            source=row['attchmntFile']
            if not source.startswith('https://nsearchives.nseindia.com/'):continue
            if not 0<=(received-published).total_seconds()<=60:continue
            accepted.append({'published_at':published.isoformat(),'received_at':received.isoformat(),
                             'source_url':source,'underlying':'NIFTY','symbol':row['symbol']})
        except (ValueError,TypeError,KeyError,AttributeError):continue
    return max(accepted,key=lambda r:r['published_at']) if accepted else None


async def watch_events(consumer, stop):
    """No broker/account client, no secrets, no direction from announcement text."""
    members=None;member_day=None;seen=set()
    async with httpx.AsyncClient(timeout=8,follow_redirects=True,
            headers={'User-Agent':'Mozilla/5.0','Accept':'application/json,text/csv,*/*',
                     'Referer':'https://www.nseindia.com/companies-listing/corporate-filings-announcements'}) as client:
        while not stop.is_set():
            now=datetime.now(timezone.utc);day=now.astimezone(IST).date()
            try:
                if members is None or member_day!=day:
                    response=await client.get(MEMBERS);response.raise_for_status()
                    members=member_symbols(response.text);member_day=day;seen.clear()
                    await client.get('https://www.nseindia.com/')
                response=await client.get(FILINGS,params={'index':'equities','from_date':day.strftime('%d-%m-%Y'),'to_date':day.strftime('%d-%m-%Y')})
                response.raise_for_status();received=datetime.now(timezone.utc)
                event=latest_event(response.json(),members,received)
                consumer.event_health={'state':'CONNECTED','observed_at':received.isoformat(),'reason':'NO_FRESH_EVENT'}
                if event:
                    identity=(event['symbol'],event['published_at'],event['source_url'])
                    if identity not in seen:
                        seen.add(identity);consumer.event=event
            except Exception as exc:
                consumer.event_health={'state':'UNAVAILABLE','observed_at':datetime.now(timezone.utc).isoformat(),
                                       'reason':'EVENT_SOURCE_UNAVAILABLE','error':type(exc).__name__}
            try:await asyncio.wait_for(stop.wait(),10 if consumer.event_health['state']=='CONNECTED' else 30)
            except asyncio.TimeoutError:pass
