"""Date-verified NSE ban archive; missing never means an empty list."""
import csv,io,json
from datetime import date
from concurrent.futures import ThreadPoolExecutor,as_completed
import httpx
from research.gauntlet.data import CACHE,save
from research.event90.experiment import parse_ban
from .prepare import STORE,part,calendar

def main():
    out={}
    for p in (CACHE/'ban_lists.json',CACHE/'event90/ban_lists.json',STORE/'ban_lists.json'):
        if p.exists():out.update(json.loads(p.read_text()))
    todo=[d for d in calendar() if part(d) and out.get(d,{}).get('status')!='VERIFIED_DATE']
    def one(day):
        dt=date.fromisoformat(day);name=f'fo_secban_{dt:%d%m%Y}.csv';errors=[]
        dest=STORE/'ban_raw'/name;dest.parent.mkdir(parents=True,exist_ok=True)
        for p in (dest,CACHE/'public'/name,CACHE/'event90/public'/name):
            if p.exists():
                try:return day,{'status':'VERIFIED_DATE','symbols':parse_ban(p.read_text(),day)}
                except ValueError:pass
        for url,params in [('https://nsearchives.nseindia.com/content/fo/'+name,None),('https://www.nseindia.com/api/reports',{'archives':json.dumps([{'name':'F&O - Security in ban period','type':'archives','category':'derivatives','section':'equity'}]),'date':dt.strftime('%d-%b-%Y'),'type':'equity','mode':'single'})]:
            try:
                r=httpx.get(url,params=params,timeout=25,headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.nseindia.com/all-reports-derivatives'})
                if r.status_code!=200:raise ValueError('HTTP_'+str(r.status_code))
                names=parse_ban(r.text,day);dest.write_bytes(r.content)
                return day,{'status':'VERIFIED_DATE','symbols':names,'url':str(r.url)}
            except Exception as e:errors.append(str(e))
        return day,{'status':'UNKNOWN','errors':errors}
    with ThreadPoolExecutor(max_workers=4) as pool:
        for i,(d,r) in enumerate(pool.map(one,todo),1):
            out[d]=r
            if i%20==0:print('ban archives',i,'/',len(todo),flush=True)
    save(STORE/'ban_lists.json',out)
    print('ban unknown',[d for d in calendar() if part(d) and out.get(d,{}).get('status')!='VERIFIED_DATE'],flush=True)

if __name__=='__main__':main()
