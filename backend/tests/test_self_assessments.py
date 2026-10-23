import sqlite3
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from eduagent.api.app import create_app
from eduagent.api.settings import APISettings
from eduagent.domain.notes import NoteConflict, NoteNotFound
from eduagent.services.self_assessments import SelfAssessmentService
from eduagent.services.guidance import GuidanceService
from eduagent.services.learning import LearningService
from eduagent.storage.sqlite import SQLiteRepository
from eduagent.storage import migrations


def body(revision=0, **changes):
    return {'request_id': str(uuid4()), 'expected_revision': revision,
            'items': [dict(knowledge_id='gradient_descent', level=3, confidence=None)], **changes}


def original_snapshot(db):
    return {key: value for key, value in migrations.preserved_snapshot(db)[0].items() if key not in migrations.STUDY_TABLES}


def test_append_replay_conflicts_and_unchanged_learning_facts(service):
    reports = SelfAssessmentService(service)
    before = original_snapshot(service.repository.connection)
    request = body()
    first = reports.save('student-a', **request)
    assert first['committed_revision'] == first['current_revision'] == 1 and not first['replayed']
    assert first['learning_revision_at_save'] == 0 and first['items'][0]['confidence'] is None
    reports.save('student-a', **body(1))
    replay = reports.save('student-a', **request)
    assert replay['committed_revision'] == 1 and replay['current_revision'] == 2 and replay['replayed']
    assert replay['items'] == first['items']
    with pytest.raises(NoteConflict):
        reports.save('student-a', **{**request, 'items': [dict(knowledge_id='gradient_descent', level=1)]})
    with pytest.raises(NoteConflict):
        reports.save('student-a', **body(0))
    assert len(reports.history('student-a')['items']) == 2
    assert reports.latest('student-a')['items'][0]['assessment'] is None
    assert reports.receipt('student-a', request['request_id'])['committed_revision'] == 1
    assert original_snapshot(service.repository.connection) == before


@pytest.mark.parametrize('change', [
    {'level': 0}, {'level': 5}, {'level': True}, {'confidence': 0}, {'confidence': 6}, {'confidence': True},
    {'knowledge_id': 'missing'}, {'probability': 1},
])
def test_invalid_report_is_rejected_without_partial_writes(service, change):
    reports = SelfAssessmentService(service)
    request = body(); request['items'].append({'knowledge_id': 'linear_regression_loss', 'level': 2, 'confidence': 3, **change})
    with pytest.raises(ValueError):
        reports.save('student-a', **request)
    assert reports.latest('student-a')['assessment_revision'] == 0


def test_scope_isolation_and_batch_atomicity(service):
    reports = SelfAssessmentService(service); service.register('student-b')
    request = body(); reports.save('student-a', **request)
    assert reports.history('student-b')['items'] == []
    for action in (lambda: reports.receipt('student-b', request['request_id']), lambda: reports.save('student-b', **request)):
        with pytest.raises(NoteNotFound): action()
    with pytest.raises(ValueError):
        reports.save('student-b', **body(items=[]))


def test_rules_snapshot_never_assigns_and_does_not_diagnose_from_prior(service, monkeypatch):
    monkeypatch.setattr(service, 'next_action', lambda _: pytest.fail('unexpected assignment'))
    before = original_snapshot(service.repository.connection)
    SelfAssessmentService(service).save('student-a', **body())
    snapshot = GuidanceService(service).snapshot('student-a')
    assert snapshot['assessment_revision'] == 1 and snapshot['learning_revision'] == 0
    assert all(not p['objective']['has_evidence'] and p['objective']['probability'] is None for p in snapshot['items'])
    assert snapshot['recommendations'][0]['knowledge_id'] == 'linear_regression_loss'
    gradient = next(p for p in snapshot['items'] if p['knowledge_id'] == 'gradient_descent')
    assert gradient['blocked_by'] == ['linear_regression_loss']
    assert 'reported_ready_needs_check' not in gradient['reason_codes']
    assert original_snapshot(service.repository.connection) == before
    assert GuidanceService(service).snapshot('student-a')['snapshot_hash'] == snapshot['snapshot_hash']


def test_different_evidence_changes_reasons_and_reports_before_attempt_are_marked(service):
    request = body(items=[dict(knowledge_id='linear_regression_loss', level=4, confidence=5)])
    SelfAssessmentService(service).save('student-a', **request)
    decision = service.next_action('student-a')
    service.submit('student-a', decision.decision_id, 'A', str(uuid4()))
    snapshot = GuidanceService(service).snapshot('student-a')
    point = snapshot['recommendations'][0]
    assert point['objective']['attempts'] == 1 and point['objective']['last_correct'] is False
    assert {'recent_error', 'reported_ready_needs_check', 'report_before_latest_attempt'} <= set(point['reason_codes'])
    external = GuidanceService.external_summary(snapshot)
    assert 'student-a' not in str(external) and 'event_id' not in str(external) and 'batch_id' not in str(external)


def test_concurrent_self_reports_use_independent_cas_and_one_commit(service, catalog):
    path = service.repository.connection.execute('PRAGMA database_list').fetchone()[2]
    def save(request):
        with SQLiteRepository(path) as repo:
            try: return SelfAssessmentService(LearningService(catalog, repo)).save('student-a', **request)
            except NoteConflict: return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(save, [body(), body()]))
    assert sum(result is not None for result in results) == 1
    assert SelfAssessmentService(service).latest('student-a')['assessment_revision'] == 1


def test_schema5_backup_failure_and_ddl_rollback_preserve_twelve_tables(tmp_path, catalog, monkeypatch):
    path = tmp_path / 'old.sqlite3'
    with SQLiteRepository(path) as repo:
        LearningService(catalog, repo).register('old')
        for table in reversed(migrations.DOCUMENT_TABLES + migrations.ARCHITECTURE_TABLES + migrations.BANK_TABLES + migrations.EXTRACTION_TABLES + migrations.RELEASE_TABLES): repo.connection.execute('DROP TABLE '+table)
        for table in reversed(migrations.STUDY_TABLES): repo.connection.execute('DROP TABLE '+table)
        repo.connection.execute('PRAGMA user_version=5')
        before, columns = migrations.preserved_snapshot(repo.connection)
    assert len(before) == 12
    backup_function = migrations.backup_database
    def denied(*args): raise OSError('synthetic backup failure')
    monkeypatch.setattr(migrations, 'backup_database', denied)
    with pytest.raises(OSError): SQLiteRepository(path)
    with sqlite3.connect(path) as db:
        assert db.execute('PRAGMA user_version').fetchone()[0] == 5
        assert migrations.preserved_snapshot(db)[0] == before
    monkeypatch.setattr(migrations, 'backup_database', backup_function)
    original = migrations.STUDY
    monkeypatch.setattr(migrations, 'STUDY', (*original[:1], 'INVALID DDL'))
    with pytest.raises(sqlite3.Error): SQLiteRepository(path)
    with sqlite3.connect(path) as db:
        assert db.execute('PRAGMA user_version').fetchone()[0] == 5
        assert migrations.preserved_snapshot(db, columns)[0] == before
    monkeypatch.setattr(migrations, 'STUDY', original)
    with SQLiteRepository(path) as repo:
        report = repo.migration_report
        assert report['from_version'] == 5 and report['to_version'] == 11
        assert migrations.preserved_snapshot(repo.connection, columns)[0] == before
    with sqlite3.connect(report['backup']) as db:
        assert db.execute('PRAGMA user_version').fetchone()[0] == 5
        assert migrations.preserved_snapshot(db)[0] == before


def test_self_api_restore_and_strict_contract_without_any_model(tmp_path, data_dir):
    settings = APISettings(data_dir=data_dir, db_path=tmp_path/'self.sqlite3')
    with TestClient(create_app(settings)) as client:
        client.post('/api/v1/students', json={'student_id': 'a'})
        prefix = '/api/v1/students/a/self-assessments'; request = body()
        assert client.post(prefix, json=request).status_code == 201
        assert client.post(prefix, json=request).status_code == 200
        assert client.get(prefix+'/latest').json()['assessment_revision'] == 1
        assert client.get(prefix+'/requests/'+request['request_id']).json()['replayed']
        assert client.get(prefix+'?knowledge_id=gradient_descent&limit=1').json()['items'][0]['confidence'] is None
        assert client.post(prefix, json={**body(1), 'probability': 1}).status_code == 422
        assert client.post(prefix, content=b'x'*262145).status_code == 413
    with TestClient(create_app(settings)) as client:
        assert client.get(prefix+'/latest').json()['assessment_revision'] == 1
        assert client.get('/api/v1/students/a/mastery').json()['revision'] == 0
