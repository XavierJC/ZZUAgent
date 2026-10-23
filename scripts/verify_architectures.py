"""Isolated real HTTP architecture acceptance. No model clients are enabled."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import json
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import threading
import time
from urllib.request import Request,build_opener,ProxyHandler
from urllib.error import HTTPError,URLError
from uuid import uuid4


def serve(folder,port):
    import uvicorn
    from eduagent.api.app import create_app
    from eduagent.api.settings import APISettings
    server=uvicorn.Server(uvicorn.Config(create_app(APISettings(db_path=folder/'http.sqlite3')),host='127.0.0.1',port=port,log_level='warning',timeout_graceful_shutdown=3))
    def stop():
        while not (folder/'stop').exists(): time.sleep(.03)
        server.should_exit=True
    threading.Thread(target=stop,daemon=True).start();server.run()


def verify(output):
    from eduagent.storage.migrations import preserved_snapshot,ARCHITECTURE_TABLES,DOCUMENT_TABLES
    sys.path.insert(0,str(Path('backend/tests').resolve()))
    from document_fixtures import pptx_bytes
    from test_architectures import example
    folder=Path('data/local').resolve()/('phase4b2-http-'+uuid4().hex[:8]);folder.mkdir()
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    base=f'http://127.0.0.1:{port}';opener=build_opener(ProxyHandler({}));process=None;log=None;starts=0;checks=[]
    prefix='/api/v1/students/a/knowledge-architectures'
    def http(path,body=None,method=None,expected=200,headers=None):
        request=Request(base+path,data=body if isinstance(body,bytes) else None if body is None else json.dumps(body).encode(),method=method or ('POST' if body is not None else 'GET'),headers=headers or {'Content-Type':'application/json'})
        try: response=opener.open(request,timeout=30)
        except HTTPError as exc: response=exc
        with response:
            raw=response.read();assert response.status in ((expected,) if isinstance(expected,int) else expected),(path,response.status,raw[:220])
            return json.loads(raw) if raw else None
    def start():
        nonlocal process,log,starts
        (folder/'stop').unlink(missing_ok=True);starts+=1;log=(folder/f'server-{starts}.log').open('w',encoding='utf8')
        process=subprocess.Popen([sys.executable,__file__,'--serve',str(folder),'--port',str(port)],stdout=log,stderr=log,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            assert process.poll() is None,'isolated server exited'
            try:http('/health');return
            except (URLError,OSError):time.sleep(.1)
        raise AssertionError('server timeout')
    def stop():
        if process and process.poll() is None:(folder/'stop').touch();process.wait(timeout=30)
        if log:log.close()
    def check(name): checks.append(dict(name=name,passed=True))
    def mutate(revision,**extra):return dict(request_id=str(uuid4()),expected_revision=revision,**extra)
    def facts(exclude=()):
        with sqlite3.connect((folder/'http.sqlite3').as_uri()+'?mode=ro',uri=True) as db:return {k:v for k,v in preserved_snapshot(db)[0].items() if k not in ARCHITECTURE_TABLES+tuple(exclude)}
    def upload(raw,name):
        boundary=uuid4().hex;meta=dict(request_id=str(uuid4()),title='合成课件',local_rights_confirmed=True)
        data=f'--{boundary}\r\nContent-Disposition: form-data; name="metadata"\r\n\r\n{json.dumps(meta)}\r\n--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{name}"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode()+raw+f'\r\n--{boundary}--\r\n'.encode()
        doc=http('/api/v1/students/a/documents',data,expected=202,headers={'Content-Type':'multipart/form-data; boundary='+boundary})
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            current=http('/api/v1/students/a/documents/'+doc['id'])
            if current['parse']['status'] not in ('pending','processing'):assert current['parse']['status'] in ('ready','partial');return current
            time.sleep(.05)
        raise AssertionError('native parser timeout')
    try:
        start()
        for student in ('a','b'):http('/api/v1/students',dict(student_id=student))
        doc=upload('# 梯度下降\n\n定义：学习率\n\n# 课堂安排\n\n1. 这是普通列表而非章节。'.encode(),'course.md')
        slides=upload(pptx_bytes(),'course.pptx');before=facts()
        request=dict(request_id=str(uuid4()),name='测试课程体系')
        with ThreadPoolExecutor(max_workers=2) as pool:created=list(pool.map(lambda _:http(prefix,request),range(2)))
        assert sorted(c['replayed'] for c in created)==[False,True] and len(http(prefix)['items'])==1
        key=created[0]['architecture_id'];path=prefix+'/'+key
        http(prefix,{**request,'name':'conflict'},expected=409);check('create_concurrent_idempotency_hash_conflict')
        g=example();body=mutate(1,graph=g);http(path+'/draft',body,'PUT');http(path+'/draft',body,'PUT')
        saved=http(path);assert len(saved['draft']['graph']['concepts'])==2 and len(saved['draft']['graph']['concepts'][0]['chapter_ids'])==2
        http(path+'/published',expected=404);check('manual_multi_chapter_same_name_identity_and_unpublished_navigation')
        bad=json.loads(json.dumps(g));bad['chapters'][0]['parent_id']=bad['chapters'][1]['id']
        assert http(path+'/draft',mutate(2,graph=bad),'PUT',expected=422)['error']['code']=='architecture_cycle'
        assert http(path)['revision']==2;check('chapter_cycle_rejected_atomically')
        bad=json.loads(json.dumps(g));r=bad['relations'][0];r['kind']='related_to';bad['relations'].append(dict(r,id=str(uuid4()),source_id=r['target_id'],target_id=r['source_id']))
        http(path+'/draft',mutate(2,graph=bad),'PUT',expected=422)
        bad['relations']=[];bad['concepts'].pop();bad['chapters'].pop()
        http(path+'/draft',mutate(2,graph=bad),'PUT',expected=422);check('symmetric_relation_uniqueness_and_referenced_delete')
        http(path+'/publish',mutate(2,confirmed=False),expected=422)
        http(path+'/publish',mutate(2,confirmed=1),expected=422)
        http(path+'/publish',mutate(2,confirmed=True));v1=http(path+'/published')
        assert v1['graph']['relations'][0]['kind']=='prerequisite_candidate'
        http(path+'/draft',mutate(3,graph=g),'PUT',expected=409);check('explicit_confirmation_and_locked_publication')
        http(path+'/draft',mutate(3,version=1));g['concepts'][0]['name']='重命名保留身份'
        update=mutate(4,graph=g);http(path+'/draft',update,'PUT');http(path+'/publish',mutate(5,confirmed=True))
        assert http(path+'/versions/1')==v1
        assert http(path+'/published')['graph']['concepts'][0]['id']==g['concepts'][0]['id'];check('stable_ids_fork_and_immutable_version_history')
        for endpoint in (path,path+'/published',path+'/versions/1',prefix+'/requests/'+request['request_id']):http(endpoint.replace('/a/','/b/'),expected=404)
        assert http(prefix.replace('/a/','/b/'))['items']==[];check('demo_student_isolation')
        state=http(path+'/concepts/'+g['concepts'][0]['id']+'/learning-state')
        assert state['items'][0]['objective']['probability'] is None and state['items'][0]['status']=='pending_diagnosis'
        assert facts()==before;check('all_original_twenty_one_tables_preserved_by_manual_graph_operations')
        # Synthetic scoring is intentionally separate from structure operations.
        decision=http('/api/v1/students/a/next',{},'POST')
        http('/api/v1/students/a/answers',dict(decision_id=decision['decision_id'],event_id=str(uuid4()),answer='B'))
        http('/api/v1/students/a/self-assessments',dict(request_id=str(uuid4()),expected_revision=0,items=[dict(knowledge_id='linear_regression_loss',level=3,confidence=4)]),expected=201)
        state=http(path+'/concepts/'+g['concepts'][0]['id']+'/learning-state')
        assert state['items'][0]['objective']['attempts']==1 and state['items'][0]['self_report']['confidence']==4
        check('readonly_formal_association_reads_real_scoring_and_self_report')
        baseline=facts();candidate_system=http(prefix,dict(request_id=str(uuid4()),name='候选体系'))['architecture_id'];cp=prefix+'/'+candidate_system
        selection=lambda d:dict(document_id=d['id'],version_id=d['version']['id'],run_id=d['parse']['id'])
        req=mutate(1,documents=[selection(doc),selection(slides)])
        receipt=http(cp+'/candidates',req);batch=http(cp+'/candidates/'+receipt['batch_id'])
        assert batch['graph']['chapters'] and batch['graph']['concepts'] and batch['graph']['relations']==[]
        assert len(batch['graph']['chapters'])==3 # two Markdown headings + one visible PPTX slide
        assert any(u['reason']=='hidden_slide' for u in batch['unclassified'])
        for e in batch['evidence']:
            units=http('/api/v1/students/a/documents/'+e['document_id']+'/units')['items'];unit=next(u for u in units if u['id']==e['unit_id'])
            assert unit['text'][e['start_offset']:e['end_offset']]==e['raw_text']
        check('actual_native_markdown_pptx_candidate_extraction_and_evidence_offsets')
        assert http(cp+'/candidates',req)['replayed'] and http(cp+'/published',expected=404)
        candidate=batch['graph'];candidate['name']='已编辑候选体系';candidate['concepts'][0]['summary']='人工核对后编辑'
        http(cp+'/draft',mutate(1,graph=candidate),'PUT');assert facts()==baseline
        http(cp+'/publish',mutate(2,confirmed=True));check('editable_preview_import_confirmation_and_no_learning_writes')
        http(cp+'/draft',mutate(3,version=1));candidate['description']='new draft'
        http(cp+'/draft',mutate(3,graph=candidate),'PUT',expected=409)
        # Two writers at the same independent revision: exactly one wins.
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda name:http(cp+'/draft',mutate(4,graph={**candidate,'name':name}),'PUT',expected=(200,409)),('writer one','writer two')))
        assert sum('error' not in x for x in results)==1;check('independent_revision_concurrent_writer_cas')
        core=facts(DOCUMENT_TABLES)
        http('/api/v1/students/a/documents/'+doc['id'],dict(request_id=str(uuid4()),expected_revision=doc['revision'],title='来源修改'),'PATCH')
        assert any(e['current_status']=='metadata_modified' for e in http(cp+'/candidates/'+batch['id'])['evidence'])
        http(cp+'/publish',mutate(5,confirmed=True),expected=409)
        published=http(cp+'/published');assert any(e['current_status']=='metadata_modified' for e in published['sources'])
        check('updated_source_blocks_old_candidates_and_labels_historical_evidence')
        http('/api/v1/students/a/documents/'+slides['id'],dict(request_id=str(uuid4()),expected_revision=slides['revision']),'DELETE')
        assert any(e['current_status']=='deleted' for e in http(cp+'/candidates/'+batch['id'])['evidence'])
        http(cp.replace('/a/','/b/')+'/candidates/'+batch['id'],expected=404);check('deleted_source_snapshot_semantics_and_candidate_isolation')
        assert facts(DOCUMENT_TABLES)==core;check('bkt_scores_self_reports_notes_and_learning_history_unchanged_by_structures')
        current=http(cp);stop();start()
        assert http(cp)['draft']['graph']==current['draft']['graph'] and http(path+'/versions/1')==v1
        assert http('/api/v1/materials/search',dict(query='梯度下降')) and http('/health')['agent_enabled'] is False
        check('restart_and_no_key_local_retrieval_compatible')
        with sqlite3.connect(folder/'http.sqlite3') as db:
            assert db.execute('pragma user_version').fetchone()[0]==12
            assert db.execute('pragma integrity_check').fetchone()[0]=='ok' and not db.execute('pragma foreign_key_check').fetchall()
        check('schema9_integrity_foreign_keys')
        report=dict(passed=True,verified_at=datetime.now(timezone.utc).isoformat(),checks=checks,server_starts=starts,schema=12,
            real_model_calls=0,simulated_model_calls=0,production_writes=0,browser_manual_validation='not_performed',test_directory=str(folder),
            synthetic_learning_events=1,scope='Self-built uploaded files through actual parser and real HTTP, no teacher-material external transmission')
        output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
        print(json.dumps(dict(passed=True,checks=len(checks),model_calls=0,report=str(output))))
    finally:stop()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--serve',type=Path);parser.add_argument('--port',type=int)
    parser.add_argument('--output',type=Path,default=Path('data/evaluation/phase4b2-http-v1.json'));args=parser.parse_args()
    if args.serve:serve(args.serve,args.port)
    else:verify(args.output)
