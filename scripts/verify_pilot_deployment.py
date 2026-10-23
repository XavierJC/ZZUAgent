"""Read-only deployment and original-row preservation checks after pilot preparation."""
import json,sqlite3,hashlib,re
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
from zipfile import ZipFile
import httpx

root=Path.cwd();folder=Path(json.loads((root/'data/local/pilot-current.json').read_text())['folder'])
before=json.loads((folder/'before.json').read_text());pilot=json.loads((root/'data/local/pilot-review.json').read_text(encoding='utf-8'))
vision=json.loads((root/'data/local/pilot-real.json').read_text(encoding='utf-8'))
with sqlite3.connect(folder/'database-before.sqlite3') as old,sqlite3.connect(root/'data/local/eduagent.sqlite3') as new:
    assert new.execute('pragma user_version').fetchone()[0]==12
    assert new.execute('pragma integrity_check').fetchone()[0]=='ok' and not new.execute('pragma foreign_key_check').fetchall()
    for name,fields in before['columns'].items():
        select='SELECT '+','.join('"'+field+'"' for field in fields)+' FROM "'+name+'"'
        assert not (Counter(old.execute(select).fetchall())-Counter(new.execute(select).fetchall())),name+' old row changed'
    for name in ('metadata','mastery','decisions','attempts','tutor_runs','notes','self_assessment_batches','self_assessment_entries','study_guide_runs'):
        assert old.execute('select * from '+name).fetchall()==new.execute('select * from '+name).fetchall(),name+' facts changed'
    assert new.execute('select revision from students where id=?',(pilot['student_id'],)).fetchone()[0]==0
    assert new.execute('select published_version from knowledge_architectures where id=?',(pilot['architecture_id'],)).fetchone()[0]==0
    assert new.execute("select count(*) from teaching_material_links where student_id=? and status='candidate'",(pilot['student_id'],)).fetchone()[0]==5
    assert new.execute("select count(*) from personal_questions where student_id=? and status='draft'",(pilot['student_id'],)).fetchone()[0]==3
    for r in new.execute('select payload_json from personal_questions where student_id=?',(pilot['student_id'],)):assert json.loads(r[0])['answer'] is None
    counts={t:new.execute('select count(*) from '+t).fetchone()[0] for t in ('students','personal_questions','notes','course_documents','document_parse_runs','teaching_material_links','course_releases','attempts')}
    vr=new.execute('select status,model_calls,error_code,usage_json from document_parse_runs where id=?',(vision['vision_run_id'],)).fetchone()
    assert vr[0]=='uncertain' and vr[1]==1 and vr[2]=='network_error'
for group in ('data_files','original_files'):
    for p,checksum in before[group].items():assert hashlib.sha256((root/p).read_bytes()).hexdigest()==checksum,p
protected=['backend/src/eduagent/services/learning.py','backend/src/eduagent/agent/policy.py','backend/src/eduagent/domain/bkt.py','backend/src/eduagent/domain/catalog.py']
with ZipFile(folder/'code-before.zip') as z:
    for p in protected:assert (root/p).read_bytes()==z.read(p),p
with httpx.Client(base_url='http://127.0.0.1:8000',trust_env=False,timeout=15) as c:
    def get(p):r=c.get(p);r.raise_for_status();return r
    assert get('/health').json()['status']=='ok' and len(get('/openapi.json').json()['paths'])==86
    assets=re.findall(r'(?:src|href)="(/assets/[^"]+)"',get('/').text)
    assert assets and all(get(a).content for a in assets)
    prefix='/api/v1/students/'+pilot['student_id']
    assert all(s['source_type']!='teaching_material' for s in get(prefix+'/knowledge/sources').json()['items'])
    assert get(prefix+'/documents/'+pilot['course']['id']).json()['index_status']=='pending'
    assert get(prefix+'/teaching-sessions').json()['session'] is None
    assert len(get(prefix+'/teaching-material-links').json()['items'])==5
    assert len(get('/api/v1/courses/published').json()['items'])==1
report=dict(passed=True,verified_at=datetime.now(timezone.utc).isoformat(),schema=12,tables=45,api_paths=86,counts=counts,
    old_43_table_rows_preserved=True,original_files_and_evaluations_unchanged=True,protected_learning_sources=protected,
    pilot_learning_revision=0,pilot_concept_published=False,pilot_teacher_fragments='5 candidate; excluded from RAG until owner review',
    pilot_questions='3 draft with unknown answers; not formal BKT',paid_vision_requests=vr[1],paid_vision_status=vr[0],paid_vision_error=vr[2],reported_usage=json.loads(vr[3]),billing_status='unknown; zero reported tokens does not prove zero charge',real_chat_calls=0,assets=assets,
    browser_manual='not_performed; prior localhost browser denial not bypassed',integrity='ok',foreign_key_errors=0)
out=root/'data/evaluation/pilot-deployment-v1.json';out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(passed=True,schema=12,api_paths=86,counts=counts,paid_vision_calls=1,report=str(out))))
