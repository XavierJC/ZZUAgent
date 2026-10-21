"""Real localhost HTTP, synthetic notes and a fake provider. Zero paid requests.

All injection/delay hooks exist only in this executable verification server.
Its own subprocess is gracefully stopped using a private file signal.
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
    from eduagent.agent.settings import AgentSettings
    from eduagent.agent.deepseek import ModelReply, ModelError
    import eduagent.agent.deepseek as adapter
    from eduagent.api.app import create_app
    from eduagent.api.settings import APISettings

    class SyntheticProvider:
        def __init__(self, _):
            pass

        def complete(self, messages, tools, required=False):
            initial = json.loads(messages[1]['content'])
            question = initial['question']
            # Store counts/types only, not private note content or credentials.
            with (directory / 'calls.jsonl').open('a', encoding='utf8') as file:
                file.write(json.dumps({'types': sorted({s['source_type'] for s in initial['untrusted_evidence']})}) + '\n')
            if 'delaymarker' in question:
                (directory / 'provider-reached').touch()
                deadline = time.monotonic() + 20
                while not (directory / 'release-provider').exists():
                    if time.monotonic() > deadline:
                        raise ModelError('model_timeout')
                    time.sleep(0.03)
            if 'timeoutmarker' in question:
                raise ModelError('model_timeout')
            if 'attackmarker' in question:
                return ModelReply({'role': 'assistant', 'content': None, 'tool_calls': [{
                    'id': 'attack', 'type': 'function', 'function': {'name': 'retrieve_selected_sources',
                    'arguments': json.dumps({'query': '梯度下降', 'student_id': 'b', 'source_ids': ['unselected']})}}]})
            ids = [item['citation_id'] for item in initial['untrusted_evidence']]
            return ModelReply({'role': 'assistant', 'content': json.dumps({'answer': '模拟解释 $w$。' + ''.join(f'[{key}]' for key in ids),
                                                                         'citation_ids': ids})}, 10, 5)
    adapter.DeepSeekClient = SyntheticProvider
    settings = APISettings(db_path=directory / 'http.sqlite3', agent=AgentSettings() if no_model else AgentSettings(enabled=True, api_key='synthetic-not-a-key'))
    server = uvicorn.Server(uvicorn.Config(create_app(settings), host='127.0.0.1', port=port, log_level='warning', timeout_graceful_shutdown=3))
    def stop():
        while not (directory / 'stop-server').exists():
            time.sleep(0.03)
        server.should_exit = True
    threading.Thread(target=stop, daemon=True).start()
    server.run()


def verify(output):
    directory = Path('data/local').resolve() / ('workbench-http-' + uuid4().hex[:8])
    directory.mkdir()
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0)); port = listener.getsockname()[1]
    base = f'http://127.0.0.1:{port}'
    opener = build_opener(ProxyHandler({}))
    checks, starts, process, log = [], 0, None, None

    def http(path, body=None, method=None, expected=200):
        data = None if body is None else json.dumps(body).encode()
        request = Request(base + path, data=data, method=method or ('POST' if body is not None else 'GET'), headers={'Content-Type': 'application/json'})
        try:
            response = opener.open(request, timeout=30)
        except HTTPError as error:
            response = error
        with response:
            raw = response.read()
            assert response.status == expected, (path, response.status, raw[:200])
            return json.loads(raw) if raw else None

    def start(no_model=False):
        nonlocal process, starts, log
        signal = directory / 'stop-server'
        if signal.exists(): signal.unlink()
        starts += 1
        log = (directory / f'server-{starts}.log').open('w', encoding='utf8')
        process = subprocess.Popen([sys.executable, __file__, '--serve', str(directory), '--port', str(port), *(['--no-model'] if no_model else [])],
                                   stdout=log, stderr=log, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if process.poll() is not None: raise AssertionError('test server exited')
            try:
                http('/health'); return
            except (URLError, OSError): time.sleep(0.1)
        raise AssertionError('test server startup timeout')

    def stop():
        if process and process.poll() is None:
            (directory / 'stop-server').touch()
            process.wait(timeout=30)
        if log: log.close()

    prefix = '/api/v1/students/a'
    wb = prefix + '/workbench'
    def count():
        path = directory / 'calls.jsonl'
        return len(path.read_text().splitlines()) if path.exists() else 0
    def selected(key):
        item = next(i for i in http(prefix + '/knowledge/sources')['items'] if i['source_id'] == key)
        return {k: item[k] for k in ('source_type', 'source_id', 'source_version')}
    def ask(refs, question='梯度下降', **extra):
        return {'request_id': str(uuid4()), 'question': question, 'sources': refs, 'course_id': 'machine_learning', 'mode': 'model', 'allow_personal_external': False, **extra}
    def check(name): checks.append({'name': name, 'passed': True})
    try:
        start()
        for owner in ('a', 'b'): http('/api/v1/students', {'student_id': owner})
        before = http(prefix + '/mastery')
        own = http(prefix + '/notes', {'id': str(uuid4()), 'title': '合成测试笔记', 'content_md': '# 梯度下降\n\n沿负梯度更新 $w$。 starunique',
                                      'knowledge_point_ids': ['gradient_descent']}, expected=201)
        other = http('/api/v1/students/b/notes', {'id': str(uuid4()), 'title': '另一个演示学生的合成笔记', 'content_md': 'secretother 梯度下降', 'knowledge_point_ids': []}, expected=201)
        course, personal = selected('gradient'), selected(own['id'])
        course_request = ask([course]); course_run = http(wb + '/questions', course_request)
        assert course_run['status'] == 'complete' and all(c['source_type'] == 'course_material' for c in course_run['citations'])
        check('course_only_scoped')
        local = http(wb + '/questions', ask([personal])); assert local['reason'] == 'personal_consent_required' and count() == 1
        check('no_consent_zero_model_transmission')
        personal_run = http(wb + '/questions', ask([personal], allow_personal_external=True))
        assert all(c['source_type'] == 'personal_note' for c in personal_run['citations'])
        joint = http(wb + '/questions', ask([course, personal], allow_personal_external=True))
        assert {c['source_type'] for c in joint['citations']} == {'course_material', 'personal_note'}
        check('personal_and_combined_scopes')
        for c in joint['citations']:
            preview = http(wb + '/sources/open', {k: c[k] for k in ('source_type', 'source_id', 'source_version')})
            assert preview['raw_md'][c['start_offset']:c['end_offset']] == c['raw_md']
        check('citation_snapshots_match_raw_positions')
        http(wb + '/questions', ask([]), expected=422)
        http('/api/v1/students/b/workbench/questions', ask([personal]), expected=404)
        http('/api/v1/students/b/workbench/runs/' + joint['request_id'], expected=404)
        http('/api/v1/students/b/workbench/sources/open', personal, expected=404)
        assert own['id'] not in json.dumps(http('/api/v1/students/b/knowledge/sources'))
        check('empty_and_cross_student_denied')
        attack = http(wb + '/questions', ask([course], '梯度下降 attackmarker'))
        assert attack['reason'] == 'tool_scope_rejected' and attack['model_calls'] == 1
        check('model_scope_attack_rejected')
        timeout_request = ask([course], '梯度下降 timeoutmarker')
        timeout = http(wb + '/questions', timeout_request); n = count()
        assert timeout['status'] == 'uncertain'
        assert http(wb + '/questions', timeout_request)['status'] == 'uncertain' and count() == n
        check('timeout_receipt_no_paid_retry')
        # One in-flight provider call: a simultaneous duplicate reads its claim.
        with ThreadPoolExecutor(max_workers=2) as pool:
            request = ask([personal], '梯度下降 delaymarker', allow_personal_external=True)
            future = pool.submit(http, wb + '/questions', request)
            deadline = time.monotonic() + 15
            while not (directory / 'provider-reached').exists():
                assert time.monotonic() < deadline; time.sleep(0.03)
            n = count()
            assert http(wb + '/questions', request)['status'] == 'uncertain' and count() == n
            changed = http(prefix + '/notes/' + own['id'], {'expected_revision': 1, 'content_md': '# 新内容\n\nmoonunique 梯度下降'}, method='PATCH')
            (directory / 'release-provider').touch()
            stale = future.result(timeout=30)
        assert stale['status'] == 'stale' and stale['source_statuses'][0]['current_status'] == 'modified'
        assert 'starunique' in stale['citations'][0]['raw_md']
        http(wb + '/questions', ask([personal]), expected=409)
        assert not http(prefix + '/knowledge/search', {'query': 'starunique', 'sources': [selected(own['id'])]})['items']
        check('inflight_duplicate_and_revision_race')
        # Concurrent answer saves must create exactly one new note.
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(http, wb + '/runs/' + course_run['request_id'] + '/note', {}, 'POST') for _ in range(2)]
            saves = [f.result() for f in futures]
        assert saves[0]['note_id'] == saves[1]['note_id']
        saved_id = saves[0]['note_id']
        edited = http(prefix + '/notes/' + saved_id, {'expected_revision': 1, 'content_md': '# 我的编辑\n\neditableunique 梯度下降'}, method='PATCH')
        assert http(wb + '/runs/' + course_run['request_id'] + '/note', {}, 'POST')['edited']
        assert http(prefix + '/knowledge/search', {'query': 'editableunique', 'sources': [selected(saved_id)]})['items']
        check('save_note_concurrent_idempotency_edit_and_index')
        http(prefix + f"/notes/{own['id']}?expected_revision=2", method='DELETE', expected=204)
        assert http(wb + '/runs/' + stale['request_id'])['source_statuses'][0]['current_status'] == 'deleted'
        http(wb + '/questions', ask([personal]), expected=404)
        check('deleted_sources_excluded_history_snapshot_retained')
        assert http(prefix + '/mastery') == before and http(prefix + '/history')['items'] == []
        assert http(prefix + '/tutor-runs') == []
        check('workbench_and_save_preserve_bkt_and_legacy_history')
        n = count(); stop(); start(no_model=True)
        history = http(wb + '/runs'); assert any(r['request_id'] == joint['request_id'] for r in history)
        http(wb + '/questions', course_request)
        assert count() == n
        recovered = http(wb + '/questions', ask([selected(saved_id)], 'editableunique', mode='local'))
        assert recovered['citations'] and recovered['model_calls'] == 0
        assert not http(wb + '/capabilities')['model_enabled']
        check('restart_history_replay_and_no_key_local_retrieval')
        assert http('/api/v1/materials/search', {'query': '梯度下降'})
        check('legacy_course_retrieval_compatible')
        # Exercise core flow using synthetic events only in this isolated DB.
        decision = http(prefix + '/next', {}, 'POST')
        graded = http(prefix + '/answers', {'decision_id': decision['decision_id'], 'event_id': str(uuid4()), 'answer': 'B'})
        assert 'correct' in graded and http(prefix + '/mastery')['revision'] == 1
        assert len(http(prefix + '/history')['items']) == 1
        check('legacy_score_bkt_history_http_regression')
        report = {'verified_at': datetime.now(timezone.utc).isoformat(), 'passed': True, 'checks': checks,
                  'server_starts': starts, 'model_kind': 'simulated', 'simulated_model_calls': count(), 'real_model_calls': 0,
                  'test_directory': str(directory), 'schema': 5, 'production_learning_writes': 0,
                  'browser_validation': 'not_performed', 'notes': 'HTTP sockets and real SQLite; provider replaced only by this test executable.'}
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
        print(json.dumps({'passed': True, 'checks': len(checks), 'simulated_calls': count(), 'real_calls': 0, 'report': str(output)}, ensure_ascii=True))
    finally:
        stop()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--serve', type=Path)
    parser.add_argument('--port', type=int)
    parser.add_argument('--no-model', action='store_true')
    parser.add_argument('--output', type=Path, default=Path('data/evaluation/workbench-http-v1.json'))
    args = parser.parse_args()
    if args.serve: serve(args.serve, args.port, args.no_model)
    else: verify(args.output)
