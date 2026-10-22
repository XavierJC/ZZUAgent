"""Real localhost HTTP acceptance for Phase4B-1; synthetic files/models only."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from hashlib import sha256
import http.client
import json
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, ProxyHandler
from uuid import uuid4


def serve(directory, port, vision):
    import uvicorn
    from eduagent.agent.settings import AgentSettings
    from eduagent.agent.deepseek import ModelReply, ModelError
    from eduagent.api.app import create_app
    from eduagent.api.settings import APISettings
    from eduagent.documents.limits import run_worker
    from eduagent.documents.models import DocumentError
    class SyntheticVision:
        def complete(self, messages, tools):
            assert tools == []
            blocks = messages[1]['content']
            assert len(blocks) == 2 and blocks[1]['image_url']['url'].startswith('data:image/png;base64,')
            with (directory/'calls.jsonl').open('a', encoding='utf8') as file:
                file.write(json.dumps({'image_count': 1, 'tools': 0, 'synthetic': True})+'\n')
            mode = (directory/'mode').read_text()
            if mode.startswith('delay'):
                (directory/'reached').touch()
                deadline = time.monotonic()+15
                while not (directory/'release').exists():
                    if time.monotonic()>deadline: raise ModelError('model_timeout')
                    time.sleep(.03)
            if mode in ('timeout', 'delay-timeout'): raise ModelError('model_timeout')
            return ModelReply({'content': json.dumps({'transcription_md': '# 合成视觉文字\n\n$x^T x$',
                'interpretation_md': '模拟图示解释，非原文。', 'warnings': []})}, 15, 12)
    def runner(manifest, output, **kwargs):
        if (directory/'mode').read_text() == 'parse-fail': raise DocumentError('parse_timeout')
        return run_worker(manifest, output, **kwargs)
    settings = APISettings(db_path=directory/'http.sqlite3', document_vision_enabled=vision,
        agent=AgentSettings(api_key='synthetic-only') if vision else AgentSettings())
    server = uvicorn.Server(uvicorn.Config(create_app(settings, document_runner=runner,
        document_vision_factory=SyntheticVision), host='127.0.0.1', port=port, log_level='warning', timeout_graceful_shutdown=3))
    def stop():
        while not (directory/'stop').exists(): time.sleep(.03)
        server.should_exit = True
    threading.Thread(target=stop, daemon=True).start(); server.run()


def verify(output):
    from eduagent.storage.migrations import preserved_snapshot, DOCUMENT_TABLES
    sys.path.insert(0, str(Path('backend/tests').resolve()))
    from document_fixtures import pdf_bytes, pptx_bytes
    directory = Path('data/local').resolve()/('phase4b1-http-'+uuid4().hex[:8]); directory.mkdir()
    (directory/'mode').write_text('normal')
    with socket.socket() as sock: sock.bind(('127.0.0.1',0)); port = sock.getsockname()[1]
    opener = build_opener(ProxyHandler({})); base = f'http://127.0.0.1:{port}'
    prefix = '/api/v1/students/a/documents'; process = None; log = None; starts = 0; checks = []
    def http(path, body=None, method=None, expected=200, raw=False, headers=None):
        request = Request(base+path, data=body if isinstance(body, bytes) else None if body is None else json.dumps(body).encode(),
            method=method or ('POST' if body is not None else 'GET'), headers=headers or {'Content-Type':'application/json'})
        try: response = opener.open(request, timeout=30)
        except HTTPError as exc: response = exc
        with response:
            value = response.read()
            assert response.status == expected, (path,response.status,value[:250])
            return value if raw else json.loads(value) if value else None
    def start(vision=False):
        nonlocal process, log, starts
        (directory/'stop').unlink(missing_ok=True); starts += 1
        log = (directory/f'server-{starts}.log').open('w',encoding='utf8')
        process = subprocess.Popen([sys.executable, __file__, '--serve', str(directory), '--port', str(port), *(['--vision'] if vision else [])],
            stdout=log,stderr=log,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        deadline = time.monotonic()+25
        while time.monotonic()<deadline:
            assert process.poll() is None, 'isolated server exited'
            try: http('/health'); return
            except (URLError,OSError): time.sleep(.1)
        raise AssertionError('startup timeout')
    def stop():
        if process and process.poll() is None: (directory/'stop').touch(); process.wait(timeout=30)
        if log: log.close()
    def check(name): checks.append({'name':name,'passed':True})
    def mode(value):
        for name in ('reached','release'): (directory/name).unlink(missing_ok=True)
        (directory/'mode').write_text(value)
    def wait(key, run_id=None):
        deadline = time.monotonic()+20
        while time.monotonic()<deadline:
            value = http(prefix+'/'+key+('/parse-runs/'+run_id if run_id else ''))
            run = value if run_id else value['parse']
            if run['status'] not in ('pending','processing'): return value
            time.sleep(.05)
        raise AssertionError('parse task timeout')
    def upload(raw, name='course.md', document=None, meta=None, expected=202):
        metadata = meta or dict(request_id=str(uuid4()), title='合成课件', local_rights_confirmed=True)
        boundary = 'eduagent'+uuid4().hex
        mime = {'pdf':'application/pdf','pptx':'application/vnd.openxmlformats-officedocument.presentationml.presentation',
                'md':'text/markdown','txt':'text/plain'}.get(name.rsplit('.',1)[-1], 'application/octet-stream')
        body = (f'--{boundary}\r\nContent-Disposition: form-data; name="metadata"\r\n\r\n'.encode()+json.dumps(metadata).encode()+
            f'\r\n--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{name}"\r\nContent-Type: {mime}\r\n\r\n'.encode()+raw+f'\r\n--{boundary}--\r\n'.encode())
        return http(prefix+('/'+document+'/versions' if document else ''),body,expected=expected,
                    headers={'Content-Type':'multipart/form-data; boundary='+boundary})
    def facts():
        with sqlite3.connect(directory/'http.sqlite3') as db:
            return {k:v for k,v in preserved_snapshot(db)[0].items() if k not in DOCUMENT_TABLES}
    def calls():
        path=directory/'calls.jsonl'; return path.read_text().splitlines() if path.exists() else []
    def mutation(doc): return dict(request_id=str(uuid4()), expected_revision=doc['revision'])
    def vision(doc): return {**mutation(doc),'version_id':doc['version']['id'],'pages':[1],'consent_external':True}
    try:
        start()
        for student in ('a','b'): http('/api/v1/students', {'student_id':student})
        before = facts(); docs = []
        for name, raw, expected in [('course.md','# 合成文档\n\n学习率 $w$'.encode(),'学习率'),
            ('course.txt','模型评估 合成资料'.encode(),'模型评估'), ('course.pdf',pdf_bytes(('主成分分析','第二页'),image=True),'主成分分析'),
            ('course.pptx',pptx_bytes(),'主要变化方向')]:
            created = upload(raw,name); doc = wait(created['id']); docs.append(doc)
            units = http(prefix+'/'+doc['id']+'/units')['items']
            assert expected in ' '.join(u['text'] for u in units)
            assert http(prefix+'/'+doc['id']+'/original',raw=True) == raw
        assert docs[2]['parse']['unit_count']==2 and docs[3]['parse']['unit_count']==2
        check('four_native_formats_original_bytes_and_page_slide_positions')
        assert any('image_content_not_extracted' in u['warnings'] for u in http(prefix+'/'+docs[2]['id']+'/units')['items'])
        assert any(b['kind']=='formula_omml' for u in http(prefix+'/'+docs[3]['id']+'/units')['items'] for b in u['blocks'])
        scan=wait(upload(pdf_bytes(('',),image=True),'scan.pdf')['id'])
        assert scan['parse']['status']=='empty'; check('formulas_images_and_scan_limitations_explicit')
        assert not http(prefix+'/capabilities')['vision_enabled'] and len(calls())==0
        http(prefix+'/'+docs[2]['id']+'/vision',vision(docs[2]),expected=503)
        assert http('/api/v1/materials/search',{'query':'线性回归'}) and facts()==before
        check('no_model_key_native_parsing_and_legacy_retrieval')
        for suffix in ('','/units','/versions','/original','/parse-runs'):
            http((prefix+'/'+docs[0]['id']+suffix).replace('/a/','/b/'),expected=404)
        check('cross_student_document_and_original_denied')
        meta=dict(request_id=str(uuid4()),title='并发合成资料',local_rights_confirmed=True)
        raw=b'# idempotent\n\nunique'
        created=upload(raw,meta=meta); upload(raw,meta=meta,expected=200)
        upload(b'changed',meta=meta,expected=409); upload(raw,expected=409)
        http(prefix+'/operations/'+meta['request_id']); assert len(http(prefix)['items'])==6
        check('upload_receipt_hash_conflict_and_duplicate_content')
        first=docs[0]; updated=wait(upload(b'# new version\n\nnew-current',document=first['id'],
            meta={**mutation(first),'course_id':'machine_learning'})['id'])
        assert updated['version']['file_revision']==2
        assert 'new-current' in http(prefix+'/'+first['id']+'/units')['items'][0]['text']
        assert http(prefix+'/'+first['id']+'/parse-runs/'+first['parse']['id'])['current_status']=='modified'
        http(prefix+'/'+first['id'],{**mutation(first),'title':'stale'},method='PATCH',expected=409)
        check('version_update_cas_and_old_snapshot_label')
        deletion=mutation(updated); http(prefix+'/'+updated['id'],deletion,method='DELETE'); http(prefix+'/'+updated['id'],deletion,method='DELETE')
        http(prefix+'/'+updated['id']+'/original',expected=404)
        assert updated['id'] not in [d['id'] for d in http(prefix)['items']]
        check('soft_delete_idempotent_immediately_invisible')
        for name, data, status in [('fake.pdf',b'bad',422),('bad.txt',b'\xff',422),('big.md',b'x'*(2*1024*1024+1),413),('bad.exe',b'bad',415)]:
            upload(data,name,expected=status)
        broken=wait(upload(pdf_bytes(encrypted=True),'encrypted.pdf')['id'])
        assert broken['parse']['error_code']=='encrypted_document'
        check('format_encoding_size_and_encryption_fail_safely')
        mode('parse-fail'); failed=wait(upload(b'failure original','failure.md')['id'])
        assert failed['parse']['error_code']=='parse_timeout' and http(prefix+'/'+failed['id']+'/original',raw=True)==b'failure original'
        mode('normal'); http(prefix+'/'+failed['id']+'/parse',mutation(failed),expected=202)
        failed=wait(failed['id']); assert failed['parse']['status']=='ready'
        check('parse_failure_keeps_original_and_explicit_retry_recovers')
        assert facts()==before and len(calls())==0
        stop()
        from eduagent.storage.sqlite import SQLiteRepository
        from eduagent.services.documents import DocumentsService
        with SQLiteRepository(directory/'http.sqlite3') as repo:
            service=DocumentsService(repo,(directory/'http.sqlite3').with_suffix('.documents'))
            service.mutate('a',failed['id'],mutation(failed),'parse')
            assert service.claim()['document_id']==failed['id']
        start(vision=True); failed=wait(failed['id']); assert failed['parse']['status']=='ready'
        assert http(prefix+'/'+docs[1]['id']+'/units')['items'][0]['text'].startswith('模型评估')
        check('restart_restores_originals_results_and_interrupted_local_task')
        pdf=docs[2]; body=vision(pdf); http(prefix+'/'+pdf['id']+'/vision',{**body,'consent_external':False},expected=422)
        assert len(calls())==0
        queued=http(prefix+'/'+pdf['id']+'/vision',body,expected=202); complete=wait(pdf['id'],queued['id'])
        assert complete['model_calls']==1 and complete['status']=='partial'
        http(prefix+'/'+pdf['id']+'/vision',body,expected=200)
        units=http(prefix+'/'+pdf['id']+'/units?run_id='+queued['id'])['items']
        assert units[0]['origin']=='deepseek_vision' and units[0]['interpretation_md']!=units[0]['text']
        assert http(prefix+'/'+pdf['id'])['parse']['id']==pdf['parse']['id'] and len(calls())==1
        check('mock_page_vision_consent_idempotency_native_separation')
        mode('delay'); race=http(prefix+'/'+pdf['id']+'/vision',vision(pdf),expected=202)
        deadline=time.monotonic()+15
        while not (directory/'reached').exists(): assert time.monotonic()<deadline; time.sleep(.03)
        pdf=http(prefix+'/'+pdf['id'],{**mutation(pdf),'title':'标题更新'},method='PATCH')
        (directory/'release').touch(); stale=wait(pdf['id'],race['id'])
        assert stale['status']=='superseded' and stale['current_status']=='modified'
        check('mock_vision_revision_race_cannot_replace_current')
        mode('timeout'); uncertain_body=vision(pdf); uncertain=http(prefix+'/'+pdf['id']+'/vision',uncertain_body,expected=202)
        assert wait(pdf['id'],uncertain['id'])['status']=='uncertain'; count=len(calls())
        stop(); mode('normal'); start(vision=True)
        assert http(prefix+'/'+pdf['id']+'/vision',uncertain_body,expected=200)['id']==uncertain['id']
        assert http(prefix+'/'+pdf['id']+'/parse-runs/'+uncertain['id'])['status']=='uncertain' and len(calls())==count
        check('mock_timeout_restart_and_get_never_repeat_paid_call')
        assert facts()==before
        assert http('/api/v1/students/a/history')['items']==[]
        assert http('/api/v1/students/a/self-assessments/latest')['assessment_revision']==0
        check('all_fifteen_original_tables_and_bkt_unchanged')
        with sqlite3.connect(directory/'http.sqlite3') as db:
            assert db.execute('PRAGMA user_version').fetchone()[0]==8
            assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok' and not db.execute('PRAGMA foreign_key_check').fetchall()
        check('schema8_integrity_and_foreign_keys')
        output.write_text(json.dumps({'passed':True,'verified_at':datetime.now(timezone.utc).isoformat(),'checks':checks,
            'server_starts':starts,'schema':8,'simulated_vision_calls':len(calls()),'real_model_calls':0,'real_material_transmissions':0,
            'test_directory':str(directory),'production_writes':0,'browser_manual_validation':'not_performed',
            'accuracy_scope':'Self-created text/OOXML fixtures; no real textbook or visual recognition accuracy claim.'},ensure_ascii=False,indent=2),encoding='utf8')
        print(json.dumps({'passed':True,'checks':len(checks),'simulated_vision_calls':len(calls()),'real_calls':0,'report':str(output)}))
    finally: stop()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--serve',type=Path); parser.add_argument('--port',type=int); parser.add_argument('--vision',action='store_true')
    parser.add_argument('--output',type=Path,default=Path('data/evaluation/phase4b1-http-v1.json')); args=parser.parse_args()
    if args.serve: serve(args.serve,args.port,args.vision)
    else: verify(args.output)
