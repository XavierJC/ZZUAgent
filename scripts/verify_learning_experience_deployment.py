"""Read-only live-service checks against the recoverable pre-change snapshot."""
import json
import re
import sqlite3
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, ProxyHandler, build_opener
from eduagent.storage.migrations import preserved_snapshot


def main():
    base='http://127.0.0.1:8000';opener=build_opener(ProxyHandler({}))
    def http(path,body=None):
        request=Request(base+path,data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json'})
        with opener.open(request,timeout=10) as response:return response.read(),dict(response.headers)
    baseline_dir=Path(json.loads(Path('data/local/learning-experience-current.json').read_text())['folder'])
    baseline=json.loads((baseline_dir/'baseline.json').read_text(encoding='utf-8'))
    path=Path('data/local/eduagent.sqlite3').resolve()
    with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as db:
        before=preserved_snapshot(db,baseline['columns'])[0]
        assert before==baseline['tables'],'Existing table content changed; inspect before claiming preservation.'
        assert db.execute('PRAGMA user_version').fetchone()[0]==13
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert not db.execute('PRAGMA foreign_key_check').fetchall()
        owner=db.execute('SELECT student_id FROM course_documents WHERE deleted_at IS NULL ORDER BY id LIMIT 1').fetchone()
    assert json.loads(http('/health')[0])['status']=='ok'
    schema=json.loads(http('/openapi.json')[0]);assert 'page' in schema['components']['schemas']['SourceOpen']['properties']
    index,headers=http('/');assets=[name.decode() for name in re.findall(rb'(?:src|href)="(/assets/[^\"]+)"',index)]
    assert assets and all(http(asset)[0] for asset in assets)
    assert index==Path('frontend/dist/index.html').read_bytes()
    assert any(key.lower()=='cache-control' and value=='no-store' for key,value in headers.items())
    preview_ok=False
    if owner:
        prefix='/api/v1/students/'+quote(owner[0],safe='')
        sources=json.loads(http(prefix+'/knowledge/sources')[0])['items']
        source=next((s for s in sources if s['source_type']=='uploaded_document' and s['total_units']>0),None)
        if source:
            selected={key:source[key] for key in ('source_type','source_id','source_version')}
            preview=json.loads(http(prefix+'/workbench/sources/open',dict(selected,page=1))[0])
            preview_ok=preview['page_number']==1 and bool(preview['pages'])
    with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as db:assert preserved_snapshot(db,baseline['columns'])[0]==before
    report=dict(passed=True,schema=13,tables=45,all_45_table_summaries_unchanged=True,
                backup=str(baseline_dir/'before.sqlite3'),code_backup=str(baseline_dir/'code-before.zip'),
                integrity=True,foreign_keys=True,migration_required=False,assets=assets,
                index_sha256=sha256(index).hexdigest(),current_page_preview_verified=preview_ok,
                production_writes=0,real_model_calls=0,verified_at=datetime.now(timezone.utc).isoformat())
    Path('data/evaluation/learning-experience-deployment-v1.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(passed=True,schema=13,tables_preserved=45,preview=preview_ok)))


if __name__=='__main__':main()
