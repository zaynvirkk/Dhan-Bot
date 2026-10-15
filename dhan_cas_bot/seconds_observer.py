"""Live quote experiments with paper fills only; no order client or write rail."""
import argparse,asyncio,csv,io,json,os,signal,tempfile,time
from dataclasses import asdict
from datetime import datetime,timezone
from decimal import Decimal as D
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlencode
import httpx

from .config import load_config
from .dashboard.collect import atomic_json
from .dashboard.data import read_json,shared_account,timestamp
from .dhan_feed import packets,decode_full_binary,book_from_packet
from .domain import Segment,json_safe
from .feeds import DhanMarketClient
from .rules import RuleSource,DHAN_MASTER_URL,NSE_FREEZE_URL
from .strategy_inputs import selected_contracts
from .session_strategies import IST
from .seconds_strategies import NAMES,SecondsTape,ns,entry_candidate,future_quote_mid
from .seconds_events import watch_events
from .seconds_paper import PaperLab
from .transport import WebSocketRunner,message_received_ns


class ObserverInputError(ValueError):
    pass


async def fetch_nifty_master(*, client=None, max_bytes=256*1024*1024):
    """Spool the exchange-wide CSV to disk; retain only NIFTY rows in memory."""
    own=client is None
    client=client or httpx.AsyncClient(timeout=15,follow_redirects=True)
    try:
        with tempfile.TemporaryFile(mode='w+b') as source:
            size=0
            async with client.stream('GET',DHAN_MASTER_URL,headers={'User-Agent':'sablestone-dhan-cas/0.1'}) as response:
                response.raise_for_status()
                async for chunk in response.aiter_bytes():
                    size+=len(chunk)
                    if size>max_bytes:raise ValueError('instrument source exceeds bounded size')
                    source.write(chunk)
            source.seek(0)
            text=io.TextIOWrapper(source,encoding='utf-8-sig',newline='')
            rows=csv.DictReader(text)
            if not {'SEGMENT','INSTRUMENT','UNDERLYING_SYMBOL','SECURITY_ID'}<=set(rows.fieldnames or ()):
                raise ValueError('instrument source missing required columns')
            output=io.StringIO();writer=csv.DictWriter(output,fieldnames=rows.fieldnames)
            writer.writeheader()
            for row in rows:
                if (row.get('UNDERLYING_SYMBOL')=='NIFTY' and row.get('INSTRUMENT') in ('OPTIDX','FUTIDX')
                        and (row.get('SEGMENT')=='NSE_FNO' or (row.get('EXCH_ID')=='NSE' and row.get('SEGMENT')=='D'))):
                    writer.writerow(row)
            return output.getvalue().encode('utf-8')
    finally:
        if own:await client.aclose()


class ObservedCalendar:
    def __init__(self,raw):
        self.opens=datetime.fromisoformat(timestamp(raw.get('session_open')))
        self.closes=datetime.fromisoformat(timestamp(raw.get('session_close')))
        self.checked=datetime.fromisoformat(timestamp(raw.get('calendar_checked_at')))
        if self.opens>=self.closes:raise ValueError('invalid calendar')
    def fresh(self,now):return 0<=(now-self.checked).total_seconds()<=3600 and self.opens.astimezone(IST).date()==now.astimezone(IST).date()
    def is_open(self,now):return self.fresh(now) and self.opens<=now<self.closes


async def run(config, output, stop):
    root=Path(output).parent;state=Path(config['state_dir']);now=datetime.now(timezone.utc)
    session_day=now.astimezone(IST).date()
    cached=read_json(state/'dhan_token.json')
    if not cached or cached.get('account')!=config['account_id']:raise ObserverInputError('SESSION_TOKEN_UNAVAILABLE')
    shared=shared_account(read_json(state/'account-observation.json'),now)
    if not shared or not shared.get('account_read_ok') or not shared.get('account'):raise ObserverInputError('STARTING_CASH_UNAVAILABLE')
    cash=D(shared['account']['available_cash'])
    raw_state=read_json(root/'seconds-paper-state.json')
    if raw_state is None and (root/'seconds-paper-state.json').exists():raise ObserverInputError('PAPER_HISTORY_UNAVAILABLE')
    lab=PaperLab(cash,saved=raw_state)
    token=cached['token']
    try:master,freeze=await asyncio.gather(fetch_nifty_master(),RuleSource(timeout=15).fetch(NSE_FREEZE_URL))
    except Exception as exc:raise ObserverInputError('CONTRACT_METADATA_UNAVAILABLE') from exc
    insts,future_id=selected_contracts(master,RuleSource.parse_freeze(freeze.payload),now.astimezone(IST).date())
    status=read_json(state/'status.json') or {};anchor=(status.get('observation') or {}).get('ltp')
    if not anchor or not future_id:raise ObserverInputError('MARKET_ANCHOR_UNAVAILABLE')
    expiry=min(i.expiry for i in insts)
    chosen=sorted((i for i in insts if i.expiry==expiry),key=lambda i:(abs(i.strike-D(str(anchor))),i.security_id))[:24]
    instruments={i.security_id:i for i in chosen};books={};tape=SecondsTape()
    events=SimpleNamespace(event=None,event_health={'state':'UNAVAILABLE','reason':'EVENT_FEED_UNAVAILABLE'})
    market=DhanMarketClient(token);seen={};recorded={};last_write=0;last_archive=0;last_save=0
    future_ref=SimpleNamespace(security_id=future_id,tick_size=D('.05'),segment=Segment.NSE_FNO)
    async def receive(payload):
        received=message_received_ns(time.time_ns());epoch=market.protocol.epoch.id
        if not market.protocol.epoch.connected:return
        try:batch=list(packets(payload))
        except Exception:tape.reset();books.clear();return
        for packet in batch:
            security=str(int.from_bytes(packet[4:8],'little'))
            if packet[0]!=8:continue
            try:
                if security==future_id:
                    if seen.get(security)==packet:continue
                    tick=decode_full_binary(packet,future_ref)
                    mid=future_quote_mid(tick)
                    seen[security]=packet
                    tape.future_tick(mid,received,epoch)
                elif security in instruments:
                    if seen.get(security)==packet:continue
                    tick=decode_full_binary(packet,instruments[security]);seen[security]=packet
                    books[security]=book_from_packet(tick,instruments[security],epoch,received)
            except Exception:
                if security==future_id:tape.reset()
                books.pop(security,None)
    def connect():market.protocol.on_connect();tape.reset();books.clear();seen.clear()
    def disconnect():market.protocol.on_disconnect();tape.reset();books.clear();seen.clear()
    url='wss://api-feed.dhan.co?'+urlencode({'version':'2','token':token,'clientId':config['account_id'],'authType':'2'})
    runner=WebSocketRunner(url,{},receive,subscribe=market.subscription_messages([*instruments,future_id]),on_connect=connect,on_disconnect=disconnect)
    tasks=[asyncio.create_task(runner.run()),asyncio.create_task(watch_events(events,stop))]
    archive=root/('seconds-quotes-'+now.astimezone(IST).date().isoformat()+'.jsonl')
    try:
        while not stop.is_set():
            now=datetime.now(timezone.utc)
            if now.astimezone(IST).date()!=session_day:return
            for task in tasks:
                if task.done():task.result();raise RuntimeError('required observer stopped')
            try:calendar=ObservedCalendar(read_json(root/'daily-monitor.json') or {})
            except (TypeError,ValueError):calendar=None
            samples=tape.evaluate(now,books,(),calendar,event=events.event,budget=max(D(r['cash']) for r in lab.rows.values())*D('.95'))
            for name,row in lab.rows.items():
                budget=D(row['cash'])*D('.95')
                if samples[name].state=='SIGNAL' and not row['position'] and entry_candidate(samples[name],books,budget,now) is None:
                    samples[name]=tape.evaluate(now,books,(),calendar,event=events.event,budget=budget)[name]
            if samples[NAMES[4]].reason=='EVENT_FEED_UNAVAILABLE' and events.event_health['state']=='CONNECTED':
                from dataclasses import replace
                samples[NAMES[4]]=replace(samples[NAMES[4]],state='WAITING',reason='NO_FRESH_EVENT')
            future=tape.future[-1][1] if tape.future and 0<=ns(now)-tape.future[-1][0]<=1_500_000_000 else None
            lab.step(now,samples,books,future)
            if time.monotonic()-last_write>=1:
                report={**lab.view(),'schema':1,'observed_at':now.isoformat(),'feed_connected':market.protocol.epoch.connected,
                    'future_current':future is not None,'options_observed':len(books),'event_feed':events.event_health,
                    'evaluations':json_safe([asdict(samples[n]) for n in NAMES]),
                    'quote_sample_interval_ms':500,
                    'quote_archive_within_cap':archive.stat().st_size<128*1024*1024 if archive.exists() else True}
                atomic_json(output,report);last_write=time.monotonic()
            if time.monotonic()-last_save>=2:
                atomic_json(root/'seconds-paper-state.json',lab.saved());last_save=time.monotonic()
            if time.monotonic()-last_archive>=.5 and (not archive.exists() or archive.stat().st_size<128*1024*1024):
                rows=[]
                if tape.future:rows.append({'kind':'future','at_ns':tape.future[-1][0],'price':str(tape.future[-1][1])})
                for b in books.values():
                    if b.received_ns<=recorded.get(b.instrument.security_id,0):continue
                    recorded[b.instrument.security_id]=b.received_ns
                    rows.append({'kind':'option','security_id':b.instrument.security_id,'at_ns':b.received_ns,
                        'bid':[[str(l.price),l.quantity] for l in b.bids],
                        'ask':[[str(l.price),l.quantity] for l in b.asks],
                        'volume':b.statistics.volume if b.statistics else None})
                with archive.open('a') as stream:
                    for row in rows:stream.write(json.dumps(row,separators=(',',':'))+'\n')
                last_archive=time.monotonic()
            await asyncio.sleep(.25)
    finally:
        atomic_json(root/'seconds-paper-state.json',lab.saved())
        for task in tasks:task.cancel()
        await asyncio.gather(*tasks,return_exceptions=True)


async def main_async(config,output):
    stop=asyncio.Event();loop=asyncio.get_running_loop()
    for sig in (signal.SIGTERM,signal.SIGINT):loop.add_signal_handler(sig,stop.set)
    while not stop.is_set():
        try:await run(config,output,stop)
        except Exception as exc:
            atomic_json(output,{'schema':1,'mode':'SIMULATION','writes_to_broker':False,
                'observed_at':datetime.now(timezone.utc).isoformat(),'status':'UNAVAILABLE','error':type(exc).__name__,
                'reason':str(exc) if isinstance(exc,ObserverInputError) else 'OBSERVER_FAILED'})
            try:await asyncio.wait_for(stop.wait(),30)
            except asyncio.TimeoutError:pass


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',default='/etc/sablestone-dhan/production.toml')
    parser.add_argument('--output',default='/var/lib/sablestone-dhan-dashboard/seconds-strategies.json')
    args=parser.parse_args();asyncio.run(main_async(load_config(args.config),args.output))


if __name__=='__main__':main()
