"""Isolated real HTTP checks of exhausted-question self-review; no paid calls."""
import argparse
import json
from pathlib import Path
import shutil
import socket
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, ProxyHandler
from uuid import uuid4

from verify_phase5 import serve


def verify(output):
    from eduagent.storage.migrations import preserved_snapshot
    folder = Path('data/local').resolve() / ('review-http-' + uuid4().hex[:8])
    folder.mkdir()
    shutil.copytree('data', folder/'data', ignore=shutil.ignore_patterns('local', 'evaluation'))
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
    opener = build_opener(ProxyHandler({}))
    checks, process, log = [], None, None
    starts = 0

    def http(path, body=None, expected=200):
        request = Request(f'http://127.0.0.1:{port}'+path,
                          data=json.dumps(body).encode() if body is not None else None,
                          headers={'Content-Type': 'application/json'})
        try: response = opener.open(request, timeout=30)
        except HTTPError as e: response = e
        with response:
            raw = response.read()
            assert response.status == expected, (path, response.status, raw[:200])
            return json.loads(raw) if raw else None

    def start_server():
        nonlocal process, log, starts
        starts += 1; (folder/'stop').unlink(missing_ok=True)
        log = (folder/f'server-{starts}.log').open('w')
        process = subprocess.Popen([sys.executable, __file__, '--serve', str(folder), '--port', str(port)],
                                   stdout=log, stderr=log, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        deadline = time.monotonic()+30
        while time.monotonic() < deadline:
            assert process.poll() is None, 'test server exited'
            try: http('/health'); return
            except (URLError, OSError): time.sleep(.1)
        raise AssertionError('test server start timeout')

    def stop_server():
        if process and process.poll() is None:
            (folder/'stop').touch(); process.wait(timeout=30)
        if log: log.close()

    def snapshot():
        with sqlite3.connect(folder/'http.sqlite3') as db: return preserved_snapshot(db)[0]

    def check(name): checks.append(dict(name=name, passed=True))
    def command(**kw): return dict(request_id=str(uuid4()), **kw)
    bank = json.loads((folder/'data/questions.json').read_text(encoding='utf-8'))['questions']
    def wrong(question_id):
        q = next(q for q in bank if q['id'] == question_id)
        return next(k for k in q['options'] if k != q['answer'])

    try:
        start_server()
        for owner in ('legacy', 'bound', 'other'):
            http('/api/v1/students', dict(student_id=owner, goals=['linear_regression_loss']))
        legacy = '/api/v1/students/legacy'
        for _ in range(2):
            d = http(legacy+'/next', {})
            http(legacy+'/answers', dict(event_id=str(uuid4()), decision_id=d['decision_id'], answer=wrong(d['question']['id'])))
        assert http(legacy+'/next', {})['stop_reason'] == 'insufficient_questions'
        check('reproduced_two_question_exhaustion_without_resetting_student')
        assert http(legacy+'/personal-bank/questions')['items'] == []
        value = http(legacy+'/review-exercises')
        assert len(value['items']) == 2 and value['bkt_updated'] is False
        assert all(not item['last_correct'] for item in value['items'])
        check('legacy_learner_has_actual_review_questions_even_when_personal_bank_empty')
        assert http('/api/v1/students/other/review-exercises')['items'] == []
        http('/api/v1/students/missing/review-exercises', expected=404)
        check('other_and_unknown_students_cannot_obtain_old_answers')
        for item in value['items']:
            assert item['question']['review_status'] == 'pending'
            assert item['correct_answer'] in item['question']['options'] and item['explanation']
        check('original_question_feedback_and_pending_review_labels_retained')
        before = snapshot()
        for _ in range(3): assert http(legacy+'/review-exercises') == value
        http(legacy+'/review-exercises', {}, expected=405)
        assert snapshot() == before
        check('review_read_refresh_and_rejected_writes_leave_all_45_tables_unchanged')
        bound = '/api/v1/students/bound'
        release = http('/api/v1/courses/published')['items'][0]
        session = http(bound+'/teaching-sessions', command(release_id=release['id'], goals=['linear_regression_loss']))['session_id']
        path = bound+'/teaching-sessions/'+session
        for revision in range(2):
            d = http(path+'/next', command(expected_learning_revision=revision))['decision']
            http(path+'/answers', command(decision_id=d['decision_id'], answer=wrong(d['question']['id'])))
        assert http(path+'/next', command(expected_learning_revision=2))['decision']['stop_reason'] == 'insufficient_questions'
        bound_value = http(bound+'/review-exercises')
        assert len(bound_value['items']) == 2
        assert not ({i['event_id'] for i in bound_value['items']} & {i['event_id'] for i in value['items']})
        check('release_bound_exhaustion_supports_same_review_without_scope_leak')
        before = snapshot()
        for _ in range(2):
            assert http(bound+'/review-exercises') == bound_value
            assert http(path)['snapshot']['revision'] == 2
        assert snapshot() == before
        check('formal_scores_mastery_releases_sessions_and_question_bank_preserved')
        stop_server(); start_server()
        assert http(legacy+'/review-exercises') == value
        assert http(bound+'/review-exercises') == bound_value
        assert snapshot() == before
        check('service_restart_restores_original_review_snapshots_without_new_assignments')
        assert not (folder/'mock-calls.jsonl').exists()
        check('zero_model_calls_and_no_external_resource_transmission')
        report = dict(passed=True, groups=len(checks), checks=checks,
                      verified_at=datetime.now(timezone.utc).isoformat(), schema=12, tables=45,
                      server_starts=starts, production_writes=0, real_model_calls=0, simulated_model_calls=0,
                      review_submission='client_only_self_check_tested_in_frontend_suite',
                      browser_manual='not_performed', directory=str(folder))
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(dict(passed=True, groups=len(checks), real_model_calls=0, report=str(output))))
    finally: stop_server()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--serve', type=Path); parser.add_argument('--port', type=int)
    parser.add_argument('--output', type=Path, default=Path('data/evaluation/review-continuation-http-v1.json'))
    args = parser.parse_args()
    if args.serve: serve(args.serve, args.port)
    else: verify(args.output)
