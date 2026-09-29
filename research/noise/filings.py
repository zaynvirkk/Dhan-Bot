"""Read every relevant primary attachment; no outcome-selected document sample."""
import hashlib,json,re,subprocess,threading,time,zipfile
from xml.etree import ElementTree
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from urllib.parse import urlsplit
import httpx
from research.gauntlet.data import CACHE,save
from research.gauntlet.signals import announcement_records
from research.gauntlet.provenance import digest
from research.noise.compile import NOISE
from research.noise.universe import relevant

LOCK=threading.Lock();NEXT=0.
PATTERNS={
 'FINANCIAL_RESULTS':r'(?:unaudited|audited|financial)\s+(?:standalone\s+and\s+consolidated\s+)?(?:financial\s+)?results|statement\s+of\s+(?:standalone|consolidated).*?results',
 'BUSINESS_ACQUISITION':r'(?:acquisition|acquire|merger|amalgamation).{0,180}(?:business|subsidiar|company|companies|enterprise|undertaking)|(?:business|subsidiar).{0,100}(?:acquisition|acquire)',
 'ORDER_WIN':r'(?:award|receipt|receiving|bagging|secured|securing).{0,100}(?:order|contract)|(?:order|contract).{0,100}(?:awarded|received|secured)',
 'GUIDANCE':r'(?:revenue|margin|profit|earnings|growth).{0,80}(?:guidance|outlook)|(?:guidance).{0,80}(?:revenue|margin|profit|earnings|growth)',
 'REGULATORY_ACTION':r'(?:regulatory|sebi|rbi|tribunal|court).{0,100}(?:penalty|order|approval|prohibit|suspend)|(?:penalty|suspension).{0,100}(?:regulatory|sebi|rbi)',
 'MANAGEMENT_CHANGE':r'(?:resignation|appointment|cessation).{0,100}(?:chief|managing director|key managerial|senior management|\bkmp\b|\bcfo\b|\bceo\b)',
}
OWNERSHIP=re.compile(r'disclosur.{0,100}(?:regulation\s*29|regulation\s*31|substantial acquisition of shares|prohibition of insider trading)|format.{0,80}(?:regulation\s*29|sast)',re.I|re.S)

def classify(text):
    body=' '.join(text.split())
    if len(body)<150:return {'status':'UNKNOWN_UNREADABLE','categories':[]}
    ownership=bool(OWNERSHIP.search(body[:10000]))
    categories=[];evidence={}
    for category,pattern in PATTERNS.items():
        if category=='BUSINESS_ACQUISITION' and ownership:continue
        match=re.search(pattern,body,re.I)
        if match:categories.append(category);evidence[category]=body[max(0,match.start()-60):match.end()+60]
    if categories:return {'status':'CATEGORY_MATCH','categories':categories,'evidence':evidence,'ownership_notice':ownership}
    return {'status':'OWNERSHIP_NOTICE' if ownership else 'UNKNOWN_MATERIALITY','categories':[]}

def extract(rawfile,txt):
    """Never extract archive paths; process bounded PDF/XML members by index."""
    if not zipfile.is_zipfile(rawfile):
        subprocess.run(['pdftotext','-layout',str(rawfile),str(txt)],check=True,timeout=40,
                       stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        return txt.read_text(errors='replace'),[]
    parts=[];errors=[]
    with zipfile.ZipFile(rawfile) as archive:
        members=archive.infolist()
        if len(members)>100 or sum(m.file_size for m in members)>64*1024*1024:
            raise ValueError('Archive exceeds extraction bound')
        for i,member in enumerate(members):
            if member.is_dir():continue
            try:
                blob=archive.read(member)
                if member.filename.lower().endswith('.xml'):
                    root=ElementTree.fromstring(blob);parts.append(' '.join(root.itertext()))
                elif blob.startswith(b'%PDF'):
                    part=rawfile.parent/(rawfile.stem+f'_{i}.pdf')
                    parttxt=txt.parent/(txt.stem+f'_{i}.txt')
                    part.write_bytes(blob)
                    body,_=extract(part,parttxt);parts.append(body)
                else:errors.append({'member':member.filename,'reason':'UNSUPPORTED_MEMBER'})
            except Exception as e:errors.append({'member':member.filename,'reason':type(e).__name__})
    body='\n'.join(parts);txt.write_text(body)
    return body,errors

def fetch(job):
    global NEXT
    url,events=job;key=hashlib.sha256(url.encode()).hexdigest();file=NOISE/'filings'/(key+'.json')
    previous={}
    if file.exists():
        x=json.loads(file.read_text())
        if x.get('classifier_sha')==digest(__file__):return x
        previous=x
    rawfile=NOISE/'filings_raw'/(key+('.zip' if urlsplit(url).path.lower().endswith('.zip') else '.pdf'))
    txt=NOISE/'filings_text'/(key+'.txt')
    for folder in (rawfile.parent,txt.parent):folder.mkdir(parents=True,exist_ok=True)
    x={'url':url,'events':events,'classifier_sha':digest(__file__)}
    try:
        if urlsplit(url).hostname not in ('nsearchives.nseindia.com','archives.nseindia.com'):
            raise ValueError('Attachment host outside original exchange allowlist')
        if not rawfile.exists():
            with LOCK:delay=max(0,NEXT-time.monotonic());NEXT=max(NEXT,time.monotonic())+.5
            if delay:time.sleep(delay)
            response=httpx.get(url,timeout=35,follow_redirects=False,
                               headers={'User-Agent':'Mozilla/5.0','Accept':'*/*'})
            x['http_status']=response.status_code
            if response.status_code!=200:raise ValueError('HTTP '+str(response.status_code))
            if not response.content.startswith((b'%PDF',b'PK\x03\x04')):raise ValueError('Not PDF or ZIP')
            rawfile.write_bytes(response.content)
        if (txt.exists() and previous.get('raw_sha')==digest(rawfile)
                and previous.get('text_sha')==digest(txt)):
            body=txt.read_text(errors='replace');errors=previous.get('unreadable_members',[])
        else:body,errors=extract(rawfile,txt)
        x.update(classify(body));x.update(raw_sha=digest(rawfile),text_sha=digest(txt),characters=len(body))
        if errors:x['unreadable_members']=errors
    except Exception as e:x.update(status='UNKNOWN_DOCUMENT',error=type(e).__name__+':'+str(e))
    x['retrieved_at']=datetime.now(timezone.utc).isoformat();save(file,x);return x

def run(workers=10):
    from collections import defaultdict,Counter
    keys=json.loads((CACHE/'keys.json').read_text());jobs=defaultdict(list)
    for symbol,rows in announcement_records().items():
        if symbol not in keys:continue
        for r in rows:
            if relevant(r) and r['url']:
                jobs[r['url']].append({'symbol':symbol,'id':r['id'],'available_at':r['at'].isoformat(),
                    'metadata_category':r['category'],'metadata_quality':r['quality']})
    counts=Counter();out=[]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for i,x in enumerate(pool.map(fetch,sorted(jobs.items())),1):
            counts[x['status']]+=1;out.append(x)
            if i%50==0:
                print('FILINGS',i,'/',len(jobs),dict(counts),flush=True)
                save(NOISE/'filings_progress.json',{'complete':i,'total':len(jobs),'counts':dict(counts)})
    from research.noise import universe
    save(NOISE/'filings.json',{'records':out,'counts':dict(counts),'total':len(jobs),
        'classifier_sha':digest(__file__),'universe_sha':digest(universe.__file__)})
    print('FILINGS_FINISHED',len(jobs),dict(counts),flush=True)

if __name__=='__main__':run()
