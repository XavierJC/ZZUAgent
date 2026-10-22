"""Read-only live deployment check; no practice allocation or model requests."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3
from urllib.parse import quote
from urllib.request import Request, build_opener, ProxyHandler
from eduagent.storage.migrations import preserved_snapshot, table_names

root=Path.cwd().resolve(); opener=build_opener(ProxyHandler({}))
def get(path, raw=False):
    with opener.open(Request('http://127.0.0.1:8000'+path),timeout=15) as response:
        assert response.status==200
        value=response.read()
        return value if raw else json.loads(value)

migration=json.loads((root/'data/evaluation/phase4b1-migration-v1.json').read_text(encoding='utf8'))
with sqlite3.connect((root/'data/local/eduagent.sqlite3').as_uri()+'?mode=ro',uri=True) as db:
    facts,columns=preserved_snapshot(db)
    assert all(facts[name]==fact for name,fact in migration['migration']['facts'].items())
    assert db.execute('PRAGMA user_version').fetchone()[0]==7 and len(table_names(db))==21
    assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok' and not db.execute('PRAGMA foreign_key_check').fetchall()
    owner=db.execute('SELECT id FROM students ORDER BY id LIMIT 1').fetchone()[0]
    assert db.execute('SELECT count(*) FROM course_documents').fetchone()[0]==0
health=get('/health'); assert health['status']=='ok'
api=get('/openapi.json'); assert len(api['paths'])==40
page=get('/',raw=True); assert page==(root/'frontend/dist/index.html').read_bytes()
assets=re.findall(rb'(?:src|href)="(/assets/[^\"]+)"',page)
assert any(b'index-VoxgI5fA.js' in path for path in assets)
for path in assets:
    asset=get(path.decode(),raw=True); assert asset==(root/'frontend/dist'/path.decode().lstrip('/')).read_bytes()
prefix='/api/v1/students/'+quote(owner,safe='')+'/documents'
capabilities=get(prefix+'/capabilities')
assert not capabilities['vision_enabled'] and not capabilities['retrieval_connected']
assert all(capabilities['formats'].values()) and get(prefix)['items']==[]
get('/docs',raw=True)
report={'passed':True,'verified_at':datetime.now(timezone.utc).isoformat(),'schema':7,'table_count':21,
    'original_fifteen_tables_match_pre_migration':True,'integrity':'ok','foreign_key_errors':0,
    'health':'ok','openapi_paths':40,'assets_verified':[p.decode() for p in assets],
    'vision_enabled':False,'documents_in_rag':False,'all_native_parser_dependencies_available':True,
    'production_document_uploads':0,'production_learning_writes':0,'model_calls':0,
    'browser_manual_validation':'not_performed','base_url':'http://127.0.0.1:8000/'}
target=root/'data/evaluation/phase4b1-deployment-v1.json'
target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({'passed':True,'paths':40,'schema':7,'vision_enabled':False,'report':str(target)}))
