"""Isolated real HTTP 4C acceptance; native parsers, synthetic vision, no paid calls."""
import argparse,json,socket,sqlite3,subprocess,sys,threading,time
from datetime import datetime,timezone
from io import BytesIO
from pathlib import Path
from urllib.request import Request,build_opener,ProxyHandler
from urllib.error import HTTPError,URLError
from uuid import uuid4

TEXT='1. 求 $x^2$ 的导数？\nA. $2x$\nB. $x$\n答案：A\n解析：幂函数求导。\n2. 判断：过拟合总能改善泛化。\n答案：错误\n'
def cmd(**kw):return dict(request_id=str(uuid4()),**kw)


def serve(folder,port):
    import uvicorn
    from eduagent.api.app import create_app
    from eduagent.api.settings import APISettings
    from eduagent.agent.settings import AgentSettings
    from eduagent.agent.deepseek import ModelReply
    class SyntheticVision:
        def complete(self,messages,tools):
            assert not tools and messages[1]['content'][1]['image_url']['url'].startswith('data:image/png;base64,')
            with (folder/'mock-calls.jsonl').open('a') as f:f.write('{"synthetic":true}\n')
            return ModelReply(dict(content=json.dumps(dict(transcription_md=(folder/'vision-text.txt').read_text(encoding='utf-8'),interpretation_md='',warnings=[]))),20,35)
    settings=APISettings(db_path=folder/'http.sqlite3',agent=AgentSettings(api_key='synthetic-only'),document_vision_enabled=True)
    server=uvicorn.Server(uvicorn.Config(create_app(settings,document_vision_factory=SyntheticVision),host='127.0.0.1',port=port,log_level='warning',timeout_graceful_shutdown=3))
    def stop():
        while not (folder/'stop').exists():time.sleep(.05)
        server.should_exit=True
    threading.Thread(target=stop,daemon=True).start();server.run()


def verify(output):
    from eduagent.storage import migrations
    sys.path.insert(0,str(Path('backend/tests').resolve()))
    from document_fixtures import pdf_bytes
    from test_architectures import example
    from PIL import Image
    folder=Path('data/local').resolve()/('phase4c-http-'+uuid4().hex[:8]);folder.mkdir()
    (folder/'vision-text.txt').write_text(TEXT,encoding='utf-8')
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    base=f'http://127.0.0.1:{port}';opener=build_opener(ProxyHandler({}));process=None;log=None;starts=0;checks=[]
    prefix='/api/v1/students/a';bank=prefix+'/personal-bank';docs=prefix+'/documents'
    def http(path,body=None,method=None,expected=200,headers=None,raw=False):
        request=Request(base+path,data=body if isinstance(body,bytes) else None if body is None else json.dumps(body).encode(),method=method or ('POST' if body is not None else 'GET'),headers=headers or {'Content-Type':'application/json'})
        try:response=opener.open(request,timeout=65)
        except HTTPError as exc:response=exc
        with response:
            value=response.read();assert response.status==expected,(path,response.status,value[:300])
            return value if raw else json.loads(value)
    def start():
        nonlocal process,log,starts
        (folder/'stop').unlink(missing_ok=True);starts+=1;log=(folder/f'server-{starts}.log').open('w',encoding='utf-8')
        process=subprocess.Popen([sys.executable,__file__,'--serve',str(folder),'--port',str(port)],stdout=log,stderr=log,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            assert process.poll() is None,'isolated server exited'
            try:http('/health');return
            except (URLError,OSError):time.sleep(.1)
        raise AssertionError('server start timeout')
    def stop():
        if process and process.poll() is None:(folder/'stop').touch();process.wait(timeout=30)
        if log:log.close()
    def check(name):checks.append(dict(name=name,passed=True))
    def upload(raw,name,document=None,meta=None):
        boundary='bank'+uuid4().hex
        metadata=meta or cmd(title='自建原题资料',local_rights_confirmed=True)
        body=(f'--{boundary}\r\nContent-Disposition: form-data; name="metadata"\r\n\r\n'.encode()+json.dumps(metadata).encode()+f'\r\n--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{name}"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode()+raw+f'\r\n--{boundary}--\r\n'.encode())
        return http(docs+('/'+document+'/versions' if document else ''),body,expected=202,headers={'Content-Type':'multipart/form-data; boundary='+boundary})
    def wait(document,run=None):
        deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            value=http(docs+'/'+document+('/parse-runs/'+run if run else ''));job=value if run else value['parse']
            if job['status'] not in ('pending','processing'):return value
            time.sleep(.08)
        raise AssertionError('parse timeout')
    def resource(document):return next(r for r in http(prefix+'/course-resources')['items'] if r['original_source_id']==document)
    def extract_resource(item,**kw):return http(bank+'/extractions',cmd(resource_id=item['resource_id'],source_version=item['source_version'],**kw))
    def getq(key):return http(bank+'/questions/'+key)
    def publish(q,**kw):return http(bank+'/questions/'+q['id'],cmd(expected_revision=q['revision'],payload=q['payload'],status='practice',reviewed=True,confirm_answer=q['payload']['answer'] is not None,**kw),'PUT')
    def formal():
        with sqlite3.connect(folder/'http.sqlite3') as db:return {k:v for k,v in migrations.preserved_snapshot(db)[0].items() if k in migrations.FACT_TABLES+migrations.NOTE_TABLES+('note_chunks',)+migrations.WORKBENCH_TABLES+migrations.STUDY_TABLES}
    try:
        start()
        for student in ('a','b'):http('/api/v1/students',dict(student_id=student))
        baseline=formal()
        assert len(http(prefix+'/course-resources')['items'])==5;check('readonly_catalogue_reuses_course_sources_without_model')
        body=cmd(text=TEXT);batch=http(bank+'/extractions',body)
        assert http(bank+'/extractions',body)['question_ids']==batch['question_ids']
        http(bank+'/extractions',dict(body,text=TEXT+'changed'),expected=409);check('paste_extract_idempotency_and_request_mismatch')
        first=getq(batch['question_ids'][0]);assert first['payload']['answer']=='A' and first['answer_provenance']=='source_provided'
        publish(first);q=getq(first['id']);assert q['answer_provenance']=='human_confirmed';check('original_answer_preserved_and_manual_promotion_required')
        http(bank+'/questions/'+q['id'],cmd(expected_revision=1,payload=q['payload']),'PUT',expected=409)
        http(bank.replace('/a/','/b/')+'/questions/'+q['id'],expected=404);assert http(bank.replace('/a/','/b/')+'/questions')['items']==[];check('optimistic_concurrency_and_student_isolation')
        sid=http(bank+'/practice',cmd(question_id=q['id']))['session_id'];view=http(bank+'/practice/'+sid)
        assert 'answer' not in view['question']
        submit=cmd(selected_answer='B');r=http(bank+'/practice/'+sid+'/answer',submit)
        assert r['result']['correct'] is False and r['result']['bkt_updated'] is False
        assert http(bank+'/practice/'+sid+'/answer',submit)['replayed'];check('ordinary_single_choice_score_idempotency_and_wrong_history')
        assert http(bank+'/practice?wrong_only=true')['items'][0]['id']==sid
        http(bank.replace('/a/','/b/')+'/practice/'+sid,expected=404);check('private_practice_history_scope')
        other=getq(batch['question_ids'][1]);publish(other);tf=http(bank+'/practice',cmd(question_id=other['id']))['session_id']
        assert http(bank+'/practice/'+tf+'/answer',cmd(selected_answer='false'))['result']['correct'] is True;check('true_false_practice_real_http')
        p=dict(q['payload'],answer=None);unknown=http(bank+'/questions',cmd(payload=p,status='practice',reviewed=True))['question_id']
        usid=http(bank+'/practice',cmd(question_id=unknown))['session_id']
        assert http(bank+'/practice/'+usid+'/answer',cmd(selected_answer='A'))['result']['score'] is None;check('missing_answer_never_fabricates_score')
        # Editing after assignment must not change the grading snapshot.
        assigned=http(bank+'/practice',cmd(question_id=q['id']))['session_id']
        http(bank+'/questions/'+q['id'],cmd(expected_revision=2,payload=dict(q['payload'],stem='新题干',answer='B')),'PUT')
        assert http(bank+'/practice/'+assigned+'/answer',cmd(selected_answer='A'))['result']['correct'] is True;check('practice_immutable_question_and_grading_basis')
        pdf=upload(pdf_bytes(('1. 跨页求 $x^2$ 导数？\nA. $2x$\n','B. $x$\n答案：A\n2. 判断：泛化误差相同。\n答案：错误')), 'q.pdf')
        wait(pdf['id']);item=resource(pdf['id']);ex=extract_resource(item);rows=[getq(k) for k in ex['question_ids']]
        assert len(rows)==2 and len(rows[0]['source']['evidence'])==2 and rows[0]['payload']['answer']=='A'
        assert http(docs+'/'+pdf['id']+'/original',raw=True).startswith(b'%PDF-');check('same_pdf_reused_cross_page_questions_exact_locations')
        preview=http(docs+'/'+pdf['id']+'/preview?version_id='+item['source_version']+'&page=1',raw=True);assert preview.startswith(b'\x89PNG');check('private_bounded_pdf_preview')
        buf=BytesIO();Image.new('RGB',(320,200),'white').save(buf,format='PNG');image=upload(buf.getvalue(),'q.png');wait(image['id']);im=resource(image['id'])
        manual=extract_resource(im);draft=getq(manual['question_ids'][0]);assert draft['payload']['answer'] is None and 'no_text_manual_transcription_required' in draft['source']['warnings'];check('image_upload_without_fake_ocr_manual_recovery')
        # This is synthetic vision, not a real DeepSeek request or accuracy measurement.
        for count in (1,2):
            (folder/'vision-text.txt').write_text(TEXT.split('2. 判断')[0] if count==1 else TEXT,encoding='utf-8')
            current=http(docs+'/'+image['id'])
            request=cmd(expected_revision=current['revision'],version_id=current['version']['id'],pages=[1],consent_external=True)
            http(docs+'/'+image['id']+'/vision',dict(request,consent_external=False),expected=422)
            vr=http(docs+'/'+image['id']+'/vision',request,expected=202);assert wait(image['id'],vr['id'])['status']=='partial'
            converted=extract_resource(im,run_id=vr['id']);assert len(converted['question_ids'])==count
            assert getq(converted['question_ids'][0])['answer_provenance']=='model_inferred'
        check('mock_vision_one_and_multiple_questions_explicit_consent_no_paid_calls')
        rawpreview=http(docs+'/'+image['id']+'/preview?page=1',raw=True);assert rawpreview.startswith(b'\x89PNG')
        http(docs.replace('/a/','/b/')+'/'+image['id']+'/preview',expected=404);check('image_private_preview_and_other_student_denied')
        aid=http(prefix+'/knowledge-architectures',cmd(name='题库关联框架'))['architecture_id'];g=example()
        http(prefix+'/knowledge-architectures/'+aid+'/draft',cmd(expected_revision=1,graph=g),'PUT');http(prefix+'/knowledge-architectures/'+aid+'/publish',cmd(expected_revision=2,confirmed=True))
        item=resource(pdf['id']);links=[dict(architecture_id=aid,node_id=c['id'],kind='concept',review_status='confirmed') for c in g['concepts']]
        http(prefix+'/course-resources/'+item['resource_id'],cmd(expected_revision=item['revision'],resource_type='exercise_material',links=links),'PUT')
        q2=getq(rows[0]['id']);q2['payload']['concepts']=[dict(architecture_id=aid,concept_id=c['id']) for c in g['concepts']]
        http(bank+'/questions/'+q2['id'],cmd(expected_revision=q2['revision'],payload=q2['payload']),'PUT')
        assert http(bank+'/questions?chapter_id='+g['chapters'][0]['id'])['total']==1;check('many_concept_links_and_chapter_filter')
        current=http(docs+'/'+pdf['id']);upload(pdf_bytes(('1. 已更改来源条件',)),'v2.pdf',pdf['id'],cmd(expected_revision=current['revision'],course_id='machine_learning'));wait(pdf['id'])
        assert getq(rows[0]['id'])['source_status']=='modified'
        http(bank+'/extractions',cmd(resource_id=item['resource_id'],source_version=item['source_version']),expected=409);check('source_update_marks_old_question_and_rejects_old_extraction')
        current=http(docs+'/'+pdf['id']);http(docs+'/'+pdf['id'],cmd(expected_revision=current['revision']),'DELETE')
        assert getq(rows[0]['id'])['source_status']=='deleted';check('source_delete_preserves_review_snapshot_but_invalidates_current_source')
        refs=[dict(question_id=k,expected_revision=getq(k)['revision']) for k in batch['question_ids']]
        merged=http(bank+'/restructure',cmd(originals=refs,questions=[dict(stem='合并后待审核原题',question_type='other')]))['question_ids'][0]
        split=http(bank+'/restructure',cmd(originals=[dict(question_id=merged,expected_revision=1)],questions=[dict(stem='拆分题干一',question_type='other'),dict(stem='拆分题干二',question_type='other')]))
        assert len(split['question_ids'])==2 and getq(merged)['status']=='archived';check('merge_split_review_and_archive_transaction')
        assert formal()==baseline;check('all_formal_learning_notes_guidance_facts_unchanged')
        stop();start();assert http(bank+'/practice/'+sid)['result']['correct'] is False and getq(split['question_ids'][0])['status']=='draft';check('restart_readonly_restore_no_repeat_generation')
        assert formal()==baseline
        # Existing formal allocation/score remains separate; no new bank record enters it.
        decision=http(prefix+'/next',{},'POST');assert decision['question']['id'] not in {r['id'] for r in http(bank+'/questions')['items']}
        http(prefix+'/answers',dict(decision_id=decision['decision_id'],event_id=str(uuid4()),answer='A'));check('original_formal_learning_still_works_separately')
        calls=len((folder/'mock-calls.jsonl').read_text().splitlines())
        assert calls==2
        report=dict(passed=True,verified_at=datetime.now(timezone.utc).isoformat(),checks=checks,groups=len(checks),server_starts=starts,synthetic_vision_calls=calls,real_model_calls=0,private_materials_sent=0,formal_facts_unchanged_before_explicit_formal_regression=True,directory=str(folder))
        output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(dict(passed=True,groups=len(checks),mock_calls=calls,real_calls=0,report=str(output))))
    finally:stop()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--serve',type=Path);p.add_argument('--port',type=int);p.add_argument('--output',type=Path,default=Path('data/evaluation/phase4c-http-v1.json'));a=p.parse_args()
    if a.serve:serve(a.serve,a.port)
    else:verify(a.output)
