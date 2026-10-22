"""Real isolated HTTP, synthetic model replies; production data never touched."""
import argparse,json,socket,sqlite3,subprocess,sys,threading,time
from pathlib import Path
from datetime import datetime,timezone
from urllib.request import Request,build_opener,ProxyHandler
from urllib.error import HTTPError,URLError
from uuid import uuid4

RAW='1. 简答：解释训练误差与测试误差。\n答案：测试误差用于估计泛化。'
def cmd(**kw):return dict(request_id=str(uuid4()),**kw)

def serve(folder,port):
    import uvicorn
    from eduagent.api.app import create_app
    from eduagent.api.settings import APISettings
    from eduagent.agent.settings import AgentSettings
    from eduagent.agent.deepseek import ModelReply,ModelError
    class Synthetic:
        def complete(self,messages,tools):
            assert not tools
            with (folder/'calls.jsonl').open('a') as f:f.write('{"mock":true}\n')
            mode=(folder/'mode').read_text() if (folder/'mode').exists() else 'ok'
            if mode=='timeout':raise ModelError('model_timeout')
            if mode=='hold':
                (folder/'entered').touch();deadline=time.monotonic()+20
                while not (folder/'release').exists() and time.monotonic()<deadline:time.sleep(.03)
            data=json.loads(messages[1]['content'][0]['text']);units=data['units'];raw=units[0]['text']
            has_image=any(block.get('type')=='image_url' for block in messages[1]['content'])
            if has_image:
                assert all(block.get('type')!='image_url' or block['image_url']['url'].startswith('data:image/png;base64,') for block in messages[1]['content'])
            p=dict(number='1',question_type='short_answer',stem=raw.split('\n答案：')[0] if not has_image else '解释原图中的梯度更新方向。',options=[],answer=None,answer_text=raw.split('\n答案：')[1] if '\n答案：' in raw else '',explanation='',concepts=[],dependencies=['原图'] if has_image else [])
            return ModelReply(dict(content=json.dumps(dict(questions=[dict(payload=p,source_units=[1],quotes=[raw] if raw else [])],warnings=[]))),20,50)
    app=create_app(APISettings(db_path=folder/'http.sqlite3',agent=AgentSettings(enabled=True,api_key='synthetic-only')),extraction_client_factory=lambda _:Synthetic())
    server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=port,log_level='warning',timeout_graceful_shutdown=3))
    def stop():
        while not (folder/'stop').exists():time.sleep(.05)
        server.should_exit=True
    threading.Thread(target=stop,daemon=True).start();server.run()

def verify(output):
    from eduagent.storage import migrations
    folder=Path('data/local').resolve()/('extraction-v2-http-'+uuid4().hex[:8]);folder.mkdir()
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    opener=build_opener(ProxyHandler({}));base=f'http://127.0.0.1:{port}';prefix='/api/v1/students/a';bank=prefix+'/personal-bank';checks=[];process=None;log=None;starts=0
    def http(path,body=None,method=None,expected=200,headers=None):
        request=Request(base+path,data=body if isinstance(body,bytes) else None if body is None else json.dumps(body).encode(),method=method or ('POST' if body is not None else 'GET'),headers=headers or {'Content-Type':'application/json'})
        try:r=opener.open(request,timeout=30)
        except HTTPError as e:r=e
        with r:
            raw=r.read();assert r.status==expected,(path,r.status,raw[:200]);return json.loads(raw) if raw else None
    def start():
        nonlocal process,log,starts
        (folder/'stop').unlink(missing_ok=True);starts+=1;log=(folder/f'server-{starts}.log').open('w')
        process=subprocess.Popen([sys.executable,__file__,'--serve',str(folder),'--port',str(port)],stdout=log,stderr=log,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            assert process.poll() is None,'server exited'
            try:http('/health');return
            except (OSError,URLError):time.sleep(.1)
        raise AssertionError('start timeout')
    def stop():
        if process and process.poll() is None:(folder/'stop').touch();process.wait(timeout=30)
        if log:log.close()
    def check(name):checks.append(dict(name=name,passed=True))
    def wait(key):
        deadline=time.monotonic()+25
        while time.monotonic()<deadline:
            value=http(bank+'/extraction-tasks/'+key)
            if value['status']!='running':return value
            time.sleep(.08)
        raise AssertionError('task timeout')
    def count():return len((folder/'calls.jsonl').read_text().splitlines()) if (folder/'calls.jsonl').exists() else 0
    def formal():
        with sqlite3.connect(folder/'http.sqlite3') as db:return migrations.fact_snapshot(db)
    try:
        start()
        for student in ('a','b'):http('/api/v1/students',dict(student_id=student))
        before=formal();assert http(bank+'/extraction-capabilities')['max_output_tokens']==10000
        http(bank+'/extraction-tasks',cmd(text=RAW,consent=False),expected=422);assert count()==0;check('no_consent_zero_model_transmission')
        http(bank+'/extraction-tasks',cmd(text=RAW,consent=True,student_id='b'),expected=422);check('immutable_identity_rejects_control_fields')
        body=cmd(text=RAW,consent=True);job=http(bank+'/extraction-tasks',body,expected=202);job=wait(job['request_id']);assert job['status']=='complete'
        assert http(bank+'/extraction-tasks',body,expected=202)['result']==job['result'];assert count()==1
        http(bank+'/extraction-tasks',dict(body,text=RAW+'different'),expected=409);check('durable_task_idempotency_no_second_call')
        assert http(bank.replace('/a/','/b/')+'/extraction-tasks')['items']==[]
        http(bank.replace('/a/','/b/')+'/extraction-tasks/'+job['request_id'],expected=404);check('task_scope_isolated')
        q=http(bank+'/questions/'+job['result']['question_ids'][0]);assert q['payload']['question_type']=='short_answer' and not q['payload']['options']
        http(bank+'/questions/'+q['id'],cmd(expected_revision=1,payload=q['payload'],status='practice',reviewed=True,confirm_answer=True),'PUT');check('semantic_to_reviewed_subjective_question')
        sid=http(bank+'/practice',cmd(question_id=q['id']))['session_id']
        draft=cmd(expected_revision=0,response_text='我的解答 $x^2$',needs_review=True)
        http(bank+'/practice/'+sid+'/draft',draft,'PUT');assert http(bank+'/practice/'+sid+'/draft',draft,'PUT')['replayed']
        http(bank+'/practice/'+sid+'/draft',cmd(expected_revision=0,response_text='old',needs_review=False),'PUT',expected=409)
        assert http(bank+'/practice/'+sid)['draft']['response_text']=='我的解答 $x^2$';check('text_draft_restore_idempotency_conflict')
        answer=http(bank+'/practice/'+sid+'/answer',cmd(selected_answer='我的解答 $x^2$',needs_review=True))['result']
        assert answer['score'] is None and answer['needs_review'] and answer['bkt_updated'] is False
        assert http(bank+'/practice?wrong_only=true')['items']==[];check('subjective_response_never_scores_or_enters_objective_wrong_answers')
        # Re-extraction creates a separate proposal, accepted only by explicit CAS.
        source=job['source'];target=http(bank+'/questions/'+q['id'])
        proposal=http(bank+'/extraction-tasks',cmd(resource_id=source['resource_id'],source_version=source['source_version'],consent=True,target_question_id=q['id'],target_revision=target['revision']),expected=202)
        proposal=wait(proposal['request_id']);pq=http(bank+'/questions/'+proposal['result']['question_ids'][0]);assert http(bank+'/questions/'+q['id'])['revision']==target['revision']
        accept=cmd(expected_revision=target['revision'],proposal_id=pq['id'],proposal_revision=pq['revision'])
        changed=http(bank+'/questions/'+q['id']+'/accept-proposal',accept);assert http(bank+'/questions/'+q['id']+'/accept-proposal',accept)['replayed']
        assert changed['revision']==3 and http(bank+'/questions/'+q['id'])['status']=='draft';check('proposal_preview_keep_original_then_explicit_revision_accept')
        # Source update while a synthetic network call waits: no SQLite write lock.
        nid=str(uuid4());note=http(prefix+'/notes',dict(id=nid,title='scope note',content_md=RAW),expected=201)
        resource=next(r for r in http(prefix+'/course-resources')['items'] if r['original_source_id']==nid)
        (folder/'mode').write_text('hold');race=http(bank+'/extraction-tasks',cmd(resource_id=resource['resource_id'],source_version=resource['source_version'],consent=True),expected=202)
        deadline=time.monotonic()+8
        while not (folder/'entered').exists() and time.monotonic()<deadline:time.sleep(.05)
        assert (folder/'entered').exists()
        http(prefix+'/notes/'+nid,dict(expected_revision=1,content_md=RAW+'\n已修改'),'PATCH');(folder/'release').touch()
        assert wait(race['request_id'])['status']=='stale';check('write_during_network_succeeds_and_stale_source_never_publishes')
        (folder/'mode').write_text('timeout');timeout=http(bank+'/extraction-tasks',cmd(text=RAW,consent=True),expected=202)
        assert wait(timeout['request_id'])['status']=='uncertain';calls=count()
        for _ in range(3):http(bank+'/extraction-tasks/'+timeout['request_id'])
        assert count()==calls;check('model_timeout_uncertain_no_automatic_retry')
        # Canonical model-free path is still callable while the model is failing.
        local=http(bank+'/extractions',cmd(text='1. 证明：$x^2>=0$。'))
        assert http(bank+'/questions/'+local['question_ids'][0])['payload']['question_type']=='proof' and count()==calls;check('offline_rules_independent_of_model')
        assert formal()==before;check('formal_learning_facts_unchanged')
        stop();start();assert http(bank+'/practice/'+sid)['result']==answer and http(bank+'/extraction-tasks/'+timeout['request_id'])['status']=='uncertain' and count()==calls;check('restart_restores_tasks_attempts_no_model_reissue')
        assert formal()==before
        report=dict(passed=True,verified_at=datetime.now(timezone.utc).isoformat(),groups=len(checks),checks=checks,server_starts=starts,simulated_model_calls=count(),real_model_calls=0,production_data_touched=False,directory=str(folder))
        output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(dict(passed=True,groups=len(checks),mock_calls=count(),report=str(output))))
    finally:stop()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--serve',type=Path);p.add_argument('--port',type=int);p.add_argument('--output',type=Path,default=Path('data/evaluation/extraction-v2-http-v1.json'));a=p.parse_args()
    if a.serve:serve(a.serve,a.port)
    else:verify(a.output)
