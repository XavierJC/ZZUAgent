"""Read-only live verification and source inventory against the rebuild backup."""
import json,re,sqlite3,zipfile
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
from urllib.request import ProxyHandler,build_opener
from eduagent.storage.migrations import preserved_snapshot

def verify():
    root=Path(__file__).resolve().parents[1]
    base=Path(json.loads((root/'data/local/notebook-rebuild-current.json').read_text())['folder'])
    baseline=json.loads((base/'baseline.json').read_text(encoding='utf-8'))
    with sqlite3.connect((root/'data/local/eduagent.sqlite3').as_uri()+'?mode=ro',uri=True) as db:
        assert db.execute('PRAGMA user_version').fetchone()[0]==14
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok' and not db.execute('PRAGMA foreign_key_check').fetchall()
        tables=preserved_snapshot(db)[0];assert len(tables)==50
        assert preserved_snapshot(db,baseline['columns'])[0]==baseline['tables']
    for name,digest in baseline['fingerprints'].items():assert sha256((root/name).read_bytes()).hexdigest()==digest,name
    opener=build_opener(ProxyHandler({}))
    def get(path):
        with opener.open('http://127.0.0.1:8000'+path,timeout=15) as r:return r.read(),dict(r.headers)
    health=json.loads(get('/health')[0]);assert health['status']=='ok'
    index,headers=get('/');assert index==(root/'frontend/dist/index.html').read_bytes()
    assert any(k.lower()=='cache-control' and v=='no-store' for k,v in headers.items())
    assets=[s.decode() for s in re.findall(rb'(?:src|href)="(/assets/[^\"]+)"',index)]
    for asset in assets:assert get(asset)[0]==(root/'frontend/dist'/asset.lstrip('/')).read_bytes()
    for page in (root/'frontend/dist/assets').glob('*Page-*.js'):assert get('/assets/'+page.name)[0]==page.read_bytes()
    schema=json.loads(get('/openapi.json')[0]);assert any('/notebooks' in key for key in schema['paths'])
    with zipfile.ZipFile(base/'code-before.zip') as z:
        assert z.testzip() is None
        before={i.filename:sha256(z.read(i)).hexdigest() for i in z.infolist()}
    current={}
    for prefix in ('frontend/src','backend/src','backend/tests','docs','scripts'):
        for file in (root/prefix).rglob('*'):
            if file.is_file() and '__pycache__' not in file.parts:current[file.relative_to(root).as_posix()]=sha256(file.read_bytes()).hexdigest()
    for name in ('AGENTS.md','README.md','frontend/package.json','frontend/package-lock.json','frontend/vite.config.js'):current[name]=sha256((root/name).read_bytes()).hexdigest()
    changes=[dict(path=name,change='modified' if name in before else 'added') for name in sorted(current) if current[name]!=before.get(name)]
    deleted=[name for name in before if name not in current];assert not deleted
    (root/'data/evaluation/notebook-rebuild-files-v1.json').write_text(json.dumps(changes,ensure_ascii=False,indent=2),encoding='utf-8')
    output=dict(passed=True,schema=14,tables=50,original_45_table_digests_unchanged=True,original_resource_and_evaluation_fingerprints_preserved=len(baseline['fingerprints']),integrity=True,foreign_keys=True,entry_assets=assets,entry_js_bytes=max(len(get(a)[0]) for a in assets if a.endswith('.js')),changed_files=len(changes),no_deleted_source_files=True,real_model_calls=0,backup=str(base),verified_at=datetime.now(timezone.utc).isoformat())
    (root/'data/evaluation/notebook-rebuild-deployment-v1.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(output,ensure_ascii=False))
if __name__=='__main__':verify()
