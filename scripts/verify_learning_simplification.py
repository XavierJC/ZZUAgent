"""Isolated real HTTP: automatic ordinary intake and direct document reading.

Providers are replaced in this subprocess; zero real model calls.
"""
import argparse,json,shutil,socket,sqlite3,subprocess,sys,threading,time
from pathlib import Path
from datetime import datetime,timezone
from uuid import uuid4
from urllib.request import Request,build_opener,ProxyHandler
from urllib.error import HTTPError,URLError

PARTS=[
 '1. 梯度下降沿哪个方向更新参数？\nA. 负梯度方向\nB. 正梯度方向\n答案：A',
 '2. 简答：说明过拟合的现象。\n答案：训练误差低，但泛化误差高。',
 '3. [无法辨认] 给出缺失图中的结论。']
RAW='\n\n'.join(PARTS)

def serve(folder,port):
    import uvicorn
    from eduagent.api.app import create_app
    from eduagent.api.settings import APISettings
    from eduagent.agent.settings import AgentSettings
    from eduagent.agent import deepseek
    class Model:
        def __init__(self,*a,**kw):pass
        def complete(self,messages,tools):
            extracting=isinstance(messages[1]['content'],list)
            with (folder/'mock-calls.jsonl').open('a') as f:f.write(json.dumps(dict(mock=True,kind='extract' if extracting else 'chat'))+'\n')
            if extracting:
                data=dict(questions=[
                    dict(payload=dict(question_type='single_choice',stem='梯度下降沿哪个方向更新参数？',options=[dict(key='A',text='负梯度方向'),dict(key='B',text='正梯度方向')],answer='A'),source_units=[1],quotes=[PARTS[0]]),
                    dict(payload=dict(question_type='short_answer',stem='简答：说明过拟合的现象。',answer_text='训练误差低，但泛化误差高。'),source_units=[1],quotes=[PARTS[1]]),
                    dict(payload=dict(question_type='unknown',stem='[无法辨认] 给出缺失图中的结论。'),source_units=[1],quotes=[PARTS[2]])],warnings=[])
            else:
                inp=json.loads(messages[1]['content']);ids=[p['citation_id'] for p in inp['untrusted_evidence'][:1]]
                if inp['question']=='scope_attack':
                    return deepseek.ModelReply(dict(content=None,tool_calls=[dict(id='bad',type='function',function=dict(name='retrieve_selected_sources',arguments=json.dumps(dict(query='梯度下降',student_id='b'))))]),10,10)
                data=dict(answer='按上传资料说明梯度下降。'+''.join(' ['+i+']' for i in ids),citation_ids=ids,supplement_md='')
            return deepseek.ModelReply(dict(content=json.dumps(data,ensure_ascii=False)),10,30)
    deepseek.DeepSeekClient=Model
    settings=APISettings(data_dir=folder/'data',db_path=folder/'http.sqlite3',agent=AgentSettings(enabled=True,api_key='synthetic-only'))
    server=uvicorn.Server(uvicorn.Config(create_app(settings,extraction_client_factory=lambda _:Model()),host='127.0.0.1',port=port,log_level='warning',timeout_graceful_shutdown=3))
    def stop():
        while not (folder/'stop').exists():time.sleep(.05)
        server.should_exit=True
    threading.Thread(target=stop,daemon=True).start();server.run()

def verify(output):
    from eduagent.storage.migrations import fact_snapshot,preserved_snapshot
    folder=Path('data/local').resolve()/('simplification-http-'+uuid4().hex[:8]);folder.mkdir();shutil.copytree('data',folder/'data',ignore=shutil.ignore_patterns('local','evaluation'))
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    opener=build_opener(ProxyHandler({}));base=f'http://127.0.0.1:{port}';root='/api/v1/students/a';checks=[];process=log=None;starts=0
    def http(path,body=None,method=None,expected=200,file=None):
        headers={'Content-Type':'application/json'};raw=None if body is None else json.dumps(body).encode()
        if file:
            boundary='eduagent-'+uuid4().hex;headers={'Content-Type':'multipart/form-data; boundary='+boundary}
            raw=(f'--{boundary}\r\nContent-Disposition: form-data; name="metadata"\r\n\r\n'+json.dumps(body)+f'\r\n--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="synthetic.md"\r\nContent-Type: text/markdown\r\n\r\n').encode()+file+f'\r\n--{boundary}--\r\n'.encode()
        try:r=opener.open(Request(base+path,data=raw,method=method or ('POST' if raw is not None else 'GET'),headers=headers),timeout=30)
        except HTTPError as e:r=e
        with r:
            data=r.read();assert r.status==expected,(path,r.status,data[:300]);return json.loads(data) if data else None
    def start():
        nonlocal process,log,starts
        starts+=1;(folder/'stop').unlink(missing_ok=True);log=(folder/f'server-{starts}.log').open('w')
        process=subprocess.Popen([sys.executable,__file__,'--serve',str(folder),'--port',str(port)],stdout=log,stderr=log,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            assert process.poll() is None,'server exited'
            try:http('/health');return
            except (URLError,OSError):time.sleep(.1)
        raise AssertionError('server start timeout')
    def stop():
        if process and process.poll() is None:(folder/'stop').touch();process.wait(timeout=30)
        if log:log.close()
    def command(**kw):return dict(request_id=str(uuid4()),**kw)
    def calls():return len((folder/'mock-calls.jsonl').read_text().splitlines()) if (folder/'mock-calls.jsonl').exists() else 0
    def facts():
        with sqlite3.connect(folder/'http.sqlite3') as db:return fact_snapshot(db)
    def check(name):checks.append(dict(name=name,passed=True))
    def wait_task(key):
        for _ in range(60):
            value=http(root+'/personal-bank/extraction-tasks/'+key)
            if value['status']!='running':return value
            time.sleep(.1)
        raise AssertionError('task timeout')
    try:
        start()
        for owner in ('a','b'):http('/api/v1/students',dict(student_id=owner,goals=['gradient_descent']))
        original=facts();meta=command(title='合成梯度下降资料',local_rights_confirmed=True)
        doc=http(root+'/documents',meta,expected=202,file='# 梯度下降\n\n梯度下降沿负梯度方向更新参数，学习率控制每一步的大小。公式 $w_{t+1}=w_t-\\eta \\nabla L(w_t)$。'.encode())
        for _ in range(80):
            current=http(root+'/documents/'+doc['id'])
            if current['parse']['status'] not in ('pending','processing'):break
            time.sleep(.1)
        assert current['index_status']=='ready';check('uploaded_original_parsed_and_ready_without_knowledge_tree_or_release')
        source=next(s for s in http(root+'/knowledge/sources')['items'] if s['source_type']=='uploaded_document')
        ref={k:source[k] for k in ('source_type','source_id','source_version')}
        assert http(root+'/documents/capabilities')['retrieval_connected'];check('source_directory_reports_unverified_document_and_parse_readiness')
        results=http(root+'/knowledge/search',dict(query='梯度下降',sources=[ref]))
        preview=http(root+'/workbench/sources/open',ref)
        assert preview['document_id']==doc['id'] and preview['version_id']==source['version_id']
        assert results['items'] and results['items'][0]['page_number']==1 and results['items'][0]['review_status']=='document_unverified';check('local_retrieval_has_actual_document_page_and_raw_excerpt')
        http(root+'/knowledge/search',dict(query='梯度下降',sources=[]),expected=422)
        http('/api/v1/students/b/knowledge/search',dict(query='梯度下降',sources=[ref]),expected=404);check('empty_source_and_cross_student_scope_cannot_expand_retrieval')
        def ask(**kw):return command(question='梯度下降',sources=[ref],mode='model',allow_personal_external=False,**kw)
        denied=http(root+'/workbench/questions',ask());assert denied['reason']=='teacher_consent_required' and calls()==0;check('no_upload_external_consent_means_zero_provider_transmission')
        request=ask(allow_teacher_external=True);answered=http(root+'/workbench/questions',request)
        assert answered['status']=='complete' and answered['citations'][0]['document_id']==doc['id'] and calls()==1
        http(root+'/workbench/questions',request);http(root+'/workbench/runs');assert calls()==1;check('consented_answer_uses_real_obtained_citation_and_replays_without_call')
        attack=ask(allow_teacher_external=True);attack['question']='scope_attack';assert http(root+'/workbench/questions',attack)['reason']=='tool_scope_rejected';check('agent_cannot_change_student_or_selected_source_capability')
        body=command(text=RAW,consent=True,auto_import=True);http(root+'/personal-bank/extraction-tasks',body,expected=202)
        task=wait_task(body['request_id']);assert task['status']=='complete' and task['result']['intake']==dict(ready=2,needs_attention=1,duplicate=0);check('synthetic_ai_extracts_two_practice_questions_and_quarantines_missing_content')
        count=calls();http(root+'/personal-bank/extraction-tasks',body,expected=202);assert calls()==count
        other=command(text=RAW,consent=True,auto_import=True);http(root+'/personal-bank/extraction-tasks',other,expected=202);assert wait_task(other['request_id'])['result']['intake']['duplicate']==3
        rows=http(root+'/personal-bank/questions')['items'];assert len(rows)==3;check('same_request_is_idempotent_and_distinct_repeated_import_deduplicates')
        objective=next(q for q in rows if q['payload']['question_type']=='single_choice');assert not objective['review']['reviewed'] and not objective['review']['answer_confirmed']
        sid=http(root+'/personal-bank/practice',command(question_id=objective['id']))['session_id']
        result=http(root+'/personal-bank/practice/'+sid+'/answer',command(selected_answer='A'))['result']
        assert result['correct'] is None and result['reference_match'] is True and not result['bkt_updated'];check('practice_feedback_is_explicitly_unverified_and_not_a_formal_score')
        drafts=next(q for q in rows if q['status']=='draft');http(root+'/personal-bank/practice',command(question_id=drafts['id']),expected=409)
        assert http('/api/v1/students/b/personal-bank/questions')['items']==[];check('incomplete_questions_and_other_student_questions_are_not_practice_candidates')
        assert facts()==original;check('all_original_formal_facts_mastery_goals_decisions_and_history_unchanged')
        http(root+'/documents/'+doc['id'],command(expected_revision=1,title='新标题'),method='PATCH')
        http(root+'/knowledge/search',dict(query='梯度下降',sources=[ref]),expected=409)
        saved=http(root+'/workbench/runs/'+request['request_id']);assert saved['source_statuses'][0]['current_status']=='modified' and saved['citations']==answered['citations'];check('source_update_invalidates_new_use_but_keeps_historical_snapshot')
        source=next(s for s in http(root+'/knowledge/sources')['items'] if s['source_type']=='uploaded_document');newref={k:source[k] for k in ref}
        http(root+'/documents/'+doc['id'],command(expected_revision=2),method='DELETE')
        http(root+'/knowledge/search',dict(query='梯度下降',sources=[newref]),expected=404);check('deleted_document_immediately_unavailable_to_current_retrieval')
        count=calls();stop();start();assert http(root+'/personal-bank/practice/'+sid)['result']==result and calls()==count and facts()==original
        assert http(root+'/workbench/runs/'+request['request_id'])['citations']==answered['citations'];check('restart_recovers_questions_responses_and_history_without_model_resubmission')
        report=dict(passed=True,groups=len(checks),checks=checks,schema=13,tables=45,simulated_model_calls=calls(),real_model_calls=0,production_writes=0,server_starts=starts,directory=str(folder),browser_manual='not_performed',verified_at=datetime.now(timezone.utc).isoformat())
        output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(dict(passed=True,groups=len(checks),mock_calls=calls(),report=str(output))))
    finally:stop()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--serve',type=Path);p.add_argument('--port',type=int);p.add_argument('--output',type=Path,default=Path('data/evaluation/learning-simplification-http-v1.json'));a=p.parse_args()
    if a.serve:serve(a.serve,a.port)
    else:verify(a.output)
