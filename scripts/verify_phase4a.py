"""Isolated real HTTP Phase4A acceptance; synthetic model, zero paid calls.

Private file controls inject faults only in this test server. They are not
production endpoints. Existing learning data and .env are never used.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import threading
import time
from urllib.request import Request, build_opener, ProxyHandler
from urllib.error import HTTPError, URLError
from uuid import uuid4


def serve(directory, port, no_model):
    import uvicorn
    import eduagent.agent.deepseek as adapter
    from eduagent.agent.deepseek import ModelReply, ModelError
    from eduagent.agent.settings import AgentSettings
    from eduagent.api.app import create_app
    from eduagent.api.settings import APISettings

    class FakeProvider:
        def __init__(self, settings): pass
        def complete(self, messages, tools, required=False):
            data = json.loads(messages[1]['content'])
            with (directory/'calls.jsonl').open('a', encoding='utf8') as file:
                file.write(json.dumps({'types': sorted({p['source_type'] for p in data['untrusted_evidence']}),
                    'guide_context': 'server_guide_context' in data,
                    'identity_or_history_leak': any(key in json.dumps(data) for key in ('"student_id"', '"event_id"', '"batch_id"'))})+'\n')
            mode = (directory/'provider-mode').read_text()
            if mode in ('delay','delay-timeout'):
                (directory/'reached').touch(); deadline = time.monotonic()+25
                while not (directory/'release').exists():
                    if time.monotonic()>deadline: raise ModelError('model_timeout')
                    time.sleep(.03)
            if mode in ('timeout','delay-timeout'): raise ModelError('model_timeout')
            if mode == 'attack':
                return ModelReply({'role': 'assistant', 'content': None, 'tool_calls': [{
                    'id': 'attack', 'type': 'function', 'function': {'name': 'update_bkt', 'arguments': '{"probability":1}'}}]})
            ids = [p['citation_id'] for p in data['untrusted_evidence']]
            return ModelReply({'role': 'assistant', 'content': json.dumps({'answer': '模拟辅助讲解 $w$。'+''.join('['+key+']' for key in ids),
                'citation_ids': ids})}, 10, 7)
    adapter.DeepSeekClient = FakeProvider
    settings = APISettings(db_path=directory/'http.sqlite3', agent=AgentSettings() if no_model else AgentSettings(enabled=True, api_key='test-synthetic-only'))
    server = uvicorn.Server(uvicorn.Config(create_app(settings), host='127.0.0.1', port=port, log_level='warning', timeout_graceful_shutdown=3))
    def stop():
        while not (directory/'stop').exists(): time.sleep(.03)
        server.should_exit = True
    threading.Thread(target=stop, daemon=True).start(); server.run()


def verify(output):
    root = Path.cwd().resolve(); directory = root/'data/local'/('phase4a-http-'+uuid4().hex[:8]); directory.mkdir()
    (directory/'provider-mode').write_text('normal')
    with socket.socket() as listener:
        listener.bind(('127.0.0.1',0)); port=listener.getsockname()[1]
    opener=build_opener(ProxyHandler({})); base=f'http://127.0.0.1:{port}'
    checks=[]; process=None; log=None; starts=0
    def http(path, body=None, method=None, expected=200):
        request=Request(base+path, data=None if body is None else json.dumps(body).encode(),
                        method=method or ('POST' if body is not None else 'GET'), headers={'Content-Type':'application/json'})
        try: response=opener.open(request,timeout=35)
        except HTTPError as error: response=error
        with response:
            raw=response.read(); accepted=(expected,) if isinstance(expected,int) else expected
            assert response.status in accepted,(path,response.status,raw[:200])
            return json.loads(raw) if raw else None
    def start(no_model=False):
        nonlocal starts,process,log
        if (directory/'stop').exists(): (directory/'stop').unlink()
        starts+=1; log=(directory/f'server-{starts}.log').open('w',encoding='utf8')
        process=subprocess.Popen([sys.executable,__file__,'--serve',str(directory),'--port',str(port), *(['--no-model'] if no_model else [])],
            stdout=log,stderr=log,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            assert process.poll() is None,'test server exited'
            try: http('/health'); return
            except (URLError,OSError):time.sleep(.1)
        raise AssertionError('startup timeout')
    def stop():
        if process and process.poll() is None: (directory/'stop').touch(); process.wait(timeout=30)
        if log:log.close()
    def calls():
        path=directory/'calls.jsonl'; return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
    def mode(value):
        for name in ('reached','release'):
            if (directory/name).exists(): (directory/name).unlink()
        (directory/'provider-mode').write_text(value)
    def reached():
        deadline=time.monotonic()+15
        while not (directory/'reached').exists(): assert time.monotonic()<deadline; time.sleep(.03)
    def check(name):checks.append({'name':name,'passed':True})
    def old_tables():
        from eduagent.storage.migrations import preserved_snapshot, STUDY_TABLES
        db=sqlite3.connect((directory/'http.sqlite3').as_uri()+'?mode=ro',uri=True)
        try:return {k:v for k,v in preserved_snapshot(db)[0].items() if k not in STUDY_TABLES}
        finally:db.close()
    prefix='/api/v1/students/a'
    def source(key):
        item=next(s for s in http(prefix+'/knowledge/sources')['items'] if s['source_id']==key)
        return {k:item[k] for k in ('source_type','source_id','source_version')}
    def report(revision=0,**extra):
        return {'request_id':str(uuid4()),'course_id':'machine_learning','expected_revision':revision,
                'items':[{'knowledge_id':'linear_regression_loss','level':4,'confidence':5}],**extra}
    def guide(sources=None,**extra):
        snapshot=http(prefix+'/learning-guidance')
        return {'request_id':str(uuid4()),'course_id':'machine_learning','expected_learning_revision':snapshot['learning_revision'],
                'expected_assessment_revision':snapshot['assessment_revision'],'mode':'rules','sources':sources or [],'allow_personal_external':False,**extra}
    def generate(body,expected=200):return http(prefix+'/study-guides',body,expected=expected)
    try:
        start()
        for owner in ('a','b'):http('/api/v1/students',{'student_id':owner,'goals':['logistic_regression']})
        own=http(prefix+'/notes',{'id':str(uuid4()),'title':'合成自评测试笔记','content_md':'# 线性回归与损失函数\n\n均方误差衡量残差。privateunique 学习内容。',
                                'knowledge_point_ids':['linear_regression_loss']},expected=201)
        baseline=old_tables(); before=http(prefix+'/mastery')
        course,personal=source('linear'),source(own['id'])
        request=report()
        with ThreadPoolExecutor(max_workers=2) as pool:
            values=list(pool.map(lambda _:http(prefix+'/self-assessments',request,expected=(200,201)),range(2)))
        assert sorted(v['replayed'] for v in values)==[False,True]
        assert len(http(prefix+'/self-assessments')['items'])==1 and http(prefix+'/self-assessments/latest')['assessment_revision']==1
        check('atomic_report_concurrent_idempotency')
        http(prefix+'/self-assessments',{**request,'items':[{'knowledge_id':'linear_regression_loss','level':1,'confidence':None}]},expected=409)
        http(prefix+'/self-assessments',report(),expected=409)
        http('/api/v1/students/b/self-assessments/requests/'+request['request_id'],expected=404)
        assert http('/api/v1/students/b/self-assessments')['items']==[]
        check('report_cas_and_student_isolation')
        snapshot=http(prefix+'/learning-guidance')
        assert all(not p['objective']['has_evidence'] and p['objective']['probability'] is None for p in snapshot['items'])
        assert snapshot['recommendations'][0]['knowledge_id']=='linear_regression_loss'
        assert old_tables()==baseline
        check('consistent_snapshot_pending_diagnosis_no_assignment')
        local_request=guide(); local=generate(local_request)
        assert local['model_calls']==0 and local['citations']==[] and len(calls())==0
        assert http(prefix+'/study-guides/'+local['request_id'])['rules_md']==local['rules_md']
        generate(guide(mode='model'),expected=422)
        check('rules_empty_scope_never_queries_all_sources')
        denied=generate(guide([personal],mode='model'))
        assert denied['reason']=='personal_consent_required' and len(calls())==0
        check('guide_personal_consent_not_inherited')
        course_request=guide([course],mode='model'); course_run=generate(course_request)
        assert course_run['status']=='complete' and calls()[-1]['types']==['course_material']
        personal_run=generate(guide([personal],mode='model',allow_personal_external=True))
        assert personal_run['status']=='complete' and calls()[-1]['types']==['personal_note']
        mixed=generate(guide([course,personal],mode='model',allow_personal_external=True))
        assert {c['source_type'] for c in mixed['citations']}=={'course_material','personal_note'}
        assert all(call['guide_context'] and not call['identity_or_history_leak'] for call in calls())
        check('course_personal_mixed_scopes_and_summary_redaction')
        for c in mixed['citations']:
            raw=http(prefix+'/workbench/sources/open',{k:c[k] for k in ('source_type','source_id','source_version')})['raw_md']
            assert raw[c['start_offset']:c['end_offset']]==c['raw_md']
        http('/api/v1/students/b/study-guides/'+mixed['request_id'],expected=404)
        http('/api/v1/students/b/study-guides',guide([personal],expected_assessment_revision=0),expected=404)
        check('citations_match_snapshots_and_cross_student_denied')
        mode('attack'); attack=generate(guide([course],mode='model'))
        assert attack['reason']=='tool_scope_rejected' and attack['explanation_md']==''
        check('model_cannot_change_bkt_or_focus')
        mode('timeout'); timeout_request=guide([course],mode='model'); timeout=generate(timeout_request); count=len(calls())
        assert timeout['status']=='uncertain' and generate(timeout_request)['status']=='uncertain' and len(calls())==count
        check('timeout_no_automatic_paid_retry')
        assert old_tables()==baseline and http(prefix+'/mastery')==before and http(prefix+'/history')['items']==[]
        check('reports_and_guides_preserve_all_original_twelve_tables')
        mode('delay-timeout'); combined=guide([course],mode='model')
        with ThreadPoolExecutor(max_workers=2) as pool:
            future=pool.submit(generate,combined); reached()
            http(prefix+'/self-assessments',report(1,items=[{'knowledge_id':'linear_regression_loss','level':3,'confidence':None}]),expected=201)
            (directory/'release').touch(); uncertain_stale=future.result(timeout=30)
        assert uncertain_stale['status']=='uncertain' and uncertain_stale['reason']=='model_timeout'
        assert 'self_assessment_changed' in uncertain_stale['stale_reasons']
        count=len(calls()); assert generate(combined)['status']=='uncertain' and len(calls())==count
        check('timeout_and_expired_snapshot_preserve_no_retry_state')
        mode('delay'); race=guide([course],mode='model')
        with ThreadPoolExecutor(max_workers=2) as pool:
            future=pool.submit(generate,race); reached(); count=len(calls())
            assert generate(race)['status']=='uncertain' and len(calls())==count
            new=http(prefix+'/self-assessments',report(2,items=[{'knowledge_id':'linear_regression_loss','level':2,'confidence':None}]),expected=201)
            (directory/'release').touch(); stale=future.result(timeout=30)
        assert new['committed_revision']==3 and stale['status']=='stale' and 'self_assessment_changed' in stale['stale_reasons']
        assert stale['snapshot']['learning_revision']==0 and stale['snapshot']['assessment_revision']==2
        check('inflight_duplicate_and_self_revision_race')
        mode('delay'); race=guide([personal],mode='model',allow_personal_external=True)
        with ThreadPoolExecutor(max_workers=2) as pool:
            future=pool.submit(generate,race); reached()
            http(prefix+'/notes/'+own['id'],{'expected_revision':1,'content_md':'# 线性回归\n\nchangedunique 新版均方误差。'},method='PATCH')
            (directory/'release').touch(); stale_note=future.result(timeout=30)
        assert stale_note['status']=='stale' and 'sources_changed' in stale_note['stale_reasons']
        assert 'privateunique' in stale_note['citations'][0]['raw_md']
        generate(guide([personal]),expected=409)
        assert not http(prefix+'/knowledge/search',{'query':'privateunique','sources':[source(own['id'])]})['items']
        check('source_version_race_and_old_index_excluded')
        mode('delay'); race=guide([course],mode='model')
        with ThreadPoolExecutor(max_workers=2) as pool:
            future=pool.submit(generate,race); reached()
            decision=http(prefix+'/next',{},'POST'); receipt=http(prefix+'/answers',{'decision_id':decision['decision_id'],'event_id':str(uuid4()),'answer':'A'})
            (directory/'release').touch(); stale_answer=future.result(timeout=30)
        assert receipt['correct'] is False and stale_answer['status']=='stale' and 'learning_state_changed' in stale_answer['stale_reasons']
        changed=http(prefix+'/learning-guidance'); focus=changed['recommendations'][0]
        assert focus['objective']['attempts']==1 and focus['objective']['last_correct'] is False and 'recent_error' in focus['reason_codes']
        check('objective_revision_race_and_explainable_recommendation_change')
        from eduagent.domain.catalog import Catalog
        catalog=Catalog.load(root/'data'); decision=http(prefix+'/next',{},'POST')
        wrong=next(answer for answer in decision['question']['options'] if answer!=catalog.questions[decision['question']['id']].answer)
        http(prefix+'/answers',{'decision_id':decision['decision_id'],'event_id':str(uuid4()),'answer':wrong})
        point=next(p for p in http(prefix+'/learning-guidance')['items'] if p['knowledge_id']=='linear_regression_loss')
        assert point['available_questions']==0 and 'questions_exhausted' in point['reason_codes']
        assert not any(a['kind']=='open_formal_practice' for a in point['actions'])
        check('formal_exercise_exhaustion_is_explicit')
        http(prefix+f"/notes/{own['id']}?expected_revision=2",method='DELETE',expected=204)
        history=http(prefix+'/study-guides/'+stale_note['request_id'])
        assert history['source_statuses'][0]['current_status']=='deleted' and history['rules_md']==stale_note['rules_md']
        generate(guide([personal]),expected=404)
        check('deleted_sources_and_immutable_history_content')
        count=len(calls()); stop()
        # Inject one unresolved claim only into this private test DB to audit
        # startup behavior without killing or manipulating the real service.
        with sqlite3.connect(directory/'http.sqlite3') as db:
            db.execute("UPDATE study_guide_runs SET status='running' WHERE request_id=?",(timeout_request['request_id'],))
        start(no_model=True)
        assert generate(timeout_request)['status']=='uncertain' and len(calls())==count
        assert generate(course_request)['status']=='stale' and len(calls())==count
        assert http(prefix+'/self-assessments/latest')['assessment_revision']==3
        no_key=generate(guide([course],mode='model'))
        assert no_key['reason']=='model_disabled' and no_key['model_calls']==0
        assert generate(guide())['model_calls']==0
        check('process_restart_recovers_without_model_or_paid_replay')
        assert http('/api/v1/materials/search',{'query':'线性回归'})
        assert len(http(prefix+'/history')['items'])==2 and http(prefix+'/tutor-runs')==[] and http(prefix+'/workbench/runs')==[]
        check('legacy_retrieval_score_bkt_and_histories_compatible')
        with sqlite3.connect(directory/'http.sqlite3') as db:
            assert db.execute('PRAGMA user_version').fetchone()[0]==10
            assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok' and not db.execute('PRAGMA foreign_key_check').fetchall()
        output.write_text(json.dumps({'passed':True,'verified_at':datetime.now(timezone.utc).isoformat(),'checks':checks,
            'server_starts':starts,'schema':10,'model_kind':'simulated','simulated_model_calls':len(calls()),'real_model_calls':0,
            'test_directory':str(directory),'production_learning_writes':0,'browser_manual_validation':'not_performed',
            'fault_injection':'Private verification server/file controls and one unresolved claim in the isolated DB only.'},ensure_ascii=False,indent=2),encoding='utf8')
        print(json.dumps({'passed':True,'checks':len(checks),'simulated_calls':len(calls()),'real_calls':0,'report':str(output)}))
    finally:stop()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--serve',type=Path);parser.add_argument('--port',type=int);parser.add_argument('--no-model',action='store_true')
    parser.add_argument('--output',type=Path,default=Path('data/evaluation/phase4a-http-v1.json'));args=parser.parse_args()
    if args.serve:serve(args.serve,args.port,args.no_model)
    else:verify(args.output)
