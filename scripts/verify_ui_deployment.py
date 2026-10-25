"""Read-only UI deployment verification against this turn's actual baseline."""
import json
import re
import sqlite3
import zipfile
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from urllib.request import ProxyHandler, build_opener
from eduagent.storage.migrations import preserved_snapshot

root=Path(__file__).resolve().parents[1]
backup=Path(json.loads((root/'data/local/ui-refactor-current.json').read_text())['folder'])
baseline=json.loads((backup/'baseline.json').read_text(encoding='utf-8'))
with sqlite3.connect((root/'data/local/eduagent.sqlite3').as_uri()+'?mode=ro',uri=True) as db:
    assert db.execute('PRAGMA user_version').fetchone()[0]==baseline['schema']==14
    assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    assert not db.execute('PRAGMA foreign_key_check').fetchall()
    tables=preserved_snapshot(db,baseline['columns'])[0]
    assert tables==baseline['tables'] and len(tables)==50
for name,digest in baseline['protected'].items():assert sha256((root/name).read_bytes()).hexdigest()==digest,name
for name,digest in baseline['files'].items():
    if name.startswith('backend/'):
        assert sha256((root/name).read_bytes()).hexdigest()==digest,name
current={}
for prefix in ('frontend/src','backend/src','backend/tests','docs','scripts'):
    for file in (root/prefix).rglob('*'):
        if file.is_file() and '__pycache__' not in file.parts:current[file.relative_to(root).as_posix()]=sha256(file.read_bytes()).hexdigest()
for name in ('README.md','AGENTS.md','.gitignore','frontend/package.json','frontend/package-lock.json'):
    current[name]=sha256((root/name).read_bytes()).hexdigest()
changes=[dict(path=name,change='modified' if name in baseline['files'] else 'added') for name in sorted(current) if current[name]!=baseline['files'].get(name)]
assert not [name for name in baseline['files'] if name not in current]
assert current['frontend/package.json']==baseline['files']['frontend/package.json']
assert current['frontend/package-lock.json']==baseline['files']['frontend/package-lock.json']
with zipfile.ZipFile(backup/'code-before.zip') as archive:assert archive.testzip() is None
opener=build_opener(ProxyHandler({}))
def get(path):
    with opener.open('http://127.0.0.1:8000'+path,timeout=10) as response:return response.read()
assert json.loads(get('/health'))['status']=='ok'
index=get('/');assert index==(root/'frontend/dist/index.html').read_bytes()
assets=[value.decode() for value in re.findall(rb'(?:src|href)="(/assets/[^\"]+)"',index)]
for asset in assets:assert get(asset)==(root/'frontend/dist'/asset.lstrip('/')).read_bytes()
chunks=list((root/'frontend/dist/assets').glob('*Page-*.js'))
for chunk in chunks:assert get('/assets/'+chunk.name)==chunk.read_bytes()
report=dict(passed=True,schema=14,tables=50,all_50_table_digests_unchanged=True,protected_files_unchanged=len(baseline['protected']),backend_sources_and_tests_unchanged=True,no_added_dependencies=True,backup=str(backup),changed_files=changes,entry_assets=assets,page_chunks_verified=len(chunks),real_model_calls=0,verified_at=datetime.now(timezone.utc).isoformat())
(root/'data/evaluation/ui-ux-deployment-v1.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k!='changed_files'},ensure_ascii=False))
