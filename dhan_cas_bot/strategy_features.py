"""Bounded read-only auxiliary inputs with explicit receipt boundaries.

No optional source can poison unrelated strategy inputs. Provider failures are
absent features, never zero. Current IV is a current snapshot, not retroactive
minute IV. Published records and completed candles stay distinct.
"""
from datetime import datetime, timedelta
from decimal import Decimal as D
from csv import DictReader
from io import BytesIO, StringIO
from zipfile import ZipFile
from urllib.parse import quote
import asyncio
import httpx

from .session_strategies import IST, Bar, integral_number
from .domain import dec, ContractError


def index_inputs(payload):
    aliases={'BANK':'BANKNIFTY','IT':'NIFTYIT','VIX':'INDIA VIX'};result={}
    rows=list(DictReader(StringIO(payload.decode('utf-8-sig'))))
    for name,symbol in aliases.items():
        ids={r['SECURITY_ID'] for r in rows if r.get('EXCH_ID')=='NSE' and r.get('SEGMENT')=='I'
             and r.get('INSTRUMENT')=='INDEX' and r.get('UNDERLYING_SYMBOL')==symbol}
        if len(ids)==1:result[name]=ids.pop()
    return result


def parse_insights(raw,kind,received):
    if raw.get('status')!='success':raise ContractError('insight unavailable')
    result={};field='max_pain' if kind=='max-pain' else 'pcr'
    for row in (raw.get('data') or {}).get('insights',[]):
        clock=row['time'];day=received.astimezone(IST).date()
        at=datetime.fromisoformat(str(day)+'T'+clock+(':00' if len(clock)==5 else '')+'+05:30')+timedelta(minutes=5)
        value=dec(row[field],field)
        if at>received or value<=0:continue
        if at in result and result[at]!=value:raise ContractError('conflicting insight')
        result[at]=value
    return result


class FeatureSource:
    def __init__(self,broker,token,now):
        self.broker,self.token,self.now=broker,token,now
        self.cache={};self.retry_at={};self.daily=None

    async def upstox(self,path):
        if not self.token:raise ContractError('auxiliary authentication unavailable')
        async with httpx.AsyncClient(timeout=5,follow_redirects=False) as client:
            r=await client.get('https://api.upstox.com'+path,headers={'Authorization':'Bearer '+self.token})
            r.raise_for_status();raw=r.json(parse_float=D)
            if raw.get('status')!='success':raise ContractError('auxiliary data unavailable')
            return raw

    async def daily_values(self,now):
        if self.daily and self.daily[0]==now.date():return self.daily[1]
        raw=await self.broker._request('POST','/charts/historical',json={'securityId':'13','exchangeSegment':'IDX_I',
            'instrument':'INDEX','expiryCode':0,'oi':False,'fromDate':str(now.date()-timedelta(days=80)),
            'toDate':str(now.date())})
        stamps,closes=raw.get('timestamp'),raw.get('close')
        if not isinstance(stamps,list) or not isinstance(closes,list) or len(stamps)!=len(closes):raise ContractError('daily history unavailable')
        days={}
        for stamp,value in zip(stamps,closes):
            day=datetime.fromtimestamp(integral_number(stamp),IST).date();value=dec(value,'close')
            if day>=now.date() or value<=0:continue
            if day in days:raise ContractError('duplicate daily history')
            days[day]=value
        if len(days)<21:raise ContractError('prior trend history unavailable')
        self.daily=(now.date(),days);return days

    async def published_chain(self,calendar,expiry):
        day=calendar.previous_opens.date()
        url='https://nsearchives.nseindia.com/content/fo/BhavCopy_NSE_FO_0_0_0_'+day.strftime('%Y%m%d')+'_F_0000.csv.zip'
        async with httpx.AsyncClient(timeout=12,follow_redirects=False) as client:
            r=await client.get(url,headers={'User-Agent':'Mozilla/5.0','Accept':'application/zip,application/octet-stream,*/*'});r.raise_for_status()
            if len(r.content)>30_000_000:raise ContractError('published chain too large')
        with ZipFile(BytesIO(r.content)) as archive:
            files=[x for x in archive.infolist() if x.filename.endswith('.csv')]
            if len(files)!=1 or files[0].file_size>100_000_000:raise ContractError('invalid published chain archive')
            rows=list(DictReader(StringIO(archive.read(files[0]).decode('utf-8-sig'))))
        rows=[x for x in rows if x.get('FinInstrmTp')=='IDO' and x.get('TckrSymb')=='NIFTY'
              and (x.get('FininstrmActlXpryDt') or x.get('XpryDt'))==str(expiry)]
        oi={};old={'CE':0,'PE':0};total={'CE':0,'PE':0}
        for row in rows:
            side=row['OptnTp'];strike=dec(row['StrkPric'],'strike')
            value=dec(row['OpnIntrst'],'oi');change=dec(row['ChngInOpnIntrst'],'oi change')
            if side not in total or value<0 or value-change<0 or (side,strike) in oi:raise ContractError('invalid published chain')
            oi[side,strike]=int(value);total[side]+=value;old[side]+=value-change
        if min(*total.values(),*old.values())<=0:raise ContractError('published chain incomplete')
        strikes=sorted({k for _,k in oi})
        liability=lambda k:sum(value*max(D(0),k-strike if side=='CE' else strike-k) for (side,strike),value in oi.items())
        return {'received_at':self.now(),'source_date':day,'expiry':expiry,'oi':oi,
                'pcr_change':(total['PE']/total['CE'])/(old['PE']/old['CE'])-1,
                'max_pain':min(strikes,key=lambda k:(liability(k),k))}

    async def refresh(self,now,calendar,expiry,families):
        result={}
        async def collect(key,fn,ttl):
            stamp=self.now();cached=self.cache.get(key)
            if cached and cached[0]==now.date() and (stamp-cached[1]).total_seconds()<ttl:
                result[key]=cached[2];return
            if stamp<self.retry_at.get(key,stamp):return
            try:
                value=await fn();self.cache[key]=(now.date(),self.now(),value);result[key]=value
                self.retry_at.pop(key,None)
            except Exception:
                # Capped backoff, no raw response or secret enters runtime/UI.
                self.retry_at[key]=stamp+timedelta(minutes=5 if ttl<3600 else 15)
        async def iv():
            raw=await self.broker._request('POST','/optionchain',json={'UnderlyingScrip':13,'UnderlyingSeg':'IDX_I','Expiry':str(expiry)})
            values={}
            for strike,row in (raw.get('data') or {}).get('oc',{}).items():
                values[dec(strike,'strike')]={s:dec(row[s.lower()]['implied_volatility'],'iv') for s in ('CE','PE') if row.get(s.lower())}
            if not values:raise ContractError('IV unavailable')
            return {'received_at':self.now(),'expiry':expiry,'values':values}
        async def insights():
            result={'received_at':self.now()}
            for kind in ('pcr','max-pain'):
                raw=await self.upstox('/v2/market/'+kind+'?instrument_key=NSE_INDEX%7CNifty%2050&expiry='+str(expiry)+'&date='+str(now.date())+'&bucket_interval=5')
                result[kind]=parse_insights(raw,kind,self.now())
            result['received_at']=self.now()
            if not any(result[k] for k in ('pcr','max-pain')):raise ContractError('insight buckets unavailable')
            return result
        async def trend():
            days=await self.daily_values(now);keys=sorted(days)
            return {'received_at':self.now(),'source_date':keys[-1],'value':days[keys[-1]]/days[keys[-21]]-1}
        async def institutions():
            days=sorted(d for d in await self.daily_values(now) if d<=calendar.previous_opens.date())
            if len(days)<3 or days[-1]!=calendar.previous_opens.date():raise ContractError('institutional session history unavailable')
            day,previous=days[-2],days[-3];rows={}
            for kind,domain in (('fii','NSE_FO|INDEX_FUTURES'),('dii','NSE_EQ|CASH')):
                # The live endpoint's `from` is its newest-row anchor, not an
                # inclusive earliest date. Anchor today, then deliberately use
                # only the two-session-lagged publication rows below.
                raw=await self.upstox('/v2/market/'+kind+'?data_type='+quote(domain,safe='')+'&interval=1D&from='+str(now.date()))
                out={}
                for batch in (raw.get('data') or {}).values():
                    for row in batch:
                        source=datetime.fromtimestamp(integral_number(row['time_stamp'])/1000,IST).date()
                        if source<=day:out[source]=row
                rows[kind]=out
            f,p,di=rows['fii'][day],rows['fii'][previous],rows['dii'][day]
            return {'received_at':self.now(),'source_date':day,
                    'fii_net_change':dec(f['total_long_contracts'],'long')-dec(f['total_short_contracts'],'short')-dec(p['total_long_contracts'],'long')+dec(p['total_short_contracts'],'short'),
                    'dii_net':dec(di['buy_amount'],'buy')-dec(di['sell_amount'],'sell')}
        if 'IV_CHEAP_TREND' in families:await collect('iv',iv,45)
        if families&{'PCR_CONFIRM','PAIN_ESCAPE'}:await collect('insights',insights,60)
        if families&{'PUBLISHED_PCR','PUBLISHED_PAIN','PRIOR_OI_WALL'}:await collect('prior_chain',lambda:self.published_chain(calendar,expiry),3600*12)
        if families&{'NIFTY_DAY_CONTINUATION','NIFTY_TREND_ALIGNMENT','TREND_CONTINUATION','TREND_PULLBACK'}:await collect('prior_trend',trend,3600*12)
        if 'INSTITUTIONAL_ALIGN' in families:await collect('institutions',institutions,3600*12)
        return result

    async def gift(self,now):
        # This provider instrument is delayed; rule uses an additional two-
        # minute lag. Never label it a zero-latency cross-market arbitrage.
        raw=await self.upstox('/v3/historical-candle/intraday/'+quote('GLOBAL_INDEX|SGX NIFTY',safe='')+'/minutes/1')
        out={}
        for row in (raw.get('data') or {}).get('candles',[]):
            start=datetime.fromisoformat(row[0]);at=start+timedelta(minutes=1)
            if start.tzinfo is None or at>now:continue
            op,hi,lo,close=[dec(row[i],'candle') for i in (1,2,3,4)]
            if min(op,hi,lo,close)<=0 or not lo<=min(op,close)<=max(op,close)<=hi or at in out:raise ContractError('invalid auxiliary candle')
            out[at]=Bar(at,op,close,integral_number(row[5]),0,hi,lo)
        return out
