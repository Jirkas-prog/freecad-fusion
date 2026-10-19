"""Package tracked files only, with a public-content gate and a SHA-256 checksum."""
from pathlib import Path
import hashlib
import re
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parents[1]
files=subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0')
files=[p for p in files if p]
assert files, 'Stage the intended source files in Git first.'
for name in files:
    p=ROOT/name
    assert p.is_file() and not p.is_symlink(), name
    assert p.suffix.lower() not in {'.fcstd','.fcbak','.f3d','.log','.pyc','.key','.pem','.keystore','.jks'}, name
    assert not any(part in {'backup','__pycache__','.git','test-output'} for part in p.relative_to(ROOT).parts), name
    if p.suffix.lower() in {'.png','.ttf','.woff','.woff2'}:continue
    text=p.read_text(encoding='utf-8',errors='replace')
    # Use escaped pieces so the scanner does not match its own source.
    patterns=[r'[A-Za-z]:[/\\]Users[/\\](?!Public\b|Default\b)[^/\\\s"\']+',
              r'gh[pousr]_[A-Za-z0-9]{25,}',r'github_pat_[A-Za-z0-9_]{30,}',
              r'-----BEGIN '+r'(?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
              r'AppData[/\\]+Local[/\\]+Autodesk[/\\]+webdeploy']
    assert not any(re.search(pattern,text,re.I) for pattern in patterns), 'Private content: '+name
out=ROOT/'dist';out.mkdir(exist_ok=True)
archive=out/'FusionFlow-addon.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for name in sorted(files):
        # ZIP permissions and timestamps are stable; no local path metadata is included.
        info=zipfile.ZipInfo('FusionFlow-addon/'+name,date_time=(2026,10,20,0,0,0))
        info.compress_type=zipfile.ZIP_DEFLATED
        info.external_attr=0o644 << 16
        z.writestr(info,(ROOT/name).read_bytes())
digest=hashlib.sha256(archive.read_bytes()).hexdigest()
(out/'SHA256SUMS.txt').write_text(digest+'  '+archive.name+'\n',encoding='ascii')
print(f'{archive.name}: {archive.stat().st_size:,} bytes, {len(files)} files')
print('SHA-256:',digest)
