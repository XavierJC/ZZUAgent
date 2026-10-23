"""Real PDF content + real isolated HTTP services; scripted approvals and mocked chat only."""
import argparse,json,shutil,socket,sqlite3,subprocess,sys,threading,time
from pathlib import Path
from datetime import datetime,timezone
from uuid import uuid4
import httpx

def cmd(**kw):return dict(request_id=str(uuid4()),**kw)
def serve(folder,port):
    import uvicorn
    from eduagent.api.app import create_app
    from eduagent.api.settings import APISettings
    from eduagent.agent.settings import AgentSettings
    from eduagent.agent.deepseek import ModelReply
    class Model:
        def complete(self,messages,tools):
            data=json.loads(messages[1]['content']);assert data.get('server_learning_context')
            evidence=data['untrusted_evidence'];assert evidence and all(p['source_type']=='teaching_material' for p in evidence)
            cid=evidence[0]['citation_id']
            with (folder/'mock-calls.jsonl').open('a') as f:f.write(json.dumps(dict(mock=True,citation_id=cid))+'\n')
            return ModelReply(dict(content=json.dumps(dict(answer='根据所选课件，复习模型评估与性能度量。 ['+cid+']',citation_ids=[cid],supplement_md=''),ensure_ascii=False)),20,30)
    app=create_app(APISettings(data_dir=folder/'data',db_path=folder/'http.sqlite3',agent=AgentSettings(enabled=True,api_key='synthetic-only')),teaching_client_factory=Model)
    server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=port,log_level='warning',timeout_graceful_shutdown=3))
    def wait():
        while not (folder/'stop').exists():time.sleep(.1)
        server.should_exit=True
    threading.Thread(target=wait,daemon=True).start();server.run()

def verify():
    root=Path.cwd();p=json.loads((root/'data/local/pilot-review.json').read_text(encoding='utf-8'))
    directory=root/'data/local'/('pilot-http-'+uuid4().hex[:8]);directory.mkdir()
    shutil.copytree(root/'data',directory/'data',ignore=shutil.ignore_patterns('local','evaluation'))
    with sqlite3.connect('file:data/local/eduagent.sqlite3?mode=ro',uri=True) as src,sqlite3.connect(directory/'http.sqlite3') as dst:src.backup(dst)
    shutil.copytree(root/'data/local/eduagent.documents',directory/'http.documents',ignore=shutil.ignore_patterns('*.lock','staging'))
    with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
    checks=[];starts=0;process=None;log=None;client=httpx.Client(base_url=f'http://127.0.0.1:{port}',trust_env=False,timeout=40)
    prefix='/api/v1/students/'+p['student_id'];links=prefix+'/teaching-material-links';graph=prefix+'/knowledge-architectures/'+p['architecture_id']
    def http(path,body=None,method=None,status=200,raw=False):
        r=client.request(method or ('POST' if body is not None else 'GET'),path,json=body) if body is not None else client.get(path)
        assert r.status_code==status,(path,r.status_code,r.text[:200]);return r.content if raw else r.json()
    def start():
        nonlocal starts,process,log
        starts+=1;(directory/'stop').unlink(missing_ok=True);log=(directory/f'server-{starts}.log').open('w')
        process=subprocess.Popen([sys.executable,__file__,'--serve',str(directory),'--port',str(port)],stdout=log,stderr=log,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        for _ in range(150):
            assert process.poll() is None,'server exited'
            try:http('/health');return
            except httpx.TransportError:time.sleep(.1)
        raise AssertionError('startup timeout')
    def stop():
        if process and process.poll() is None:(directory/'stop').touch();process.wait(timeout=30)
        if log:log.close()
    def check(name):checks.append(dict(name=name,passed=True))
    def calls():return len((directory/'mock-calls.jsonl').read_text().splitlines()) if (directory/'mock-calls.jsonl').exists() else 0
    def facts():
        from eduagent.storage.migrations import fact_snapshot
        with sqlite3.connect(directory/'http.sqlite3') as db:return fact_snapshot(db)
    try:
        start();assert not any(s['source_type']=='teaching_material' for s in http(prefix+'/knowledge/sources')['items']);rows=http(links)['items'];assert len(rows)==5 and all(r['status']=='candidate' for r in rows)
        check('real_unreviewed_pages_excluded_from_sources')
        before=facts();a=http(graph);http(graph+'/publish',cmd(expected_revision=a['revision'],confirmed=True))
        for r in rows:http(links+'/'+r['id']+'/review',cmd(expected_revision=r['revision'],confirmed=True,architecture_version=1,reviewer='ISOLATED SCRIPTED CHECK; NOT OWNER ACCEPTANCE'),'PUT')
        assert facts()==before;check('scripted_confirmation_maps_five_pages_to_one_existing_concept_without_bkt')
        source=next(s for s in http(prefix+'/knowledge/sources')['items'] if s['source_type']=='teaching_material');ref={k:source[k] for k in ('source_type','source_id','source_version')}
        result=http(prefix+'/knowledge/search',dict(query='查准率 查全率 混淆矩阵',sources=[ref],top_k=5))['items'];assert result and {r['page_number'] for r in result}<={32,35,20,11,12}
        stored={r['id']:r for r in http(links)['items']}
        assert all(r['raw_md']==stored[r['chunk_id']]['excerpt_md'] and r['concept_id']==p['concept_id'] for r in result)
        image=http(prefix+'/documents/'+p['course']['id']+'/preview?version_id='+p['course']['version_id']+'&page=32',raw=True);assert image.startswith(b'\x89PNG')
        check('selected_teacher_tfidf_citation_matches_saved_excerpt_and_actual_pdf_page')
        other='/api/v1/students/learner-8ab5e4c4';http(other+'/knowledge/search',dict(query='查准率',sources=[ref]),status=404);http(prefix+'/knowledge/search',dict(query='查准率',sources=[]),status=422)
        check('other_student_and_empty_source_requests_do_not_expand_scope')
        payload=dict(title='模型评估真实课件 · 隔离验收演示',sources=[ref],architecture_id=p['architecture_id'],architecture_version=1,reviewer='',reviewed_question_ids=[])
        draft=http(prefix+'/course-builder/drafts',cmd(payload=payload))['draft_id'];checked=http(prefix+'/course-builder/drafts/'+draft)
        release=http(prefix+'/course-builder/drafts/'+draft+'/publish',cmd(expected_revision=checked['revision'],snapshot_hash=checked['snapshot_hash'],kind='demo',confirmed=True))
        session=http(prefix+'/teaching-sessions',cmd(release_id=release['release_id'],goals=['model_evaluation']))['session_id'];lesson=prefix+'/teaching-sessions/'+session
        assert http(lesson)['pending_diagnosis']==['model_evaluation'];assert facts()==before;check('release_scope_binds_real_teacher_version_goal_and_read_only_state')
        bank=json.loads((root/'data/questions.json').read_text(encoding='utf-8'))['questions']
        d=http(lesson+'/next',cmd(expected_learning_revision=0))['decision'];assert d['knowledge_id']=='model_evaluation'
        q=next(q for q in bank if q['id']==d['question']['id']);wrong=next(k for k in q['options'] if k!=q['answer'])
        body=cmd(decision_id=d['decision_id'],answer=wrong);answer=http(lesson+'/answers',body);assert not answer['result']['correct'] and http(lesson+'/answers',body)['replayed'];assert http(lesson)['next_task']['action']=='review'
        check('actual_formal_diagnosis_scores_and_updates_original_bkt_once')
        req=cmd(question='查准率和查全率有什么区别，混淆矩阵怎样理解？',sources=[ref],course_id='machine_learning',mode='local',allow_personal_external=False)
        local=http(lesson+'/explain',req);assert local['citations'] and local['model_calls']==0 and calls()==0
        no=http(lesson+'/explain',dict(req,request_id=str(uuid4()),mode='model',allow_personal_external=True));assert no['reason']=='teacher_consent_required' and calls()==0
        check('local_explanation_and_independent_teacher_consent_zero_transmission')
        req=dict(req,request_id=str(uuid4()),mode='model',allow_teacher_external=True)
        reply=http(lesson+'/explain',req);assert reply['status']=='complete' and calls()==1 and reply['citations'][0]['page_number']
        assert http(lesson+'/explain',req)['answer']==reply['answer'];http(prefix+'/workbench/runs');assert calls()==1
        check('mock_teacher_explanation_uses_real_citations_and_history_without_repeat')
        before_practice=facts();qid=p['question_ids'][0];personal=http(prefix+'/personal-bank/questions/'+qid);personal['payload']['answer']='A'
        personal['payload']['concepts']=[dict(architecture_id=p['architecture_id'],concept_id=p['concept_id'])]
        http(prefix+'/personal-bank/questions/'+qid,cmd(expected_revision=personal['revision'],payload=personal['payload'],status='practice',reviewed=True,confirm_answer=True),'PUT')
        ps=http(prefix+'/personal-bank/practice',cmd(question_id=qid))['session_id'];normal=http(prefix+'/personal-bank/practice/'+ps+'/answer',cmd(selected_answer='A'))
        assert normal['result']['bkt_updated'] is False and facts()==before_practice;check('real_question_scripted_ordinary_review_and_practice_do_not_touch_formal_bkt')
        d=http(lesson+'/next',cmd(expected_learning_revision=1))['decision'];q=next(q for q in bank if q['id']==d['question']['id']);http(lesson+'/answers',cmd(decision_id=d['decision_id'],answer=q['answer']))
        state=http(lesson);assert state['snapshot']['revision']==2 and state['next_task']['action']=='stopped' and state['next_task']['stop_reason']=='insufficient_questions'
        check('existing_formal_retest_updates_evidence_and_reports_bank_exhaustion')
        http('/api/v1/students',dict(student_id='different-state',goals=['model_evaluation']));demo=http('/api/v1/courses/published')['items'][0]
        sk=http('/api/v1/students/different-state/teaching-sessions',cmd(release_id=demo['id'],goals=['model_evaluation']))['session_id']
        assert http('/api/v1/students/different-state/teaching-sessions/'+sk)['next_task']['action']=='diagnose';check('different_objective_evidence_changes_next_action')
        stop();start();assert calls()==1 and http(lesson)['snapshot']['revision']==2 and http(prefix+'/knowledge/search',dict(query='查准率',sources=[ref]))['items'];check('restart_restores_reviewed_index_history_and_state_without_model_replay')
        r=http(links)['items'][0];http(links+'/'+r['id']+'/review',cmd(expected_revision=r['revision'],confirmed=False),'PUT');http(prefix+'/knowledge/search',dict(query='查准率',sources=[ref]),status=409)
        assert not http(prefix+'/course-releases/'+release['release_id'])['usable'];old=http(prefix+'/workbench/runs/'+req['request_id']);assert old['citations'] and old['source_statuses'][0]['current_status']=='modified'
        check('review_change_invalidates_current_source_release_but_preserves_historical_citation')
        report=dict(passed=True,verified_at=datetime.now(timezone.utc).isoformat(),groups=len(checks),checks=checks,directory=str(directory),schema=12,tables=45,server_starts=starts,simulated_model_calls=calls(),real_chat_calls=0,production_learning_writes=0,approval_semantics='Scripted review in isolated copy only; main data still candidate and not owner reviewed.',browser_manual='not_performed')
        output=root/'data/evaluation/pilot-http-v1.json';output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(dict(passed=True,groups=len(checks),mock_calls=calls(),real_chat_calls=0,report=str(output))))
    finally:stop();client.close()

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--serve',type=Path);parser.add_argument('--port',type=int);args=parser.parse_args()
    if args.serve:serve(args.serve,args.port)
    else:verify()
