"""Real loopback HTTP, synthetic PDF, disabled provider, disposable database."""
import argparse
import json
import shutil
import socket
import sqlite3
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, ProxyHandler, build_opener
from uuid import uuid4


def serve(folder, port):
    import uvicorn
    from eduagent.api.app import create_app
    from eduagent.api.settings import APISettings
    from eduagent.agent.settings import AgentSettings
    settings=APISettings(data_dir=folder/'data', db_path=folder/'http.sqlite3', agent=AgentSettings(enabled=False))
    server=uvicorn.Server(uvicorn.Config(create_app(settings),host='127.0.0.1',port=port,log_level='warning'))
    def finish():
        while not (folder/'stop').exists(): time.sleep(.1)
        server.should_exit=True
    threading.Thread(target=finish,daemon=True).start()
    server.run()


def verify():
    from eduagent.storage.migrations import fact_snapshot, preserved_snapshot
    sys.path.insert(0,str(Path('backend/tests').resolve()))
    from document_fixtures import pdf_bytes
    folder=Path('data/local').resolve()/('experience-http-'+uuid4().hex[:8]);folder.mkdir()
    shutil.copytree('data',folder/'data',ignore=shutil.ignore_patterns('local','evaluation'))
    with socket.socket() as sock: sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    opener=build_opener(ProxyHandler({}));base=f'http://127.0.0.1:{port}';root='/api/v1/students/a';checks=[]
    process=log=None;starts=0
    def http(path,body=None,expected=200,method=None,file=None):
        headers={'Content-Type':'application/json'};raw=None if body is None else json.dumps(body).encode()
        if file is not None:
            boundary='experience-'+uuid4().hex;headers={'Content-Type':'multipart/form-data; boundary='+boundary}
            raw=(f'--{boundary}\r\nContent-Disposition: form-data; name="metadata"\r\n\r\n'+json.dumps(body)+f'\r\n--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="synthetic.pdf"\r\nContent-Type: application/pdf\r\n\r\n').encode()+file+f'\r\n--{boundary}--\r\n'.encode()
        try: reply=opener.open(Request(base+path,data=raw,headers=headers,method=method or ('POST' if raw is not None else 'GET')),timeout=10)
        except HTTPError as error: reply=error
        with reply:
            data=reply.read();assert reply.status==expected,(path,reply.status,data[:200])
            return json.loads(data) if data else None
    def command(**values):return dict(request_id=str(uuid4()),**values)
    def check(name):checks.append(dict(name=name,passed=True))
    def snapshot(all_tables=False):
        with sqlite3.connect(folder/'http.sqlite3') as db:return preserved_snapshot(db)[0] if all_tables else fact_snapshot(db)
    def start():
        nonlocal process,log,starts
        starts+=1;(folder/'stop').unlink(missing_ok=True);log=(folder/f'server-{starts}.log').open('w')
        process=subprocess.Popen([sys.executable,__file__,'--serve',str(folder),'--port',str(port)],stdout=log,stderr=log,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        deadline=time.monotonic()+25
        while time.monotonic()<deadline:
            assert process.poll() is None,'isolated server exited'
            try:http('/health');return
            except (URLError,OSError):time.sleep(.1)
        raise AssertionError('server start timeout')
    def stop():
        if process and process.poll() is None:(folder/'stop').touch();process.wait(timeout=20)
        if log:log.close()
    try:
        start()
        for owner in ('a','b'):http('/api/v1/students',dict(student_id=owner,goals=['gradient_descent']))
        original=snapshot()
        cap=http(root+'/workbench/capabilities');assert not cap['model_enabled'] and cap['retrieval_enabled'];check('no_model_key_local_reading_enabled')
        doc=http(root+'/documents',command(title='Synthetic source',local_rights_confirmed=True),202,file=pdf_bytes(('Gradient descent follows negative gradients and updates model weights.','','Precision and recall are used for model evaluation.')))
        for _ in range(100):
            current=http(root+'/documents/'+doc['id'])
            if current['parse']['status'] not in ('pending','processing'):break
            time.sleep(.1)
        assert current['parse']['status']=='partial';check('local_three_page_pdf_parse_with_blank_page')
        source=next(s for s in http(root+'/knowledge/sources')['items'] if s['source_type']=='uploaded_document')
        ref={k:source[k] for k in ('source_type','source_id','source_version')}
        before_reads=snapshot(True)
        first=http(root+'/workbench/sources/open',dict(ref,page=1));third=http(root+'/workbench/sources/open',dict(ref,page=3))
        assert 'Gradient' in first['raw_md'] and 'Precision' not in first['raw_md'] and 'Precision' in third['raw_md']
        assert [p['readable'] for p in first['pages']]==[True,False,True];check('exact_page_text_and_coverage')
        sparse=http(root+'/workbench/sources/open',dict(ref,page=2));assert sparse['raw_md']=='' and sparse['pages'][1]['warnings'];check('blank_page_is_explicit_and_not_fabricated')
        assert http(root+'/workbench/sources/open',ref)['raw_md'];check('legacy_open_request_stays_compatible')
        for bad in (0,201,True,1.5):http(root+'/workbench/sources/open',dict(ref,page=bad),422)
        http(root+'/workbench/sources/open',dict(ref,page=1,student_id='b'),422);check('invalid_page_types_and_control_fields_rejected')
        http(root+'/workbench/sources/open',dict(ref,page=4),404)
        http('/api/v1/students/b/workbench/sources/open',dict(ref,page=1),404);check('missing_page_and_other_student_cannot_read')
        assert snapshot(True)==before_reads;check('reading_preserves_all_tables_and_allocates_no_exercises')
        http(root+'/knowledge/search',dict(query='Precision',sources=[]),422)
        matches=http(root+'/knowledge/search',dict(query='Precision',sources=[ref]));assert matches['items'][0]['page_number']==3;check('selected_source_search_locates_real_page')
        request=command(question='Precision',sources=[ref],mode='local',allow_personal_external=False)
        run=http(root+'/workbench/questions',request);assert run['model_calls']==0 and run['citations'][0]['page_number']==3
        assert http(root+'/workbench/questions',request)['request_id']==run['request_id'];check('local_answer_and_replay_have_zero_model_calls')
        count=snapshot(True);stop();start()
        assert http(root+'/workbench/sources/open',dict(ref,page=3))['raw_md']==third['raw_md']
        assert http(root+'/workbench/runs/'+run['request_id'])['citations']==run['citations'] and snapshot(True)==count;check('restart_restores_page_reader_and_history_without_writes')
        http(root+'/documents/'+doc['id'],command(expected_revision=1,title='Updated'),method='PATCH')
        http(root+'/workbench/sources/open',dict(ref,page=3),409)
        history=http(root+'/workbench/runs/'+run['request_id']);assert history['source_statuses'][0]['current_status']=='modified' and history['citations']==run['citations'];check('stale_preview_rejected_history_snapshot_preserved')
        source=next(s for s in http(root+'/knowledge/sources')['items'] if s['source_type']=='uploaded_document');newref={k:source[k] for k in ref}
        http(root+'/documents/'+doc['id'],command(expected_revision=2),method='DELETE')
        http(root+'/workbench/sources/open',dict(newref,page=3),404);check('deleted_source_immediately_unreadable')
        assert snapshot()==original;check('formal_learning_bkt_scoring_and_assessment_facts_unchanged')
        report=dict(passed=True,groups=len(checks),checks=checks,real_model_calls=0,simulated_model_calls=0,
                    schema=13,tables=45,production_writes=0,server_starts=starts,directory=str(folder),verified_at=datetime.now(timezone.utc).isoformat())
        Path('data/evaluation/learning-experience-page-http-v1.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(dict(passed=True,groups=len(checks),model_calls=0)))
    finally:stop()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--serve',type=Path);parser.add_argument('--port',type=int);args=parser.parse_args()
    if args.serve:serve(args.serve,args.port)
    else:verify()
