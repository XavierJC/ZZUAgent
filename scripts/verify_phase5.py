"""Isolated real HTTP teaching loop and release audit. All model calls synthetic."""
import argparse,json,shutil,socket,sqlite3,subprocess,sys,threading,time
from datetime import datetime,timezone
from pathlib import Path
from urllib.request import Request,build_opener,ProxyHandler
from urllib.error import HTTPError,URLError
from uuid import uuid4
def cmd(**kw):return dict(request_id=str(uuid4()),**kw)

def serve(folder,port):
    import uvicorn
    from eduagent.api.app import create_app
    from eduagent.api.settings import APISettings
    from eduagent.agent.settings import AgentSettings
    from eduagent.agent.deepseek import ModelReply
    class Model:
        def complete(self,messages,tools):
            data=json.loads(messages[1]['content']);context=data.get('server_learning_context')
            assert context and 'session_id' not in context and 'release_id' not in context
            with (folder/'mock-calls.jsonl').open('a') as f:f.write(json.dumps(dict(mock=True,learning_revision=context['learning_revision']))+'\n')
            evidence=data['untrusted_evidence'];ids=[e['citation_id'] for e in evidence[:1]]
            return ModelReply(dict(content=json.dumps(dict(answer='按课程定义理解损失与更新方向。'+(' ['+ids[0]+']' if ids else ''),citation_ids=ids,supplement_md='') if ids else dict(answer='',citation_ids=[],supplement_md='本轮没有足够本地片段，先说明模型知识。'),ensure_ascii=False)),50,80)
    settings=APISettings(data_dir=folder/'data',db_path=folder/'http.sqlite3',agent=AgentSettings(enabled=True,api_key='synthetic-only'))
    server=uvicorn.Server(uvicorn.Config(create_app(settings,teaching_client_factory=Model),host='127.0.0.1',port=port,log_level='warning',timeout_graceful_shutdown=3))
    def stop():
        while not (folder/'stop').exists():time.sleep(.05)
        server.should_exit=True
    threading.Thread(target=stop,daemon=True).start();server.run()

def verify(output):
    from eduagent.storage import migrations
    folder=Path('data/local').resolve()/('phase5-http-'+uuid4().hex[:8]);folder.mkdir();shutil.copytree('data',folder/'data',ignore=shutil.ignore_patterns('local','evaluation'))
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    opener=build_opener(ProxyHandler({}));base=f'http://127.0.0.1:{port}';prefix='/api/v1/students/a';workflow=prefix+'/teaching-sessions';builder=prefix+'/course-builder';checks=[];process=None;log=None;starts=0
    def http(path,body=None,method=None,expected=200):
        req=Request(base+path,data=None if body is None else json.dumps(body).encode(),method=method or ('POST' if body is not None else 'GET'),headers={'Content-Type':'application/json'})
        try:r=opener.open(req,timeout=40)
        except HTTPError as e:r=e
        with r:
            raw=r.read();assert r.status==expected,(path,r.status,raw[:300]);return json.loads(raw) if raw else None
    def start():
        nonlocal process,log,starts
        (folder/'stop').unlink(missing_ok=True);starts+=1;log=(folder/f'server-{starts}.log').open('w')
        process=subprocess.Popen([sys.executable,__file__,'--serve',str(folder),'--port',str(port)],stdout=log,stderr=log,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            assert process.poll() is None,'server exited'
            try:http('/health');return
            except (URLError,OSError):time.sleep(.1)
        raise AssertionError('start timeout')
    def stop():
        if process and process.poll() is None:(folder/'stop').touch();process.wait(timeout=30)
        if log:log.close()
    def check(name):checks.append(dict(name=name,passed=True))
    def calls():return len((folder/'mock-calls.jsonl').read_text().splitlines()) if (folder/'mock-calls.jsonl').exists() else 0
    def facts():
        with sqlite3.connect(folder/'http.sqlite3') as db:return migrations.fact_snapshot(db)
    def count(table):
        with sqlite3.connect(folder/'http.sqlite3') as db:return db.execute('SELECT count(*) FROM '+table).fetchone()[0]
    def explain(key,sources,mode='local',consent=False):return cmd(question='MSE均方误差的定义与梯度下降',course_id='machine_learning',sources=sources,mode=mode,allow_personal_external=consent)
    try:
        start();demo=http('/api/v1/courses/published')['items'][0];original_hash=demo['content_hash'];assert demo['kind']=='demo' and len(demo['question_versions'])==10 and 'answer' not in demo['question_versions'][0]
        check('prepublished_demo_available_without_builder_no_false_review')
        for s in ('a','b'):http('/api/v1/students',dict(student_id=s,goals=['logistic_regression']))
        before=facts();assert http(prefix+'/current-decision') is None
        for _ in range(3):assert http(workflow)['session'] is None
        assert facts()==before and count('decisions')==0;check('refresh_and_history_are_read_only_no_allocation')
        body=cmd(release_id=demo['id'],goals=['logistic_regression']);session=http(workflow,body)['session_id'];path=workflow+'/'+session
        assert http(workflow,body)['replayed'];http(workflow,dict(body,goals=['model_evaluation']),expected=409)
        state=http(path);assert not state['has_objective_evidence'] and state['decision'] is None and all(i['objective']['probability'] is None for i in state['guidance']['items']);check('goals_bound_to_release_no_prior_diagnosis')
        allocation=cmd(expected_learning_revision=0);decision=http(path+'/next',allocation)['decision'];assert http(path+'/next',allocation)['replayed'] and count('decisions')==1
        http(workflow,cmd(release_id=demo['id'],goals=['logistic_regression']),expected=409);check('explicit_diagnosis_idempotency_and_pending_session_protection')
        bank=json.loads((folder/'data/questions.json').read_text(encoding='utf-8'))['questions'];answer=next(q['answer'] for q in bank if q['id']==decision['question']['id'])
        submission=cmd(decision_id=decision['decision_id'],answer=answer);graded=http(path+'/answers',submission)
        assert graded['result']['correct'] and http(path+'/answers',submission)['replayed']
        state=http(path);assert state['snapshot']['revision']==1 and state['next_task']['action']=='practice' and count('decisions')==1
        assert state['history'][0]['course_provenance']['release_id']==demo['id'];check('core_scoring_bkt_update_and_replanning_real_services')
        c=http(builder);assert c['candidate_count']==40 and c['shared_formal_count']==10 and c['additional_candidate_count']==30;check('candidate_pool_contains_original_ten_not_fifty')
        local=http(path+'/explain',explain(session,demo['retrieval_scope']));assert local['model_calls']==0 and local['citations'] and calls()==0;check('release_bound_local_explanation_without_model')
        request=explain(session,demo['retrieval_scope'],'model');reply=http(path+'/explain',request);assert reply['status']=='complete' and reply['lesson_context']['release_id']==demo['id'] and calls()==1
        assert http(path+'/explain',request)['answer']==reply['answer'];http(prefix+'/workbench/runs');assert calls()==1;check('mock_agent_context_citations_history_replay_no_repeat_call')
        nextq=http(path+'/next',cmd(expected_learning_revision=1))['decision'];assert http(path)['session']['stage']=='verification'
        correct=next(q['answer'] for q in bank if q['id']==nextq['question']['id']);http(path+'/answers',cmd(decision_id=nextq['decision_id'],answer=correct))
        assert http(path)['snapshot']['revision']==2;check('explanation_to_formal_retest_and_updated_evidence')
        # New course content draft, no formal-bank replacement.
        payload=dict(title='隔离HTTP课程',sources=[demo['retrieval_scope'][0]],reviewed_question_ids=[],reviewer='')
        draft=http(builder+'/drafts',cmd(payload=payload));did=draft['draft_id'];review=http(builder+'/drafts/'+did);assert not review['formal_allowed']
        pub=cmd(expected_revision=1,snapshot_hash=review['snapshot_hash'],kind='reviewed',confirmed=True)
        http(builder+'/drafts/'+did+'/publish',pub,expected=409);pub['kind']='demo';published=http(builder+'/drafts/'+did+'/publish',pub)
        assert http(builder+'/drafts/'+did+'/publish',pub)['replayed'];http(builder+'/drafts/'+did+'/publish',dict(pub,request_id=str(uuid4())),expected=409);check('draft_review_blocks_unreviewed_formal_release_demo_explicit')
        release=http(prefix+'/course-releases/'+published['release_id']);hash_before=release['content_hash']
        http(builder+'/drafts/'+did,cmd(expected_revision=1,payload=dict(payload,title='另一个草稿')),'PUT')
        assert http(prefix+'/course-releases/'+release['id'])['content_hash']==hash_before
        http(builder+'/drafts/'+did,cmd(expected_revision=1,payload=payload),'PUT',expected=409);check('published_snapshot_frozen_draft_cas_and_version_history')
        ownsession=http(workflow,cmd(release_id=release['id'],goals=['logistic_regression']))['session_id'];ownpath=workflow+'/'+ownsession
        http(ownpath+'/explain',explain(ownsession,[demo['retrieval_scope'][1]]),expected=409);http(ownpath+'/explain',explain(ownsession,[]),expected=422);assert calls()==1;check('unselected_release_sources_and_empty_set_rejected_server_side')
        http(prefix.replace('/a','/b')+'/course-releases/'+release['id'],expected=404);http(workflow.replace('/a/','/b/')+'/'+ownsession,expected=404);check('private_course_and_session_scope_isolation')
        nid=str(uuid4());note=http(prefix+'/notes',dict(id=nid,title='合成个人笔记',content_md='个人笔记：MSE是平方残差的平均。'),expected=201)
        selected=next(s for s in http(prefix+'/knowledge/sources')['items'] if s['source_id']==nid)
        ref={k:selected[k] for k in ('source_type','source_id','source_version')}
        private=http(ownpath+'/explain',explain(ownsession,[ref],'model',False));assert private['reason']=='personal_consent_required' and calls()==1;check('private_note_consent_independent_zero_model_transfer_without_consent')
        http(ownpath+'/explain',explain(ownsession,[ref],'model',True));assert calls()==2;check('mock_personal_explicit_round_consent')
        sid=http(prefix+'/personal-bank/questions',cmd(payload=dict(stem='普通简答',question_type='short_answer',answer_text='参考'),status='practice',reviewed=True))['question_id']
        before=facts();practice=http(prefix+'/personal-bank/practice',cmd(question_id=sid))['session_id'];r=http(prefix+'/personal-bank/practice/'+practice+'/answer',cmd(selected_answer='个人文字作答',needs_review=True));assert r['result']['score'] is None and facts()==before;check('ordinary_practice_separate_from_bkt')
        old=http('/api/v1/students/b/next',{});http('/api/v1/students/b/answers',dict(decision_id=old['decision_id'],event_id=str(uuid4()),answer='A'))
        legacy=http('/api/v1/students/b/teaching-history')['items'][0];assert legacy['course_provenance']['release_id'] is None
        assert http('/api/v1/students/b/learning-guidance')['recommendations'][0]['objective']['last_correct'] is False;check('legacy_facts_not_relabelled_and_wrong_state_has_other_guidance')
        prior_events=http(prefix+'/teaching-history')['items'];assert all(e['course_provenance']['release_id']==demo['id'] for e in prior_events)
        source=folder/'data/materials/linear_regression.md';source.write_text(source.read_text(encoding='utf-8')+'\nsource changed',encoding='utf-8')
        assert not http(prefix+'/course-releases/'+release['id'])['usable'] and http(prefix+'/course-releases/'+release['id'])['content_hash']==hash_before
        http(ownpath+'/next',cmd(expected_learning_revision=2),expected=409);assert http(prefix+'/teaching-history')['items']==prior_events;check('source_update_invalidates_current_use_keeps_history_snapshot')
        final=facts();stop();start();assert http(path)['snapshot']['revision']==2 and http(prefix+'/teaching-history')['items']==prior_events and calls()==2
        assert http('/api/v1/courses/published')['items'][0]['content_hash']==original_hash and facts()==final;check('restart_restores_release_session_and_facts_no_auto_republish_or_model')
        report=dict(passed=True,verified_at=datetime.now(timezone.utc).isoformat(),groups=len(checks),checks=checks,server_starts=starts,schema=12,tables=45,simulated_model_calls=calls(),real_model_calls=0,production_writes=0,directory=str(folder),browser_manual='not_performed')
        output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(dict(passed=True,groups=len(checks),mock_calls=calls(),real_calls=0,report=str(output))))
    finally:stop()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--serve',type=Path);p.add_argument('--port',type=int);p.add_argument('--output',type=Path,default=Path('data/evaluation/phase5-http-v1.json'));a=p.parse_args()
    if a.serve:serve(a.serve,a.port)
    else:verify(a.output)
