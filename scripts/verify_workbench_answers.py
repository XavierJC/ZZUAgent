"""Real localhost HTTP verification with an isolated DB and simulated provider."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener
from uuid import uuid4


def serve(directory, port):
    import uvicorn
    import eduagent.agent.deepseek as adapter
    from eduagent.agent.deepseek import ModelReply
    from eduagent.agent.settings import AgentSettings
    from eduagent.api.app import create_app
    from eduagent.api.settings import APISettings

    def complete(self, messages, tools, required=False):
        data = json.loads(messages[1]['content'])
        evidence = data['untrusted_evidence']
        assert set(data) == {'question', 'untrusted_evidence'}
        if not evidence:
            assert tools == []
        event = {'evidence_count': len(evidence), 'source_types': sorted({p['source_type'] for p in evidence}),
                 'tools_count': len(tools)}
        with (directory / 'calls.jsonl').open('a', encoding='utf8') as stream:
            stream.write(json.dumps(event) + '\n')
        mode = (directory / 'mode').read_text()
        ids = [p['citation_id'] for p in evidence[:1]]
        text = '模型模拟解释 $w$。' if evidence else '你好，本轮没有本地资料依据。'
        if mode == 'invented':
            ids = ['unselected:99']
        if mode != 'footer':
            text += ' '.join(f'[{key}]' for key in ids)
        raw = json.dumps({'answer': text, 'citation_ids': ids})
        if mode in ('hybrid', 'unused_sources'):
            raw = json.dumps({'answer': text if mode == 'hybrid' else '', 'citation_ids': ids if mode == 'hybrid' else [],
                              'supplement_md': '模型知识补充：PCA还可用于可视化与去噪。注意力机制通过加权组合信息。'})
        if mode == 'unbacked_answer':
            raw = json.dumps({'answer': '使用模型知识回答，不声称资料支持。', 'citation_ids': []})
        if mode == 'fenced':
            raw = '```json\n' + raw + '\n```'
        if mode == 'bad_json':
            raw = 'invalid JSON, do not persist rejected provider text'
        return ModelReply({'role': 'assistant', 'content': raw}, 12, 8)

    adapter.DeepSeekClient.complete = complete
    model = AgentSettings(enabled=True, api_key='synthetic-not-a-real-key')
    config = APISettings(data_dir=Path.cwd() / 'data', db_path=directory / 'http.sqlite3', agent=model)
    server = uvicorn.Server(uvicorn.Config(create_app(config), host='127.0.0.1', port=port, log_level='warning'))
    def stop():
        while not (directory / 'stop').exists():
            time.sleep(.05)
        server.should_exit = True
    threading.Thread(target=stop, daemon=True).start()
    server.run()


def verify(output):
    root = Path.cwd().resolve()
    directory = root / 'data/local' / ('workbench-answers-http-' + uuid4().hex[:8])
    directory.mkdir()
    (directory / 'mode').write_text('fenced')
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
    opener = build_opener(ProxyHandler({}))
    base = f'http://127.0.0.1:{port}'
    process = log = None
    checks = []
    starts = 0
    def http(path, body=None, expected=200, method=None):
        request = Request(base + path, data=None if body is None else json.dumps(body).encode(),
                          method=method or ('POST' if body is not None else 'GET'), headers={'Content-Type': 'application/json'})
        try:
            response = opener.open(request, timeout=15)
        except HTTPError as error:
            response = error
        with response:
            data = response.read()
            assert response.status == expected, (path, response.status, data[:180])
            return json.loads(data) if data else None
    def calls():
        path = directory / 'calls.jsonl'
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
    def start():
        nonlocal process, log, starts
        starts += 1
        (directory / 'stop').unlink(missing_ok=True)
        log = (directory / f'server-{starts}.log').open('w', encoding='utf8')
        process = subprocess.Popen([sys.executable, __file__, '--serve', str(directory), '--port', str(port)],
            stdout=log, stderr=log, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            assert process.poll() is None, 'verification server exited'
            try:
                http('/health'); return
            except (URLError, OSError):
                time.sleep(.1)
        raise AssertionError('verification server startup timeout')
    def stop():
        if process and process.poll() is None:
            (directory / 'stop').touch(); process.wait(timeout=20)
        if log:
            log.close()
    def check(name):
        checks.append({'name': name, 'passed': True})
    prefix = '/api/v1/students/a'
    def source(key):
        found = next(s for s in http(prefix + '/knowledge/sources')['items'] if s['source_id'] == key)
        return {k: found[k] for k in ('source_type', 'source_id', 'source_version')}
    def ask(refs, **extra):
        body = {'request_id': str(uuid4()), 'question': '梯度下降', 'course_id': 'machine_learning',
                'mode': 'model', 'allow_personal_external': False, 'sources': refs, **extra}
        return body, http(prefix + '/workbench/questions', body)
    def learning_facts():
        from eduagent.storage.migrations import fact_snapshot
        with sqlite3.connect((directory / 'http.sqlite3').as_uri() + '?mode=ro', uri=True) as db:
            return fact_snapshot(db)
    try:
        start()
        for owner in ('a', 'b'):
            http('/api/v1/students', {'student_id': owner})
        note = http(prefix + '/notes', {'id': str(uuid4()), 'title': '合成验证笔记',
            'content_md': '# 梯度下降\n\n沿负梯度方向更新。test_private_note_marker',
            'knowledge_point_ids': ['gradient_descent']}, expected=201)
        course, personal = source('gradient'), source(note['id'])
        baseline = learning_facts()
        request, run = ask([course])
        assert run['status'] == 'complete' and run['answer_basis'] == 'selected_sources'
        assert run['validation_error'] is None and run['citations']
        assert calls()[-1]['source_types'] == ['course_material']
        check('fenced_json_received_after_selected_source_rag')
        (directory / 'mode').write_text('footer')
        _, foot = ask([course])
        assert foot['status'] == 'complete' and '参考片段' in foot['answer'] and foot['model_calls'] == 1
        check('valid_reference_footer_added_without_extra_provider_call')
        (directory / 'mode').write_text('fenced')
        empty_request, empty = ask([course], question='hi deepseek')
        assert empty['answer_basis'] == 'model_knowledge' and empty['status'] == 'complete' and empty['citations'] == []
        assert calls()[-1] == {'evidence_count': 0, 'source_types': [], 'tools_count': 0}
        count = len(calls())
        assert http(prefix + '/workbench/questions', empty_request)['answer'] == empty['answer'] and len(calls()) == count
        check('no_match_calls_model_question_only_and_replay_is_idempotent')
        _, denied = ask([personal])
        assert denied['reason'] == 'personal_consent_required' and len(calls()) == count
        _, accepted = ask([personal], allow_personal_external=True)
        assert accepted['status'] == 'complete' and calls()[-1]['source_types'] == ['personal_note']
        http('/api/v1/students/b/workbench/questions', {**request, 'request_id': str(uuid4()), 'sources': [personal]}, expected=404)
        http(prefix + '/workbench/questions', {**request, 'request_id': str(uuid4()), 'sources': []}, expected=422)
        check('consent_student_isolation_and_empty_source_constraints_preserved')
        (directory / 'mode').write_text('invented')
        _, invented = ask([course])
        assert invented['reason'] == 'unverified_model_answer' and invented['validation_error'] == 'unknown_citation'
        assert 'unselected:99' not in invented['answer']
        (directory / 'mode').write_text('bad_json')
        bad_request, bad = ask([course])
        assert bad['validation_error'] == 'invalid_json' and bad['answer_basis'] == 'local_excerpts'
        assert 'rejected provider text' not in json.dumps(bad)
        assert http(prefix + '/workbench/runs/' + bad_request['request_id'])['validation_error'] == 'invalid_json'
        check('specific_validation_codes_persist_without_rejected_private_text')
        saved = http(prefix + '/workbench/runs/' + empty_request['request_id'] + '/note', {})
        saved_again = http(prefix + '/workbench/runs/' + empty_request['request_id'] + '/note', {})
        assert saved['note_id'] == saved_again['note_id']
        assert '模型自身知识' in http(prefix + '/notes/' + saved['note_id'])['content_md']
        assert learning_facts() == baseline
        check('answer_note_provenance_and_learning_facts_unchanged')
        pca = http(prefix + '/notes', {'id': str(uuid4()), 'title': '合成PCA资料',
            'content_md': '# PCA\n\nPCA将数据投影到正交主成分，保留主要方差信息。', 'knowledge_point_ids': []}, expected=201)
        (directory / 'mode').write_text('hybrid')
        compound_request, compound = ask([source(pca['id'])], question='PCA可以干什么，另外解释注意力机制', allow_personal_external=True)
        assert compound['answer_basis'] == 'mixed' and compound['citations']
        assert '可视化与去噪' in compound['supplement_md'] and '注意力机制' in compound['answer']
        assert '注意力' not in pca['content_md'] and '可视化' not in pca['content_md']
        check('partial_rag_context_still_generates_applications_and_uncovered_topic')
        (directory / 'mode').write_text('unused_sources')
        _, unused = ask([course])
        assert unused['answer_basis'] == 'model_knowledge' and unused['citations'] == []
        check('unused_retrieval_hits_do_not_force_invented_citations')
        (directory / 'mode').write_text('unbacked_answer')
        _, general = ask([course])
        assert general['status'] == 'complete' and general['answer_basis'] == 'model_knowledge' and general['citations'] == []
        check('uncited_general_answer_becomes_explicit_supplement_without_false_local_attribution')
        count = len(calls()); stop(); start()
        restored = http(prefix + '/workbench/runs/' + empty_request['request_id'])
        assert restored['answer_basis'] == 'model_knowledge' and restored['answer'] == empty['answer']
        assert http(prefix + '/workbench/questions', empty_request)['model_calls'] == 1 and len(calls()) == count
        compound_history = http(prefix + '/workbench/runs/' + compound_request['request_id'])
        assert compound_history['answer'] == compound['answer'] and compound_history['supplement_md'] == compound['supplement_md']
        assert learning_facts() == baseline
        check('restart_restores_original_answer_without_model_retry')
        report = {'verified_at': datetime.now(timezone.utc).isoformat(), 'passed': True, 'checks': checks,
                  'schema': 6, 'server_starts': starts, 'simulated_model_calls': len(calls()), 'real_model_calls': 0,
                  'test_directory': str(directory), 'production_database_writes': 0, 'browser_manual_validation': 'not_performed'}
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
        print(json.dumps(report))
    finally:
        stop()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--serve', type=Path)
    parser.add_argument('--port', type=int)
    parser.add_argument('--output', type=Path, default=Path('data/evaluation/workbench-generation-http-v1.json'))
    args = parser.parse_args()
    if args.serve:
        serve(args.serve, args.port)
    else:
        verify(args.output)
