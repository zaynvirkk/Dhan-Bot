"""Content digests for local research results; never a live-trading receipt."""
import hashlib
from pathlib import Path
from .data import ROOT

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def source_manifest():
    paths=sorted((ROOT/'research/gauntlet').glob('*.py'))
    paths += [ROOT/'dhan_cas_bot/risk.py',ROOT/'research/gauntlet/PROTOCOL.md']
    files={str(p.relative_to(ROOT)):digest(p) for p in paths}
    joined='\n'.join(k+':'+v for k,v in sorted(files.items()))
    return {'sha256':hashlib.sha256(joined.encode()).hexdigest(),'files':files}
