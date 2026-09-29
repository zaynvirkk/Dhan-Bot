"""Download a named public source and preserve a non-secret retrieval receipt."""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import urllib.request
import urllib.error

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'artifacts/private/gauntlet/literature'


def bridge(action, args):
    data = json.dumps({'action': action, 'args': args, 'session': 'dhan-literature'}).encode()
    req = urllib.request.Request('http://127.0.0.1:10086/command', data, {'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=50) as response:
        result = json.load(response)
    if not result.get('ok'):
        raise ValueError(str(result)[:250])
    return result['data']


def browser_collect(key, url, *, pdf=False):
    import base64
    OUT.mkdir(parents=True, exist_ok=True)
    receipt = {'id': key, 'url': url, 'retrieved_utc': datetime.now(timezone.utc).isoformat(), 'method': 'browser'}
    try:
        if pdf:
            # Caller first opens the public landing page in this task's own tab.
            code = '(async()=>{const r=await fetch(' + json.dumps(url) + ');const a=new Uint8Array(await r.arrayBuffer());let s="";for(let i=0;i<a.length;i+=16384)s+=String.fromCharCode(...a.subarray(i,i+16384));return JSON.stringify({status:r.status,type:r.headers.get("content-type"),body:btoa(s)});})()'
            result = json.loads(bridge('evaluate', {'code': code})['value'])
            body = base64.b64decode(result.pop('body'))
            receipt.update(result)
            ext = '.pdf' if body.startswith(b'%PDF') else '.html'
        else:
            bridge('navigate', {'url': url, 'newTab': True})
            code = 'JSON.stringify({url:location.href,title:document.title,text:document.body.innerText,links:Array.from(document.querySelectorAll("a")).map(a=>({text:a.innerText,url:a.href})).filter(a=>a.text)})'
            body = bridge('evaluate', {'code': code})['value'].encode()
            ext = '.json'
        path = OUT / (key + ext)
        path.write_bytes(body)
        receipt.update(path=str(path.relative_to(ROOT)), sha256=hashlib.sha256(body).hexdigest(), bytes=len(body))
        if ext == '.pdf':
            text_path = path.with_suffix('.txt')
            proc = subprocess.run(['pdftotext', '-layout', str(path), str(text_path)], capture_output=True, text=True)
            receipt['text_extraction_exit'] = proc.returncode
            if proc.returncode == 0:
                receipt['text_sha256'] = hashlib.sha256(text_path.read_bytes()).hexdigest()
        else:
            receipt['note'] = 'Manual inspection required: may be landing page or access challenge'
    except Exception as error:
        receipt.update(error=type(error).__name__, detail=str(error)[:250])
    (OUT / (key + '.receipt.json')).write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt


def collect(key, url):
    OUT.mkdir(parents=True, exist_ok=True)
    receipt = {'id': key, 'url': url, 'retrieved_utc': datetime.now(timezone.utc).isoformat()}
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (compatible; research source retrieval)'})
        with urllib.request.urlopen(req, timeout=35) as response:
            body = response.read(30_000_001)
            if len(body) > 30_000_000:
                raise ValueError('source exceeds 30 MB retrieval cap')
            receipt.update(status=response.status, final_url=response.url,
                           content_type=response.headers.get('Content-Type'))
        ext = '.pdf' if body.startswith(b'%PDF') else '.html'
        path = OUT / (key + ext)
        path.write_bytes(body)
        receipt.update(path=str(path.relative_to(ROOT)), sha256=hashlib.sha256(body).hexdigest(), bytes=len(body))
        if ext == '.pdf':
            text_path = path.with_suffix('.txt')
            proc = subprocess.run(['pdftotext', '-layout', str(path), str(text_path)], capture_output=True, text=True)
            receipt['text_extraction_exit'] = proc.returncode
            if proc.returncode == 0:
                receipt['text_sha256'] = hashlib.sha256(text_path.read_bytes()).hexdigest()
        else:
            receipt['note'] = 'HTML response; manual content inspection required, not proof of paper access'
    except Exception as error:
        receipt.update(error=type(error).__name__, detail=str(error)[:250])
    (OUT / (key + '.receipt.json')).write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('key')
    p.add_argument('url')
    p.add_argument('--browser', action='store_true')
    p.add_argument('--pdf', action='store_true')
    args = p.parse_args()
    if not args.key.replace('-', '').replace('_', '').isalnum():
        p.error('key must be alphanumeric with hyphens/underscores')
    print(json.dumps(browser_collect(args.key, args.url, pdf=args.pdf) if args.browser else collect(args.key, args.url), indent=2))
