"""Read-only checks of live service; never create questions or call models."""
from datetime import datetime,timezone
from hashlib import sha256
import json,re,sqlite3
from pathlib import Path
from urllib.request import build_opener,ProxyHandler
from eduagent.storage.migrations import preserved_snapshot,table_names,BANK_TABLES

root=Path.cwd();folder=Path(json.loads((root/'data/local/phase4c-current.json').read_text())['folder'])
baseline=json.loads((folder/'before.json').read_text(encoding='utf-8'))
opener=build_opener(ProxyHandler({}));base='http://127.0.0.1:8000'
def get(path,raw=False):
    with opener.open(base+path,timeout=20) as response:
        assert response.status==200;data=response.read();return data if raw else json.loads(data)
health=get('/health');assert health['status']=='ok' and health['question_count']==10
schema=get('/openapi.json');assert len(schema['paths'])==62
index=get('/',True).decode();assets=re.findall(r'(?:src|href)="(/assets/[^\"]+)"',index)
assert assets and all(get(asset,True) for asset in assets)
with sqlite3.connect('file:data/local/eduagent.sqlite3?mode=ro',uri=True) as db:
    version=db.execute('pragma user_version').fetchone()[0];assert version==9 and len(table_names(db))==34
    assert preserved_snapshot(db,baseline['columns'])[0]==baseline['facts']
    assert not db.execute('pragma foreign_key_check').fetchall() and db.execute('pragma integrity_check').fetchone()[0]=='ok'
    student=db.execute('select student_id from course_documents where deleted_at is null order by created_at limit 1').fetchone()[0]
    counts={name:db.execute('select count(*) from '+name).fetchone()[0] for name in BANK_TABLES}
    assert all(count==0 for count in counts.values()),'production contains bank writes; audit separately'
    calls=db.execute("select coalesce(sum(model_calls),0) from document_parse_runs where mode='vision'").fetchone()[0]
    migration=json.loads(Path('data/evaluation/phase4c-migration-v1.json').read_text(encoding='utf-8'))
    with sqlite3.connect(Path(migration['migration']['backup']).as_uri()+'?mode=ro',uri=True) as old:
        prior_calls=old.execute("select coalesce(sum(model_calls),0) from document_parse_runs where mode='vision'").fetchone()[0]
    assert calls==prior_calls
    catalogue=get('/api/v1/students/'+student+'/course-resources')
    assert any(r['original_source_type']=='document' for r in catalogue['items'])
    assert get('/api/v1/students/'+student+'/personal-bank/questions')['items']==[]
    cap=get('/api/v1/students/'+student+'/documents/capabilities');assert cap['vision_enabled']
    assert preserved_snapshot(db,baseline['columns'])[0]==baseline['facts']
assert all(sha256((root/p).read_bytes()).hexdigest()==h for p,h in baseline['original_files'].items())
# This extra data-file inventory was captured after the first isolated 4C run.
# A regenerated 4C report is a delivery output, not a pre-existing evaluation.
previous_data={p:h for p,h in baseline['data_files'].items() if not (Path(p).parent==Path('data/evaluation') and Path(p).name.startswith('phase4c-'))}
assert all(sha256((root/p).read_bytes()).hexdigest()==h for p,h in previous_data.items())
report=dict(passed=True,verified_at=datetime.now(timezone.utc).isoformat(),schema=version,tables=34,paths=62,
    assets=assets,health='ok',formal_question_count=10,all_original_27_tables_unchanged=True,original_files_unchanged=True,
    previous_evaluations_and_course_data_unchanged=True,previous_data_files_verified=len(previous_data),new_phase4c_reports_excluded_from_original_inventory=True,new_tables_counts=counts,catalogue_existing_document_visible=True,
    vision_manually_enabled=True,vision_model_calls_before_phase4c=prior_calls,vision_model_calls_in_production=calls,new_vision_calls=0,real_model_calls=0,browser_manual='not_performed',
    browser_limitation='Prior localhost automation denial; no workaround attempted',integrity='ok',foreign_key_errors=0)
p=Path('data/evaluation/phase4c-deployment-v1.json');p.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(passed=True,schema=version,tables=34,original_tables_unchanged=True,real_model_calls=0,report=str(p))))
