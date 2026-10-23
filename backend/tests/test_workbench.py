"""Simulated provider only. These tests make zero live model requests."""

import json
import sqlite3
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from eduagent.agent.deepseek import ModelReply, ModelError
from eduagent.agent.settings import AgentSettings
from eduagent.api.app import create_app
from eduagent.api.settings import APISettings
from eduagent.domain.notes import NoteNotFound, NoteConflict
from eduagent.retrieval.index import CourseIndex
from eduagent.services.knowledge import CourseSources, SourceChanged
from eduagent.services.notes import NotesService
from eduagent.services.workbench import WorkbenchService
from eduagent.storage import migrations
from eduagent.storage.sqlite import SQLiteRepository


class FakeModel:
    def __init__(self, tool=None, error=None, mutate=None, invented=False, loop=False):
        self.messages, self.calls = [], 0
        self.tool, self.error, self.mutate, self.invented, self.loop = tool, error, mutate, invented, loop

    def complete(self, messages, tools, required=False):
        self.calls += 1
        self.messages.append(json.loads(json.dumps(messages)))
        if self.error:
            raise ModelError(self.error)
        if self.mutate:
            callback, self.mutate = self.mutate, None
            callback()
        if self.tool and (self.calls == 1 or self.loop):
            name, args = self.tool
            return ModelReply({'role': 'assistant', 'content': None, 'tool_calls': [
                {'id': 'call1', 'type': 'function', 'function': {'name': name, 'arguments': json.dumps(args)}}]}, 5, 5)
        evidence = json.loads(messages[1]['content'])['untrusted_evidence']
        ids = ['invented:999'] if self.invented else [p['citation_id'] for p in evidence]
        return ModelReply({'role': 'assistant', 'content': json.dumps({
            'answer': '解释 $w$。 ' + ' '.join(f'[{key}]' for key in ids), 'citation_ids': ids})}, 7, 4)


@pytest.fixture
def bench(service, data_dir):
    courses = CourseSources(CourseIndex(data_dir / 'materials', set(service.catalog.knowledge)), data_dir / 'materials')
    model = FakeModel()
    result = WorkbenchService(service, courses, settings=AgentSettings(enabled=True, api_key='test-only'), client_factory=lambda: model)
    result.fake = model
    return result


def ref(bench, key):
    source = next(s for s in bench.knowledge.sources('student-a')['items'] if s['source_id'] == key)
    return {field: source[field] for field in ('source_type', 'source_id', 'source_version')}


def note(bench, text='# 梯度下降\n\n沿负梯度方向更新。$w$。 starunique'): 
    return NotesService(bench.learning.catalog, bench.repository).create('student-a', id=str(uuid4()), title='合成测试笔记',
        content_md=text, knowledge_point_ids=['gradient_descent'])[0]


def body(sources, **changes):
    return {'request_id': str(uuid4()), 'question': '梯度下降', 'sources': sources, 'mode': 'model',
            'allow_personal_external': False, 'course_id': 'machine_learning', **changes}


def test_course_only_does_not_read_personal_note_contents(bench, monkeypatch):
    note(bench)
    selected = ref(bench, 'gradient')
    def forbidden(*args, **kwargs):
        raise AssertionError('course-only read personal note')
    monkeypatch.setattr(bench.knowledge.personal, 'note', forbidden)
    run = bench.ask('student-a', body([selected]))
    assert run['status'] == 'complete' and run['model_calls'] == 1
    assert all(c['source_type'] == 'course_material' for c in run['citations'])
    assert 'starunique' not in json.dumps(bench.fake.messages)


@pytest.mark.parametrize('mode,consent,expected', [('model', False, 0), ('local', True, 0), ('model', True, 1)])
def test_personal_consent_is_per_request_and_local_mode_never_calls_model(bench, mode, consent, expected):
    own = note(bench)
    request = body([ref(bench, own['id'])], mode=mode, allow_personal_external=consent)
    result = bench.ask('student-a', request)
    assert bench.fake.calls == expected and result['model_calls'] == expected
    assert result['citations'] and all(c['source_type'] == 'personal_note' for c in result['citations'])
    if expected:
        assert 'starunique' in json.dumps(bench.fake.messages)
    # A different request has no inherited consent.
    bench.ask('student-a', body(request['sources']))
    assert bench.fake.calls == expected


def test_mixed_sources_citations_match_original_snapshots(bench):
    own = note(bench)
    result = bench.ask('student-a', body([ref(bench, 'gradient'), ref(bench, own['id'])], allow_personal_external=True))
    assert {c['source_type'] for c in result['citations']} == {'personal_note', 'course_material'}
    for citation in result['citations']:
        preview = bench.preview('student-a', {k: citation[k] for k in ('source_type', 'source_id', 'source_version')})
        assert preview['raw_md'][citation['start_offset']:citation['end_offset']] == citation['raw_md']


@pytest.mark.parametrize('tool', [
    ('retrieve_selected_sources', {'query': '梯度下降', 'student_id': 'student-b'}),
    ('retrieve_selected_sources', {'query': '梯度下降', 'source_ids': ['unselected']}),
    ('execute_sql', {'sql': 'SELECT * FROM notes'}),
    ('update_bkt', {'probability': 1}),
    ('get_next_exercise', {}),
])
def test_model_cannot_expand_capabilities(bench, tool):
    bench.fake.tool = tool
    before = migrations.fact_snapshot(bench.db)
    result = bench.ask('student-a', body([ref(bench, 'gradient')]))
    assert result['reason'] == 'tool_scope_rejected' and result['model_calls'] == 1
    assert result['tools_used'][0]['status'] == 'rejected'
    assert migrations.fact_snapshot(bench.db) == before


def test_allowed_rewrite_stays_in_original_sources_and_learning_tool_is_readonly(bench):
    own = note(bench)
    bench.fake.tool = ('retrieve_selected_sources', {'query': '梯度下降'})
    result = bench.ask('student-a', body([ref(bench, own['id'])], allow_personal_external=True))
    assert result['status'] == 'complete' and result['model_calls'] == 2
    assert all(c['source_id'] == own['id'] for c in result['citations'])
    bench.fake.calls = 0
    bench.fake.tool = ('get_learning_state', {})
    assert bench.ask('student-a', body([ref(bench, 'gradient')]))['status'] == 'complete'


def test_budget_and_unverified_citations_fall_back(bench):
    bench.fake.tool, bench.fake.loop = ('get_learning_state', {}), True
    run = bench.ask('student-a', body([ref(bench, 'gradient')]))
    assert run['model_calls'] == bench.settings.max_calls and run['reason'] == 'model_call_limit'
    bench.fake.loop, bench.fake.tool, bench.fake.invented = False, None, True
    result = bench.ask('student-a', body([ref(bench, 'gradient')]))
    assert result['reason'] == 'unverified_model_answer' and 'invented' not in result['answer']
    assert result['validation_error'] == 'unknown_citation'


def test_no_rag_match_calls_model_with_empty_evidence_and_replays_without_charge(bench):
    note(bench, '# 未选中笔记\n\nprivate_unselected_secret')
    before = migrations.fact_snapshot(bench.db)
    request = body([ref(bench, 'gradient')], question='hi deepseek')
    run = bench.ask('student-a', request)
    assert run['status'] == 'complete' and run['reason'] is None
    assert run['model_calls'] == 1 and run['answer_basis'] == 'model_knowledge' and run['citations'] == []
    sent = json.loads(bench.fake.messages[0][1]['content'])
    assert sent['question'] == 'hi deepseek' and sent['untrusted_evidence'] == []
    assert set(sent) == {'question', 'untrusted_evidence'}
    assert '没有匹配片段' in bench.fake.messages[0][0]['content']
    assert 'private_unselected_secret' not in json.dumps(bench.fake.messages)
    assert 'mastery' not in json.dumps(bench.fake.messages)
    assert bench.ask('student-a', request)['answer_basis'] == 'model_knowledge'
    assert bench.get('student-a', request['request_id'])['answer_basis'] == 'model_knowledge'
    assert bench.fake.calls == 1 and migrations.fact_snapshot(bench.db) == before
    saved = bench.save_note('student-a', request['request_id'])
    assert '模型自身知识' in NotesService(bench.learning.catalog, bench.repository).get('student-a', saved['note_id'])['content_md']
    assert bench.save_note('student-a', request['request_id'])['note_id'] == saved['note_id']
    assert migrations.fact_snapshot(bench.db) == before


def test_no_evidence_does_not_enable_learning_or_retrieval_tools(bench):
    seen_tools = []
    original = bench.fake.complete
    def complete(messages, tools, required=False):
        seen_tools.append(tools)
        return original(messages, tools, required)
    bench.fake.complete = complete
    bench.fake.tool = ('get_learning_state', {})
    result = bench.ask('student-a', body([ref(bench, 'gradient')], question='hi deepseek'))
    assert result['reason'] == 'tool_scope_rejected' and seen_tools == [[]]
    assert result['model_calls'] == 1 and not result['citations']


def test_no_evidence_still_checks_versions_scope_and_personal_consent(bench):
    own = note(bench)
    selected = ref(bench, own['id'])
    request = body([selected], question='hi deepseek')
    assert bench.ask('student-a', request)['reason'] == 'personal_consent_required'
    assert bench.fake.calls == 0
    accepted = bench.ask('student-a', {**request, 'request_id': str(uuid4()), 'allow_personal_external': True})
    assert accepted['answer_basis'] == 'model_knowledge' and accepted['model_calls'] == 1
    NotesService(bench.learning.catalog, bench.repository).update('student-a', own['id'], 1, {'title': '新版'})
    with pytest.raises(SourceChanged):
        bench.ask('student-a', {**request, 'request_id': str(uuid4())})
    assert bench.fake.calls == 1


def test_fenced_response_and_verified_reference_list_are_accepted_without_retry(bench):
    class Wrapped:
        def complete(self, messages, tools):
            evidence = json.loads(messages[1]['content'])['untrusted_evidence']
            key = evidence[0]['citation_id']
            return ModelReply({'role': 'assistant', 'content': '```json\n' + json.dumps({
                'answer': '模型解释 $w$。', 'citation_ids': [key]}) + '\n```'})
    bench.client_factory = Wrapped
    run = bench.ask('student-a', body([ref(bench, 'gradient')]))
    assert run['status'] == 'complete' and run['model_calls'] == 1
    assert run['answer_basis'] == 'selected_sources' and run['validation_error'] is None
    assert f"[{run['citations'][0]['citation_id']}]" in run['answer']


def test_format_failure_diagnostic_survives_history_without_raw_model_text(bench):
    class Invalid:
        def complete(self, messages, tools):
            return ModelReply({'role': 'assistant', 'content': 'not JSON private upstream text'})
    bench.client_factory = Invalid
    request = body([ref(bench, 'gradient')])
    run = bench.ask('student-a', request)
    assert run['reason'] == 'unverified_model_answer' and run['validation_error'] == 'invalid_json'
    assert run['answer_basis'] == 'local_excerpts'
    assert bench.get('student-a', request['request_id'])['validation_error'] == 'invalid_json'
    assert 'private upstream text' not in bench.db.execute('SELECT result_json FROM workbench_runs').fetchone()[0]


def test_incomplete_second_call_counts_all_reported_usage_and_never_retries(bench):
    class TruncatedAfterTools:
        calls = 0
        def complete(self, messages, tools):
            self.calls += 1
            if self.calls == 1:
                return ModelReply({'role': 'assistant', 'content': None, 'tool_calls': [
                    {'id': 'tool-1', 'type': 'function', 'function': {'name': 'get_learning_state', 'arguments': '{}'}}]}, 20, 10)
            raise ModelError('model_output_truncated', finish_reason='length', prompt_tokens=50, completion_tokens=700)
    model = TruncatedAfterTools()
    bench.client_factory = lambda: model
    before = migrations.fact_snapshot(bench.db)
    request = body([ref(bench, 'gradient')])
    result = bench.ask('student-a', request)
    assert result['status'] == 'local' and result['reason'] == 'model_output_truncated'
    assert result['finish_reason'] == 'length' and result['model_calls'] == 2
    assert result['usage'] == {'prompt_tokens': 70, 'completion_tokens': 710}
    assert result['max_output_tokens'] == 700
    assert bench.ask('student-a', request)['finish_reason'] == 'length'
    assert bench.get('student-a', request['request_id'])['usage'] == result['usage'] and model.calls == 2
    assert migrations.fact_snapshot(bench.db) == before


def test_workbench_route_uses_json_mode_and_chat_budget_without_changing_tutor_settings(tmp_path, data_dir, monkeypatch):
    seen = []
    def complete(self, messages, tools, required=False):
        seen.append((self.json_output, self.settings.max_tokens))
        matches = json.loads(messages[1]['content'])['untrusted_evidence']
        key = matches[0]['citation_id']
        return ModelReply({'role': 'assistant', 'content': json.dumps({'answer': '解释 ['+key+']', 'citation_ids': [key]})})
    monkeypatch.setattr('eduagent.agent.deepseek.DeepSeekClient.complete', complete)
    agent = AgentSettings(enabled=True, api_key='test-only', max_tokens=700, workbench_max_tokens=1500)
    with TestClient(create_app(APISettings(data_dir=data_dir, db_path=tmp_path/'chat.sqlite3', agent=agent))) as client:
        client.post('/api/v1/students', json={'student_id': 'a'})
        cap = client.get('/api/v1/students/a/workbench/capabilities').json()
        assert cap['max_output_tokens'] == 1500 and cap['max_model_calls'] == 3
        source = next(s for s in client.get('/api/v1/students/a/knowledge/sources').json()['items'] if s['source_id'] == 'gradient')
        selected = {k: source[k] for k in ('source_type', 'source_id', 'source_version')}
        result = client.post('/api/v1/students/a/workbench/questions', json=body([selected]))
        assert result.status_code == 200 and result.json()['status'] == 'complete'
        assert result.json()['max_output_tokens'] == 1500 and seen == [(True, 1500)]
        assert agent.max_tokens == 700


def test_old_receipt_is_read_without_reinterpretation_or_model_call(bench):
    run = bench.ask('student-a', body([ref(bench, 'gradient')]))
    raw = json.loads(bench.db.execute('SELECT result_json FROM workbench_runs').fetchone()[0])
    raw.pop('answer_basis', None); raw.pop('validation_error', None)
    bench.db.execute('UPDATE workbench_runs SET result_json=?', (json.dumps(raw),))
    restored = bench.get('student-a', run['request_id'])
    assert restored['answer_basis'] == 'selected_sources' and restored['validation_error'] is None
    assert restored['answer'] == run['answer'] and bench.fake.calls == 1


@pytest.mark.parametrize('error,status', [('model_timeout', 'uncertain'), ('network_error', 'uncertain'),
                                        ('upstream_error', 'uncertain'), ('invalid_model_response', 'uncertain'), ('authentication_failed', 'local')])
def test_model_failures_are_durable_and_never_retried(bench, error, status):
    bench.fake.error = error
    request = body([ref(bench, 'gradient')])
    run = bench.ask('student-a', request)
    assert run['status'] == status and run['reason'] == error
    assert bench.ask('student-a', request)['request_id'] == run['request_id']
    assert bench.get('student-a', run['request_id'])['model_calls'] == 1
    assert len(bench.history('student-a')) == 1 and bench.fake.calls == 1
    with pytest.raises(NoteConflict):
        bench.ask('student-a', {**request, 'question': 'changed'})


def test_note_update_during_generation_marks_stale_and_history_preserves_snapshot(bench):
    own = note(bench)
    selected = ref(bench, own['id'])
    bench.fake.mutate = lambda: NotesService(bench.learning.catalog, bench.repository).update(
        'student-a', own['id'], 1, {'content_md': '完全不同的新原文 moonunique'})
    request = body([selected], allow_personal_external=True)
    run = bench.ask('student-a', request)
    assert run['status'] == 'stale' and run['reason'] == 'context_changed'
    assert run['source_statuses'][0]['current_status'] == 'modified'
    assert run['citations'][0]['raw_md'] == own['content_md']
    with pytest.raises(SourceChanged):
        bench.ask('student-a', body([selected], mode='local'))
    NotesService(bench.learning.catalog, bench.repository).delete('student-a', own['id'], 2)
    history = bench.get('student-a', request['request_id'])
    assert history['source_statuses'][0]['current_status'] == 'deleted'
    assert history['citations'][0]['raw_md'] == own['content_md']
    with pytest.raises(NoteNotFound):
        bench.ask('student-a', body([selected], mode='local'))


def test_cross_student_and_empty_sources_do_not_leak(bench):
    own = note(bench)
    selected = ref(bench, own['id'])
    bench.learning.register('student-b')
    request = body([selected])
    result = bench.ask('student-a', request)
    for action in (lambda: bench.ask('student-b', body([selected])), lambda: bench.get('student-b', result['request_id']),
                   lambda: bench.preview('student-b', selected), lambda: bench.save_note('student-b', result['request_id'])):
        with pytest.raises(NoteNotFound):
            action()
    assert not bench.history('student-b')
    with pytest.raises(ValueError):
        bench.ask('student-a', body([]))
    assert bench.fake.calls == 0


def test_save_note_atomic_idempotent_editable_indexed_and_no_learning_changes(bench):
    before = migrations.fact_snapshot(bench.db)
    run = bench.ask('student-a', body([ref(bench, 'gradient')]))
    saved = bench.save_note('student-a', run['request_id'])
    again = bench.save_note('student-a', run['request_id'])
    assert saved == again and not saved['edited']
    notes = NotesService(bench.learning.catalog, bench.repository)
    original = notes.get('student-a', saved['note_id'])
    assert original['index_status'] == 'ready'
    assert original['generation_origin']['request_id'] == run['request_id'] and not original['generation_origin']['edited']
    edited = notes.update('student-a', saved['note_id'], 1, {'content_md': '# 修改后的理解\n\nmoonunique 梯度下降'})
    replay = bench.save_note('student-a', run['request_id'])
    assert replay['note_id'] == saved['note_id'] and replay['edited'] and replay['revision'] == 2
    assert notes.get('student-a', saved['note_id'])['content_md'] == edited['content_md']
    assert notes.get('student-a', saved['note_id'])['generation_origin']['edited']
    assert bench.knowledge.search('student-a', 'moonunique', [ref(bench, saved['note_id'])])['items']
    assert migrations.fact_snapshot(bench.db) == before
    notes.delete('student-a', saved['note_id'], 2)
    assert bench.save_note('student-a', run['request_id'])['deleted']
    assert notes.list('student-a')['total'] == 0


def test_api_no_key_restart_history_and_strict_fields(tmp_path, data_dir):
    config = APISettings(data_dir=data_dir, db_path=tmp_path / 'bench.sqlite3')
    with TestClient(create_app(config)) as client:
        client.post('/api/v1/students', json={'student_id': 'a'})
        item = client.get('/api/v1/students/a/knowledge/sources').json()['items'][1]
        selected = {k: item[k] for k in ('source_type', 'source_id', 'source_version')}
        request = body([selected], mode='local')
        path = '/api/v1/students/a/workbench'
        run = client.post(path + '/questions', json=request)
        assert run.status_code == 200, run.text
        assert run.json()['model_calls'] == 0
        assert client.post(path + '/sources/open', json=selected).json()['raw_md']
        for change in ({'sources': []}, {'student_id': 'b'}, {'allow_personal_external': 'true'}, {'request_id': 'bad'}):
            assert client.post(path + '/questions', json={**request, **change}).status_code == 422
        assert client.post(path + '/questions', content=b'x' * 262145).status_code == 413
    with TestClient(create_app(config)) as client:
        assert client.get(path + '/runs').json()[0]['request_id'] == request['request_id']
        assert client.post(path + '/questions', json=request).json()['model_calls'] == 0


def test_interrupted_claim_is_uncertain_on_restart_and_not_taken_over(bench):
    request = body([ref(bench, 'gradient')])
    bench.ask('student-a', request)
    bench.db.execute("UPDATE workbench_runs SET status='running',model_calls=1 WHERE request_id=?", (request['request_id'],))
    result = bench.ask('student-a', request)
    assert result['status'] == 'uncertain' and result['reason'] == 'execution_unconfirmed'
    assert bench.fake.calls == 1


def test_schema4_backup_preserves_ten_tables_and_ddl_failure_rolls_back(tmp_path, catalog, monkeypatch):
    path = tmp_path / 'v4.sqlite3'
    with SQLiteRepository(path) as repo:
        from eduagent.services.learning import LearningService
        LearningService(catalog, repo).register('old')
        for table in reversed(migrations.DOCUMENT_TABLES + migrations.ARCHITECTURE_TABLES + migrations.BANK_TABLES + migrations.EXTRACTION_TABLES + migrations.RELEASE_TABLES + migrations.TEACHER_TABLES):
            repo.connection.execute('DROP TABLE '+table)
        for table in ('study_guide_runs', 'self_assessment_entries', 'self_assessment_batches'):
            repo.connection.execute('DROP TABLE '+table)
        repo.connection.execute('DROP TABLE workbench_note_origins')
        repo.connection.execute('DROP TABLE workbench_runs')
        repo.connection.execute('PRAGMA user_version=4')
        before, columns = migrations.preserved_snapshot(repo.connection)
    assert len(before) == 10
    original = migrations.WORKBENCH
    monkeypatch.setattr(migrations, 'WORKBENCH', (*original[:1], 'SYNTHETIC INVALID DDL'))
    with pytest.raises(sqlite3.Error):
        SQLiteRepository(path)
    with sqlite3.connect(path) as db:
        assert db.execute('PRAGMA user_version').fetchone()[0] == 4
        assert migrations.preserved_snapshot(db, columns)[0] == before
    monkeypatch.setattr(migrations, 'WORKBENCH', original)
    with SQLiteRepository(path) as repo:
        report = repo.migration_report
        assert report['from_version'] == 4 and report['to_version'] == 12
        assert migrations.preserved_snapshot(repo.connection, columns)[0] == before
    with sqlite3.connect(report['backup']) as db:
        assert db.execute('PRAGMA user_version').fetchone()[0] == 4
        assert migrations.preserved_snapshot(db)[0] == before
        assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
