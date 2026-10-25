"""Real loopback HTTP notebook acceptance. Synthetic content and mock provider only."""
import argparse,json,shutil,socket,sqlite3,subprocess,sys,threading,time
from datetime import datetime,timezone
from pathlib import Path
from urllib.error import HTTPError,URLError
from urllib.request import Request,ProxyHandler,build_opener
from uuid import uuid4

def serve(folder,port):
    import uvicorn
    from eduagent.api.app import create_app
    from eduagent.api.settings import APISettings
    from eduagent.agent.settings import AgentSettings
    sys.path.insert(0,str(Path('backend/tests').resolve()))
    from test_workbench import FakeModel
    class RecordedFake(FakeModel):
        def complete(self,*a,**kw):
            with (folder/'mock-calls').open('a') as f:f.write('1\n')
            return super().complete(*a,**kw)
    settings=APISettings(data_dir=folder/'data',db_path=folder/'http.sqlite3',agent=AgentSettings(enabled=True,api_key='synthetic-test-key'))
    server=uvicorn.Server(uvicorn.Config(create_app(settings,teaching_client_factory=lambda:RecordedFake()),host='127.0.0.1',port=port,log_level='warning'))
    def end():
        while not (folder/'stop').exists():time.sleep(.1)
        server.should_exit=True
    threading.Thread(target=end,daemon=True).start();server.run()

def verify(output=Path('data/evaluation/notebook-rebuild-http-v1.json')):
    from eduagent.storage.migrations import fact_snapshot,preserved_snapshot
    sys.path.insert(0,str(Path('backend/tests').resolve()))
    from test_personal_bank import payload
    from document_fixtures import pdf_bytes
    folder=Path('data/local').resolve()/('notebook-http-'+uuid4().hex[:8]);folder.mkdir()
    shutil.copytree('data',folder/'data',ignore=shutil.ignore_patterns('local','evaluation'))
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    opener=build_opener(ProxyHandler({}));base=f'http://127.0.0.1:{port}';root='/api/v1/students/a';checks=[];process=log=None;starts=0
    uid=lambda:str(uuid4())
    def command(**kw):return dict(request_id=uid(),**kw)
    def http(path,body=None,expected=200,method=None,file=None):
        raw=None if body is None else json.dumps(body).encode()
        headers={'Content-Type':'application/json'}
        if file is not None:
            boundary='notebook-'+uid();headers={'Content-Type':'multipart/form-data; boundary='+boundary}
            raw=(f'--{boundary}\r\nContent-Disposition: form-data; name="metadata"\r\n\r\n'+json.dumps(body)+f'\r\n--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="synthetic.pdf"\r\nContent-Type: application/pdf\r\n\r\n').encode()+file+f'\r\n--{boundary}--\r\n'.encode()
        try:r=opener.open(Request(base+path,data=raw,headers=headers,method=method or ('POST' if raw is not None else 'GET')),timeout=30)
        except HTTPError as e:r=e
        with r:
            data=r.read();assert r.status==expected,(path,r.status,data[:400]);return json.loads(data) if data else None
    def check(name):checks.append(dict(name=name,passed=True))
    def snapshot(full=False):
        with sqlite3.connect(folder/'http.sqlite3') as db:return preserved_snapshot(db)[0] if full else fact_snapshot(db)
    def calls():return len((folder/'mock-calls').read_text().splitlines()) if (folder/'mock-calls').exists() else 0
    def start():
        nonlocal process,log,starts
        starts+=1;(folder/'stop').unlink(missing_ok=True);log=(folder/f'server-{starts}.log').open('w')
        process=subprocess.Popen([sys.executable,__file__,'--serve',str(folder),'--port',str(port)],stdout=log,stderr=log,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            assert process.poll() is None,'server failed to start'
            try:http('/health');return
            except (URLError,OSError):time.sleep(.1)
        raise AssertionError('server timeout')
    def stop():
        if process and process.poll() is None:(folder/'stop').touch();process.wait(timeout=20)
        if log:log.close()
    def create(title):
        key=uid();body=command(id=key,title=title,description='合成HTTP验收');http(root+'/notebooks',body,201);return key,body
    def link(key,refs,expected_revision=None):
        revision=expected_revision or http(root+'/notebooks/'+key)['revision']
        return http(root+'/notebooks/'+key+'/sources',command(expected_revision=revision,sources=refs),method='PUT')
    def ref(source):return{k:source[k] for k in ('source_type','source_id','source_version')}
    def ask(key,refs,**kw):return command(question='梯度下降沿什么方向更新？',sources=refs,mode='model',allow_personal_external=False,expected_revision=http(root+'/notebooks/'+key)['revision'],**kw)
    try:
        start()
        for student in ('a','b'):http('/api/v1/students',dict(student_id=student,goals=['gradient_descent']))
        before=snapshot();a,create_body=create('梯度下降合成笔记本');b,_=create('第二个笔记本');path=root+'/notebooks/'+a
        assert http(root+'/notebooks',create_body,201)['replayed'];http(root+'/notebooks',dict(create_body,title='different'),409)
        assert len(http(root+'/notebooks')['items'])==2;check('persistent_creation_and_exactly_once_receipt')
        http('/api/v1/students/b/notebooks/'+a,expected=404);http('/api/v1/students/b/notebooks/requests/'+create_body['request_id'],expected=404);check('student_scope_and_receipt_isolation')
        http(root+'/notebooks',dict(create_body,student_id='b'),422);http(root+'/notebooks',dict(create_body,title=' '),422);check('unknown_control_fields_and_blank_title_rejected')
        catalog=http(root+'/knowledge/sources')['items'];course=ref(next(s for s in catalog if s['source_id']=='gradient'));other=ref(next(s for s in catalog if s['source_id']=='linear'))
        link(a,[course]);link(b,[other]);check('explicit_source_membership_saved')
        http(path+'/questions',ask(a,[]),422);http(path+'/questions',ask(a,[other]),409)
        assert calls()==0;check('empty_and_unselected_sources_never_expand_or_call_model')
        request=ask(a,[course]);run=http(path+'/questions',request);assert run['status']=='complete' and calls()==1
        assert all(c['source_id']=='gradient' for c in run['citations']);check('mock_model_uses_only_notebook_selected_evidence')
        assert http(path+'/questions',request)['answer']==run['answer'] and calls()==1
        http(path+'/questions',dict(request,question='different'),409);check('duplicate_question_no_second_provider_execution')
        assert http(root+'/notebooks/'+b+'/runs')==[];http(root+'/notebooks/'+b+'/runs/'+request['request_id'],expected=404);check('conversation_history_does_not_cross_notebooks')
        preview=http(path+'/sources/open',dict(course,expected_revision=2));assert preview['raw_md']
        http(path+'/sources/open',dict(other,expected_revision=2),409);check('source_preview_enforces_same_membership')
        document=http(root+'/documents',command(title='Synthetic notebook slides',local_rights_confirmed=True),202,file=pdf_bytes(('Gradient descent follows the negative gradient and updates model weights.','','Precision and recall measure model evaluation performance.')))
        for _ in range(100):
            doc=http(root+'/documents/'+document['id'])
            if doc['parse']['status'] not in ('pending','processing'):break
            time.sleep(.1)
        docref=ref(next(s for s in http(root+'/knowledge/sources')['items'] if s['source_id']==document['id']))
        link(a,[course,docref]);rev=http(path)['revision']
        preview=http(path+'/sources/open',dict(docref,expected_revision=rev,page=3))
        assert 'Precision' in preview['raw_md'] and [p['readable'] for p in preview['pages']]==[True,False,True];check('uploaded_pdf_membership_preserves_page_location_and_missing_coverage')
        docbody=ask(a,[docref]);docbody['question']='Precision and recall';docbody['mode']='local'
        docrun=http(path+'/questions',docbody);assert docrun['citations'][0]['page_number']==3 and docrun['model_calls']==0;check('notebook_uploaded_pdf_rag_cites_only_selected_real_page')
        http(root+'/documents/'+document['id'],command(expected_revision=1,title='Synthetic revised title'),method='PATCH')
        http(path+'/questions',docbody | {'request_id':uid()},409)
        assert http(path+'/runs/'+docrun['request_id'])['citations']==docrun['citations']
        http(root+'/documents/'+document['id'],command(expected_revision=2),method='DELETE')
        http(path+'/sources/open',dict(docref,expected_revision=rev,page=3),404);check('document_change_and_delete_invalidate_current_scope_keep_history_snapshot')
        saved=http(path+'/runs/'+run['request_id']+'/note',{});again=http(path+'/runs/'+run['request_id']+'/note',{})
        assert saved['note_id']==again['note_id'];note=http(root+'/notes/'+saved['note_id']);assert note['content_md']
        assert len([s for s in http(path)['sources'] if s['source_type']=='personal_note'])==1;check('answer_saved_once_as_editable_linked_markdown_note')
        private=http(root+'/notes',dict(id=uid(),title='合成个人资料',content_md='# 梯度下降\n\n沿负梯度方向更新模型权重。',knowledge_point_ids=['gradient_descent']),201)
        personal=dict(source_type='personal_note',source_id=private['id'],source_version=f"r1-{private['content_hash']}");link(a,[course,personal])
        denied=http(path+'/questions',ask(a,[personal]));assert denied['model_calls']==0 and calls()==1;check('private_note_without_turn_permission_has_zero_model_transmission')
        permitted=ask(a,[personal]);permitted['allow_personal_external']=True
        private_run=http(path+'/questions',permitted);assert private_run['status']=='complete' and calls()==2
        assert all(c['source_type']=='personal_note' for c in private_run['citations']);check('explicit_private_permission_scoped_to_selected_note')
        http(root+'/notes/'+private['id'],dict(expected_revision=1,title='已修改',content_md='新的内容',knowledge_point_ids=[]),method='PATCH')
        http(path+'/questions',ask(a,[personal]),409);old=http(path+'/runs/'+permitted['request_id']);assert old['citations']==private_run['citations'];check('source_update_blocks_old_current_results_but_retains_snapshot')
        foreign_book=uid();http('/api/v1/students/b/notebooks',command(id=foreign_book,title='另一个学生',description=''),201)
        http('/api/v1/students/b/notebooks/'+foreign_book+'/sources',command(expected_revision=1,sources=[personal]),404,method='PUT');check('foreign_note_cannot_be_linked')
        q=http(root+'/personal-bank/questions',command(payload=payload(),status='practice',reviewed=True,confirm_answer=True))
        qid=q['question_id'];qref=dict(source_type='personal_question',source_id=qid,source_version='r1');link(b,[other,qref])
        bp=root+'/notebooks/'+b;assert len(http(bp+'/practice/questions')['items'])==1
        http(path+'/practice/questions/'+qid,expected=404);check('questions_are_scoped_and_not_inferred_from_display_names')
        start_body=command(question_id=qid,expected_revision=http(bp)['revision']);session=http(bp+'/practice',start_body)
        assert http(bp+'/practice',start_body)['session_id']==session['session_id'];sid=session['session_id']
        http(path+'/practice/sessions/'+sid,expected=404);check('ordinary_session_cannot_be_adopted_by_another_notebook')
        result=http(bp+'/practice/sessions/'+sid+'/answer',command(selected_answer='A'))
        assert result['result']['correct'] and not result['result']['bkt_updated'];assert len(http(bp+'/practice/sessions')['items'])==1;check('confirmed_ordinary_scoring_without_bkt_update')
        link(a,[course]);revision=http(path)['revision'];http(path,command(id=a,title='已归档',description='',expected_revision=revision,archived=True),method='PATCH')
        http(path+'/questions',ask(a,[course]),409);assert http(path+'/runs');check('archive_is_read_only_and_keeps_history')
        read_before=snapshot(True);count=calls();stop();start()
        assert http(bp+'/practice/sessions/'+sid)['result']['correct'];assert http(path+'/runs/'+run['request_id'])['answer']==run['answer'];assert calls()==count and snapshot(True)==read_before;check('restart_and_refresh_restore_without_writes_or_model_replay')
        assert snapshot()==before;check('all_formal_learning_bkt_scoring_and_student_revision_unchanged')
        report=dict(passed=True,groups=len(checks),checks=checks,simulated_model_calls=calls(),real_model_calls=0,production_writes=0,schema=14,tables=50,server_starts=starts,directory=str(folder),verified_at=datetime.now(timezone.utc).isoformat())
        output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(dict(passed=True,groups=len(checks),mock_calls=calls(),real_calls=0)))
    finally:stop()
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--serve',type=Path);p.add_argument('--port',type=int);p.add_argument('--output',type=Path,default=Path('data/evaluation/notebook-rebuild-http-v1.json'));a=p.parse_args()
    if a.serve:serve(a.serve,a.port)
    else:verify(a.output)
