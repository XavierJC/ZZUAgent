"""Isolated real HTTP verification. Explicit no-key settings, synthetic data only.

Starts and gracefully restarts our own subprocess on an ephemeral localhost port.
The paused-build hook exists only in this test server, never in create_app.
Preserves test databases/logs under data/local for inspection.
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
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, ProxyHandler
from uuid import uuid4


def serve(directory, port):
    import uvicorn
    from eduagent.api.app import create_app
    from eduagent.api.settings import APISettings
    from eduagent.services.note_index import NoteIndexer
    from eduagent.retrieval.note_chunks import chunk_markdown

    original = NoteIndexer.__init__
    def configure(self, repository, builder=None):
        def controlled(snapshot):
            pause = directory / ('pause-' + snapshot['id'])
            reached = directory / ('reached-' + snapshot['id'])
            if pause.exists():
                pause.rename(reached)
                deadline = time.monotonic() + 15
                while not (directory / ('release-' + snapshot['id'])).exists():
                    if time.monotonic() > deadline:
                        raise RuntimeError('verification pause timeout')
                    time.sleep(0.03)
            return chunk_markdown(snapshot)
        original(self, repository, builder or controlled)
    NoteIndexer.__init__ = configure
    settings = APISettings(data_dir=Path.cwd() / 'data', db_path=directory / 'http.sqlite3')
    assert settings.agent.enabled is False and settings.agent.api_key == ''
    server = uvicorn.Server(uvicorn.Config(create_app(settings), host='127.0.0.1', port=port, log_level='info', timeout_graceful_shutdown=3))
    def stop():
        # The Windows venv launcher does not reliably forward redirected stdin.
        while not (directory / 'stop-server').exists():
            time.sleep(0.03)
        server.should_exit = True
    threading.Thread(target=stop, daemon=True).start()
    server.run()


def verify(output):
    root = Path.cwd().resolve()
    directory = root / 'data/local' / ('personal-rag-http-' + uuid4().hex[:8])
    directory.mkdir(parents=True)
    assert directory.resolve().is_relative_to(root / 'data/local')
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
    base = f'http://127.0.0.1:{port}'
    process = None
    streams = []
    checks = []
    # All requests target our own loopback test server, never a system proxy.
    opener = build_opener(ProxyHandler({}))
    def passed(name):
        checks.append({'name': name, 'passed': True})
    def request(method, path, body=None, expected=200, timeout=20):
        encoded = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
        req = Request(base + path, data=encoded, method=method,
                      headers={'Content-Type': 'application/json'} if encoded else {})
        try:
            with opener.open(req, timeout=timeout) as response:
                code, raw = response.status, response.read()
        except HTTPError as error:
            code, raw = error.code, error.read()
        result = json.loads(raw) if raw else None
        assert code == expected, (method, path, code, result)
        return result
    def start(number):
        nonlocal process
        (directory / 'stop-server').unlink(missing_ok=True)
        log = (directory / f'server-{number}.log').open('wb')
        streams.append(log)
        process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '--serve', str(directory), '--port', str(port)],
            stdin=subprocess.DEVNULL, stdout=log, stderr=log, cwd=root,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(f'Local verification server exited; inspect {log.name}')
            try:
                health = request('GET', '/health', timeout=1)
                assert not health['agent_enabled'] and health['retrieval_available']
                return
            except (URLError, TimeoutError):
                time.sleep(0.1)
        raise RuntimeError('Verification server startup timeout')
    def stop():
        nonlocal process
        if process and process.poll() is None:
            (directory / 'stop-server').write_text('stop', encoding='utf-8')
            process.wait(timeout=15)
        process = None
    prefix = '/api/v1/students/a'
    def create(text):
        return request('POST', prefix + '/notes', {'id': str(uuid4()), 'title': '合成检索笔记',
            'content_md': text, 'knowledge_point_ids': ['gradient_descent']}, 201)
    def ref(identifier):
        item = next(s for s in request('GET', prefix + '/knowledge/sources')['items'] if s['source_id'] == identifier)
        return {key: item[key] for key in ('source_type', 'source_id', 'source_version')}
    def search(refs, query, expected=200, owner='a'):
        return request('POST', f'/api/v1/students/{owner}/knowledge/search', {'query': query, 'sources': refs, 'top_k': 5}, expected)

    try:
        start(1)
        for student in ('a', 'b'):
            request('POST', '/api/v1/students', {'student_id': student})
        before = request('GET', prefix + '/mastery')
        history = request('GET', prefix + '/history')
        assert request('POST', '/api/v1/materials/search', {'query': '梯度下降'})
        passed('course and personal retrieval enabled with explicit empty model key')
        note = create('# 橙光\n\norangeunique 描述梯度下降。\n\n$$w := w-\\eta g$$')
        selected = ref(note['id'])
        assert search([selected], 'orangeunique')['items'][0]['raw_md'] == note['content_md']
        passed('saved Markdown is locally searchable with source positions and revision')
        other = create('blueunique 只存在于另一篇合成笔记。')
        assert not search([selected], 'blueunique')['items']
        assert not search([ref('gradient')], 'orangeunique')['items']
        mixed = search([selected, ref('gradient')], '梯度下降')
        assert mixed['fusion'] == 'rrf-k60' and all(i['source_id'] in (note['id'], 'gradient') for i in mixed['items'])
        passed('unselected sources excluded for course, notes and combined scopes')
        search([], '梯度下降', 422)
        passed('empty source list is rejected without falling back to all sources')
        search([selected], 'orangeunique', 404, owner='b')
        assert note['id'] not in json.dumps(request('GET', '/api/v1/students/b/knowledge/sources'))
        request('POST', f"/api/v1/students/b/notes/{note['id']}/reindex", {'expected_revision': 1}, 404)
        passed('foreign learner cannot list, retrieve or rebuild private note sources')
        changed = request('PATCH', prefix + f"/notes/{note['id']}", {'expected_revision': 1, 'content_md': '# 紫星\n\npurpleunique 使用新的学习率。'})
        search([selected], 'orangeunique', 409)
        current = ref(note['id'])
        assert not search([current], 'orangeunique')['items']
        assert search([current], 'purpleunique')['items'][0]['source_revision'] == 2
        passed('update invalidates old source version and removes old unique content')
        failed = create('```python\n' + 'x' * 9000 + '\n```')
        assert failed['index_status'] == 'failed'
        failed_ref = ref(failed['id'])
        search([failed_ref], 'python', 503)
        assert request('GET', prefix + f"/notes/{failed['id']}")['content_md'] == failed['content_md']
        assert request('POST', prefix + f"/notes/{failed['id']}/reindex", {'expected_revision': 1})['status'] == 'failed'
        passed('oversized atomic code block fails safely while original Markdown remains saved')
        # Explicit synthetic failure state in this isolated database, not the user's database.
        with sqlite3.connect(directory / 'http.sqlite3') as db:
            db.execute("UPDATE note_index_state SET status='failed',error_code='synthetic_interruption' WHERE note_id=?", (note['id'],))
        search([current], 'purpleunique', 503)
        assert request('POST', prefix + f"/notes/{note['id']}/reindex", {'expected_revision': 2})['status'] == 'ready'
        assert search([current], 'purpleunique')['items']
        passed('injected transient failure can be retried safely through real HTTP')
        race = create('oldraceunique 用于合成版本竞争。')
        race_ref = ref(race['id'])
        (directory / ('pause-' + race['id'])).write_text('pause', encoding='utf-8')
        with ThreadPoolExecutor(max_workers=1) as pool:
            waiting = pool.submit(request, 'POST', prefix + f"/notes/{race['id']}/reindex", {'expected_revision': 1}, 409)
            deadline = time.monotonic() + 10
            while not (directory / ('reached-' + race['id'])).exists():
                assert time.monotonic() < deadline, 'Build hook was not reached'
                time.sleep(0.03)
            search([race_ref], 'oldraceunique', 503)
            request('PATCH', prefix + f"/notes/{race['id']}", {'expected_revision': 1, 'content_md': 'newraceunique 新版本必须获胜。'})
            (directory / ('release-' + race['id'])).write_text('release', encoding='utf-8')
            waiting.result(timeout=20)
        assert search([ref(race['id'])], 'newraceunique')['items'][0]['source_revision'] == 2
        passed('real HTTP delayed rebuild loses to concurrent save; old task cannot publish')
        # Simulate an interrupted build, then stop/start the actual process.
        with sqlite3.connect(directory / 'http.sqlite3') as db:
            db.execute("UPDATE note_index_state SET status='building',build_token='synthetic-dead-process' WHERE note_id=?", (note['id'],))
            db.execute('DELETE FROM note_chunks WHERE note_id=?', (note['id'],))
        stop(); start(2)
        assert search([current], 'purpleunique')['items']
        passed('real process restart restores interrupted index and persisted retrieval')
        request('DELETE', prefix + f"/notes/{note['id']}?expected_revision=2", expected=204)
        search([current], 'purpleunique', 404)
        assert note['id'] not in json.dumps(request('GET', prefix + '/knowledge/sources'))
        passed('soft-deleted notes and their chunks cannot reenter search')
        assert request('GET', prefix + '/mastery') == before
        assert request('GET', prefix + '/history') == history
        assert not request('GET', prefix + '/tutor-runs')
        passed('indexing and retrieval leave BKT, scores, learning history and tutor history unchanged')
        learner = '/api/v1/students/learning-regression'
        request('POST', '/api/v1/students', {'student_id': 'learning-regression', 'goals': ['logistic_regression']})
        for index, answer in enumerate(['B', 'A', 'C', 'D', 'C', 'D']):
            decision = request('POST', learner + '/next')
            payload = {'decision_id': decision['decision_id'], 'event_id': str(uuid4()), 'answer': answer}
            receipt = request('POST', learner + '/answers', payload)
            assert receipt['correct']
            if index == 0:
                assert request('POST', learner + '/answers', payload)['replayed']
        assert request('POST', learner + '/next')['action'] == 'finish'
        assert request('GET', learner + '/mastery')['revision'] == 6
        assert len(request('GET', learner + '/history')['items']) == 6
        wrong = '/api/v1/students/wrong-regression'
        request('POST', '/api/v1/students', {'student_id': 'wrong-regression', 'goals': ['gradient_descent']})
        for answer in ['A', 'B']:
            decision = request('POST', wrong + '/next')
            assert not request('POST', wrong + '/answers', {'decision_id': decision['decision_id'],
                'event_id': str(uuid4()), 'answer': answer})['correct']
        assert request('POST', wrong + '/next')['stop_reason'] == 'insufficient_questions'
        assert len(request('GET', wrong + '/history')['items']) == 2
        passed('original scoring, event replay, six-question finish and wrong-answer pause work in isolated DB')
        with sqlite3.connect(directory / 'http.sqlite3') as db:
            assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
            assert not db.execute('PRAGMA foreign_key_check').fetchall()
        report = dict(date=datetime.now(timezone.utc).isoformat(), phase='v0.5.0 Phase3A', synthetic_data=True,
            isolated_database=str(directory / 'http.sqlite3'), main_database_modified=False,
            model_api_key_present=False, agent_enabled=False, model_requests=0, actual_process_starts=2,
            actual_restart_verified=True, failure_injection='isolated DB states and test-only delayed builder',
            learning_effect_measured=False, checks=checks)
        with Path(output).open('x', encoding='utf-8', newline='\n') as target:
            json.dump(report, target, ensure_ascii=False, indent=2)
            target.write('\n')
        print(json.dumps(report, ensure_ascii=True))
    finally:
        stop()
        for stream in streams:
            stream.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--serve', type=Path)
    parser.add_argument('--port', type=int)
    parser.add_argument('--output', default='data/evaluation/personal-rag-http-v1.json')
    args = parser.parse_args()
    if args.serve:
        serve(args.serve.resolve(), args.port)
    else:
        verify(args.output)
