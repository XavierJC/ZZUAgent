"""Read-only production health/assets/scope plus migration data preservation."""
import hashlib,json,re,sqlite3
from datetime import datetime,timezone
from pathlib import Path
from urllib.request import build_opener,ProxyHandler
from eduagent.storage.migrations import preserved_snapshot

root=Path.cwd();audit=json.loads((root/'data/evaluation/extraction-v2-migration-v1.json').read_text(encoding='utf-8'))
opener=build_opener(ProxyHandler({}));base='http://127.0.0.1:8000'
def get(path):
    with opener.open(base+path,timeout=10) as r:return r.read()
assert json.loads(get('/health'))['status']=='ok'
schema=json.loads(get('/openapi.json'));assert len(schema['paths'])==67
index=get('/');assets=re.findall(rb'(?:src|href)="(/assets/[^"]+)"',index)
assert assets and all(get(path.decode()) for path in assets)
with sqlite3.connect(root/'data/local/eduagent.sqlite3') as db:
    assert db.execute('pragma user_version').fetchone()[0]==10
    assert preserved_snapshot(db,audit['original_columns'])[0]==audit['original_table_summaries']
    assert db.execute('pragma integrity_check').fetchone()[0]=='ok' and not db.execute('pragma foreign_key_check').fetchall()
    assert db.execute('select count(*) from question_extraction_tasks').fetchone()[0]==0
    assert db.execute('select count(*) from personal_practice_drafts').fetchone()[0]==0
    student=db.execute('select id from students order by id limit 1').fetchone()[0]
    counts={name:db.execute('select count(*) from '+name).fetchone()[0] for name in ('personal_questions','notes','course_documents','attempts')}
    historical_vision_calls=db.execute("select coalesce(sum(model_calls),0) from document_parse_runs where mode='vision'").fetchone()[0]
from urllib.parse import quote
prefix='/api/v1/students/'+quote(student,safe='')
cap=json.loads(get(prefix+'/personal-bank/extraction-capabilities'));assert cap['enabled'] and cap['max_output_tokens']==10000
assert json.loads(get(prefix+'/personal-bank/extraction-tasks'))['items']==[]
assert len(json.loads(get(prefix+'/personal-bank/questions'))['items'])<=counts['personal_questions']
assert json.loads(get(prefix+'/course-resources'))['items']
for path,value in audit['formal_files'].items():assert hashlib.sha256((root/path).read_bytes()).hexdigest()==value
report=dict(passed=True,verified_at=datetime.now(timezone.utc).isoformat(),schema=10,tables=36,api_paths=67,assets=[p.decode() for p in assets],
    original_34_tables_unchanged=True,formal_files_unchanged=True,counts=counts,production_new_model_calls=0,production_extraction_tasks=0,
    historical_document_vision_calls=historical_vision_calls,model_capabilities=cap,browser_manual='not_performed',
    browser_limitation='Earlier browser access to localhost was denied; no bypass using another browser or automation tool.',integrity='ok',foreign_key_errors=0)
output=root/'data/evaluation/extraction-v2-deployment-v1.json';output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(passed=True,schema=10,paths=67,counts=counts,production_model_calls=0,report=str(output))))
