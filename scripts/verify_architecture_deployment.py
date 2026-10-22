"""Read-only checks against the installed local API, never creates a graph."""
from datetime import datetime,timezone
import json
from pathlib import Path
import re
import sqlite3
from urllib.parse import quote
from urllib.request import Request,build_opener,ProxyHandler
from eduagent.storage.migrations import preserved_snapshot,table_names

root=Path.cwd();opener=build_opener(ProxyHandler({}))
def get(path,raw=False):
    with opener.open(Request('http://127.0.0.1:8000'+path),timeout=15) as response:
        assert response.status==200;value=response.read();return value if raw else json.loads(value)
migration=json.loads((root/'data/evaluation/phase4b2-migration-v1.json').read_text(encoding='utf8'))
with sqlite3.connect((root/'data/local/eduagent.sqlite3').resolve().as_uri()+'?mode=ro',uri=True) as db:
    facts,columns=preserved_snapshot(db)
    assert all(facts[k]==v for k,v in migration['migration']['facts'].items())
    assert db.execute('pragma user_version').fetchone()[0]==8 and len(table_names(db))==27
    assert db.execute('pragma integrity_check').fetchone()[0]=='ok' and not db.execute('pragma foreign_key_check').fetchall()
    owner=db.execute('select id from students order by id limit 1').fetchone()[0]
    assert db.execute('select count(*) from knowledge_architectures').fetchone()[0]==0
assert get('/health')['status']=='ok';assert len(get('/openapi.json')['paths'])==50
page=get('/',raw=True);assert page==(root/'frontend/dist/index.html').read_bytes()
assets=re.findall(rb'(?:src|href)="(/assets/[^\"]+)"',page)
for path in assets:assert get(path.decode(),True)==(root/'frontend/dist'/path.decode().lstrip('/')).read_bytes()
prefix='/api/v1/students/'+quote(owner,safe='')
assert get(prefix+'/knowledge-architectures')['items']==[]
assert not get(prefix+'/documents/capabilities')['vision_enabled']
get(prefix+'/documents');get(prefix+'/learning-guidance');get(prefix+'/self-assessments/latest');get(prefix+'/knowledge/sources')
report=dict(passed=True,verified_at=datetime.now(timezone.utc).isoformat(),schema=8,table_count=27,original_twenty_one_tables_unchanged=True,
    integrity='ok',foreign_key_errors=0,openapi_paths=50,assets_verified=[a.decode() for a in assets],vision_enabled=False,
    production_graph_creations=0,production_learning_writes=0,real_model_calls=0,browser_manual_validation='not_performed')
output=root/'data/evaluation/phase4b2-deployment-v1.json';output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(dict(passed=True,schema=8,paths=50,report=str(output))))
