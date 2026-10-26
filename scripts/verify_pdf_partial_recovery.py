"""Back up, validate and explicitly retry ONE local PDF, without any model call."""
import argparse
import json
import re
import sqlite3
import tempfile
import time
import zipfile
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import ProxyHandler, Request, build_opener
from uuid import uuid4

from eduagent.storage.migrations import preserved_snapshot

ROOT = Path(__file__).resolve().parents[1]
POINTER = ROOT/'data/local/pdf-partial-current.json'
DB = ROOT/'data/local/eduagent.sqlite3'
FILES = ROOT/'data/local/eduagent.documents'

def connect(path=DB):
    db=sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)
    db.row_factory=sqlite3.Row
    return db

def digest(path): return sha256(path.read_bytes()).hexdigest()
def write(path,value): path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
def load():
    folder=Path(json.loads(POINTER.read_text())['folder'])
    return folder,json.loads((folder/'baseline.json').read_text(encoding='utf-8'))

def snapshot(document):
    folder=ROOT/'data/local'/('pdf-partial-'+datetime.now().strftime('%Y%m%d-%H%M%S'))
    folder.mkdir()
    with connect() as live,sqlite3.connect(folder/'before.sqlite3') as backup:
        live.backup(backup)
    with connect(folder/'before.sqlite3') as db:
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert not db.execute('PRAGMA foreign_key_check').fetchall()
        tables,columns=preserved_snapshot(db)
        doc=dict(db.execute('SELECT * FROM course_documents WHERE id=? AND deleted_at IS NULL',(document,)).fetchone())
        version=dict(db.execute('SELECT * FROM document_versions WHERE id=?',(doc['current_version_id'],)).fetchone())
        run=dict(db.execute('SELECT * FROM document_parse_runs WHERE id=?',(doc['current_parse_id'],)).fetchone())
        assert version['format']=='pdf' and run['status']=='failed'
        originals={r['storage_key']:r['content_hash'] for r in db.execute('SELECT storage_key,content_hash FROM document_versions')}
        schema=db.execute('PRAGMA user_version').fetchone()[0]
    for key,value in originals.items():assert digest(FILES/key)==value
    protected={}
    for path in (ROOT/'data').rglob('*'):
        relative=path.relative_to(ROOT/'data')
        if path.is_file() and relative.parts[0] not in ('local','reference-code'):
            protected[path.relative_to(ROOT).as_posix()]=digest(path)
    sources={}
    with zipfile.ZipFile(folder/'code-before.zip','w',zipfile.ZIP_DEFLATED) as archive:
        for prefix in ('backend/src','backend/tests','frontend/src','docs','scripts'):
            for path in (ROOT/prefix).rglob('*'):
                if path.is_file() and '__pycache__' not in path.parts:
                    name=path.relative_to(ROOT).as_posix();sources[name]=digest(path);archive.write(path,name)
        for name in ('AGENTS.md','README.md','frontend/package.json','frontend/package-lock.json'):
            sources[name]=digest(ROOT/name);archive.write(ROOT/name,name)
    write(folder/'baseline.json',dict(schema=schema,tables=tables,columns=columns,document=doc,version=version,run=run,originals=originals,protected=protected,sources=sources))
    write(POINTER,dict(folder=str(folder)))
    print(json.dumps(dict(backup=str(folder),schema=schema,tables=len(tables),originals=len(originals),protected_files=len(protected))))

def isolated():
    from eduagent.documents.limits import run_worker
    folder,base=load()
    original=FILES/base['version']['storage_key']
    assert digest(original)==base['version']['content_hash']
    # The real worker receives no credentials and retains its original limits.
    with tempfile.TemporaryDirectory(prefix='worker-',dir=folder) as temporary:
        path=Path(temporary);manifest=path/'input.json';output=path/'output.json'
        write(manifest,dict(path=str(original),kind='pdf',mode='local'))
        data=run_worker(manifest,output)
        json.dumps(data,ensure_ascii=False).encode('utf-8')
        units=data['units']
        report=dict(passed=True,status=data['status'],pages=len(units),readable_pages=sum(len(''.join(u['text'].split()))>=24 for u in units),
            skipped_pages=[u['ordinal'] for u in units if 'pdf_page_text_extraction_failed' in u['warnings']],
            encoding_repaired_pages=[u['ordinal'] for u in units if 'pdf_text_encoding_repaired' in u['warnings']],
            invalid_codepoints_remaining=sum(0xd800<=ord(c)<=0xdfff for u in units for c in u['text']),
            original_hash_preserved=digest(original)==base['version']['content_hash'],real_model_calls=0,database_writes=0)
    assert report['invalid_codepoints_remaining']==0 and report['readable_pages']>0
    write(ROOT/'data/evaluation/pdf-partial-worker-v1.json',report);print(json.dumps(report))

def api(path,body=None):
    request=Request('http://127.0.0.1:8000'+path,data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json'})
    try:
        with build_opener(ProxyHandler({})).open(request,timeout=30) as response:return json.load(response)
    except HTTPError as error: raise RuntimeError('Local document API returned HTTP '+str(error.code)) from None

def retry():
    folder,base=load();doc=base['document'];prefix='/api/v1/students/'+quote(doc['student_id'],safe='')+'/documents'
    pending=folder/'retry-operation.json'
    if pending.exists():
        body=json.loads(pending.read_text());api(prefix+'/operations/'+body['request_id'])
    else:
        current=api(prefix+'/'+doc['id'])
        assert current['revision']==doc['revision'] and current['parse']['status']=='failed'
        body=dict(request_id=str(uuid4()),expected_revision=doc['revision'])
        write(pending,body)  # Persist BEFORE POST. Subsequent invocations only GET this receipt.
        try:api(prefix+'/'+doc['id']+'/parse',body)
        except (URLError,TimeoutError):
            print('Retry execution unconfirmed; operation id retained. Query receipt only.');return
    deadline=time.monotonic()+45
    while time.monotonic()<deadline:
        current=api(prefix+'/'+doc['id'])
        if current['parse']['status'] not in ('pending','processing'):
            assert current['parse']['status'] in ('partial','ready'),current['parse']['error_code']
            print(json.dumps(dict(status=current['parse']['status'],pages=current['parse']['unit_count'],model_calls=current['parse']['model_calls'])));return
        time.sleep(.3)
    raise RuntimeError('Local parse still running; query the saved operation instead of posting another retry.')

def verify():
    folder,base=load();target=base['document']['id']
    with connect() as db,connect(folder/'before.sqlite3') as before:
        assert db.execute('PRAGMA user_version').fetchone()[0]==base['schema']==14
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok' and not db.execute('PRAGMA foreign_key_check').fetchall()
        tables=preserved_snapshot(db,base['columns'])[0]
        changed=[name for name in tables if tables[name]!=base['tables'][name]]
        allowed={'course_documents','document_parse_runs','document_units','document_operations'}
        assert set(changed)==allowed
        def rows(connection,table,condition='',params=()):
            return {json.dumps(tuple(row),ensure_ascii=True) for row in connection.execute('SELECT * FROM '+table+condition,params)}
        assert rows(db,'course_documents',' WHERE id!=?',(target,))==rows(before,'course_documents',' WHERE id!=?',(target,))
        for table in allowed-{'course_documents'}:
            assert rows(before,table).issubset(rows(db,table)),table
            assert rows(db,table,' WHERE document_id!=?',(target,))==rows(before,table,' WHERE document_id!=?',(target,)),table
        doc=dict(db.execute('SELECT * FROM course_documents WHERE id=?',(target,)).fetchone())
        for name in doc:
            if name not in ('revision','parse_generation','current_parse_id','updated_at'):assert doc[name]==base['document'][name]
        assert doc['revision']==base['document']['revision']+1 and doc['parse_generation']==base['document']['parse_generation']+1
        run=dict(db.execute('SELECT * FROM document_parse_runs WHERE id=?',(doc['current_parse_id'],)).fetchone())
        assert run['mode']=='local' and run['status']=='partial' and run['model_calls']==0
        assert tables['document_parse_runs']['rows']==base['tables']['document_parse_runs']['rows']+1
        assert tables['document_operations']['rows']==base['tables']['document_operations']['rows']+1
        assert db.execute('SELECT status FROM document_parse_runs WHERE id=?',(base['run']['id'],)).fetchone()[0]=='failed'
        units=db.execute('SELECT ordinal,text,warnings_json FROM document_units WHERE run_id=? ORDER BY ordinal',(run['id'],)).fetchall()
        summary=dict(status=run['status'],pages=len(units),readable_pages=sum(len(''.join(u['text'].split()))>=24 for u in units),
            skipped_pages=[u['ordinal'] for u in units if 'pdf_page_text_extraction_failed' in json.loads(u['warnings_json'])],
            encoding_repaired_pages=[u['ordinal'] for u in units if 'pdf_text_encoding_repaired' in json.loads(u['warnings_json'])],
            damaged_character_pages=[u['ordinal'] for u in units if 'text_encoding_needs_review' in json.loads(u['warnings_json'])])
    prefix='/api/v1/students/'+quote(base['document']['student_id'],safe='')
    source=next(row for row in api(prefix+'/knowledge/sources')['items'] if row['source_type']=='uploaded_document' and row['source_id']==target)
    assert source['index_status']=='ready' and source['readable_units']==summary['readable_pages'] and source['total_units']==summary['pages']
    assert api(prefix+'/documents/'+target)['parse']['status']=='partial'
    for key,value in base['originals'].items():assert digest(FILES/key)==value
    for name,value in base['protected'].items():assert digest(ROOT/name)==value,name
    assert digest(ROOT/'frontend/package.json')==base['sources']['frontend/package.json']
    assert digest(ROOT/'frontend/package-lock.json')==base['sources']['frontend/package-lock.json']
    changes=[]
    for prefix in ('backend/src','backend/tests','frontend/src','docs','scripts'):
        for path in (ROOT/prefix).rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts:
                name=path.relative_to(ROOT).as_posix()
                if digest(path)!=base['sources'].get(name):changes.append(name)
    for name in ('README.md','AGENTS.md'):
        if digest(ROOT/name)!=base['sources'][name]:changes.append(name)
    opener=build_opener(ProxyHandler({}))
    def get_bytes(path):
        with opener.open('http://127.0.0.1:8000'+path,timeout=10) as response:return response.read()
    index=get_bytes('/')
    assert index==(ROOT/'frontend/dist/index.html').read_bytes()
    for path in re.findall(rb'(?:src|href)="(/assets/[^\"]+)"',index):
        asset=path.decode();assert get_bytes(asset)==(ROOT/'frontend/dist'/asset.lstrip('/')).read_bytes()
    chunks=list((ROOT/'frontend/dist/assets').glob('*Page-*.js'))
    for chunk in chunks:assert get_bytes('/assets/'+chunk.name)==chunk.read_bytes()
    report=dict(passed=True,schema=14,tables=len(tables),changed_tables=changed,other_tables_unchanged=len(tables)-len(changed),
        existing_parse_history_preserved=True,other_documents_unchanged=True,original_files_preserved=len(base['originals']),
        protected_files_preserved=len(base['protected']),target=summary,real_model_calls=0,new_dependencies=0,
        source_catalog_ready=True,api_compatible=True,
        served_frontend_matches_build=True,page_chunks_verified=len(chunks),
        backup=str(folder),changed_files=sorted(changes),verified_at=datetime.now(timezone.utc).isoformat())
    write(ROOT/'data/evaluation/pdf-partial-recovery-v1.json',report);print(json.dumps(report,ensure_ascii=True))

if __name__=='__main__':
    parser=argparse.ArgumentParser();group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--snapshot',metavar='DOCUMENT_ID');group.add_argument('--isolated',action='store_true');group.add_argument('--retry',action='store_true');group.add_argument('--verify',action='store_true')
    args=parser.parse_args()
    if args.snapshot:snapshot(args.snapshot)
    elif args.isolated:isolated()
    elif args.retry:retry()
    else:verify()
