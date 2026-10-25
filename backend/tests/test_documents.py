"""Independent document facts, scope, version races and paid request receipts."""

from dataclasses import replace
from hashlib import sha256
import json
import sqlite3
from uuid import uuid4

import pytest

from eduagent.agent.deepseek import ModelReply, ModelError
from eduagent.agent.settings import AgentSettings
from eduagent.documents.models import DocumentError
from eduagent.documents.parsers import parse
from eduagent.services.documents import DocumentsService
from eduagent.services.learning import LearningService
from eduagent.storage.sqlite import SQLiteRepository
from eduagent.storage import migrations
from document_fixtures import pdf_bytes


@pytest.fixture
def documents(tmp_path, catalog):
    with SQLiteRepository(tmp_path / 'docs.sqlite3') as repo:
        learning = LearningService(catalog, repo)
        learning.register('doc-a'); learning.register('doc-b')
        yield DocumentsService(repo, tmp_path / 'files')


def metadata(**changes):
    value = dict(request_id=str(uuid4()), course_id='machine_learning', title='自建资料',
                 material_role='teaching_slides', source_note='合成夹具', local_rights_confirmed=True)
    return {**value, **changes}


def upload(service, raw=b'# title\n\nGradient descent and learning rate.', name='course.md', meta=None, student='doc-a', doc=None):
    key, path = service.files.stage(); path.write_bytes(raw)
    return service.upload(student, meta or metadata(), key, name, len(raw), sha256(raw).hexdigest(), doc)


def local_runner(manifest, output, **kwargs):
    data = json.loads(manifest.read_text(encoding='utf8'))
    from pathlib import Path
    return parse(Path(data['path']), data['kind'])


def tick(service, runner=local_runner, model=None):
    run = service.claim()
    assert run is not None
    service.execute(run, runner, (lambda: model) if model else None)
    return run


def old_facts(service):
    facts = migrations.preserved_snapshot(service.db)[0]
    return {key: value for key, value in facts.items() if key not in migrations.DOCUMENT_TABLES + migrations.ARCHITECTURE_TABLES + migrations.BANK_TABLES}


def test_create_replay_conflict_duplicates_and_owner_scope(documents):
    before = old_facts(documents)
    meta = metadata()
    first, replayed = upload(documents, meta=meta)
    assert not replayed and first['version']['file_revision'] == 1 and first['parse']['status'] == 'pending'
    same, replayed = upload(documents, meta=meta)
    assert replayed and same == first
    with pytest.raises(DocumentError) as conflict:
        upload(documents, raw=b'different', meta=meta)
    assert conflict.value.code == 'request_id_conflict'
    with pytest.raises(DocumentError) as duplicate:
        upload(documents)
    assert duplicate.value.code == 'duplicate_document'
    other, _ = upload(documents, student='doc-b')
    assert other['id'] != first['id']
    assert len(documents.list('doc-b')['items']) == 1
    with pytest.raises(DocumentError) as denied:
        documents.get('doc-b', first['id'])
    assert denied.value.status == 404 and 'doc-a' not in str(denied.value)
    assert old_facts(documents) == before


def test_parse_original_positions_and_readonly_get_recover(documents):
    before = old_facts(documents)
    doc, _ = upload(documents, '# PCA\n\n$$\nx^T x\n$$'.encode())
    run = tick(documents)
    restored = documents.get('doc-a', doc['id'])
    units = documents.units('doc-a', doc['id'])
    assert restored['parse']['status'] == 'ready' and restored['index_status'] == 'empty'
    assert units['items'][0]['text'].startswith('# PCA')
    assert units['items'][0]['location']['start_line'] == 1
    for _ in range(3):
        assert documents.get_run('doc-a', doc['id'], run['id'])['model_calls'] == 0
    path, name = documents.original('doc-a', doc['id'])
    assert name == 'course.md' and path.read_text().startswith('# PCA')
    assert old_facts(documents) == before


def test_version_race_never_publishes_old_run_as_current(documents):
    first, _ = upload(documents)
    old = documents.claim()
    updated, _ = upload(documents, raw=b'# New\n\nnew text', meta=dict(request_id=str(uuid4()), course_id='machine_learning', expected_revision=1), doc=first['id'])
    documents.execute(old, local_runner)
    assert documents.get_run('doc-a', first['id'], old['id'])['status'] == 'superseded'
    assert documents.get('doc-a', first['id'])['parse']['id'] == updated['parse']['id']
    assert documents.units('doc-a', first['id'])['items'] == []
    tick(documents)
    assert documents.units('doc-a', first['id'])['items'][0]['text'].startswith('# New')
    with pytest.raises(DocumentError) as stale:
        documents.mutate('doc-a', first['id'], dict(request_id=str(uuid4()), expected_revision=1, title='old'), 'update')
    assert stale.value.code == 'revision_conflict'


def test_delete_while_parsing_and_late_upload_replay_do_not_resurrect(documents):
    meta = metadata()
    doc, _ = upload(documents, meta=meta)
    old = documents.claim()
    deletion = dict(request_id=str(uuid4()), expected_revision=1)
    value, _ = documents.mutate('doc-a', doc['id'], deletion, 'delete')
    assert value['deleted']
    documents.execute(old, local_runner)
    assert documents.list('doc-a')['items'] == []
    assert upload(documents, meta=meta)[1]
    assert documents.mutate('doc-a', doc['id'], deletion, 'delete')[1]
    assert documents.list('doc-a')['items'] == []
    assert documents.db.execute('SELECT count(*) FROM document_versions').fetchone()[0] == 1
    with pytest.raises(DocumentError): documents.original('doc-a', doc['id'])


def test_failures_keep_original_and_manual_retry_can_succeed(documents):
    doc, _ = upload(documents)
    def failed(*args, **kwargs): raise DocumentError('parse_timeout')
    tick(documents, failed)
    assert documents.get('doc-a', doc['id'])['parse']['error_code'] == 'parse_timeout'
    assert documents.original('doc-a', doc['id'])[0].exists()
    assert documents.claim() is None
    response, _ = documents.mutate('doc-a', doc['id'], dict(request_id=str(uuid4()), expected_revision=1), 'parse')
    assert response['revision'] == 2
    tick(documents)
    assert documents.get('doc-a', doc['id'])['parse']['status'] == 'ready'


def test_restart_recovers_local_once_and_original_tamper_fails(documents):
    doc, _ = upload(documents)
    documents.claim(); documents.recover()
    tick(documents)
    assert documents.get('doc-a', doc['id'])['parse']['status'] == 'ready'
    path, _ = documents.original('doc-a', doc['id']); path.write_bytes(b'local tampering')
    with pytest.raises(DocumentError) as caught: documents.original('doc-a', doc['id'])
    assert caught.value.code == 'original_unavailable'


def test_composite_foreign_key_rejects_cross_owner_version(documents):
    a, _ = upload(documents)
    b, _ = upload(documents, student='doc-b')
    with pytest.raises(sqlite3.IntegrityError):
        with documents.repository.transaction():
            documents.db.execute('UPDATE course_documents SET current_version_id=? WHERE id=?', (a['version']['id'], b['id']))


class VisionModel:
    calls = 0
    def __init__(self, callback=None, failure=None):
        self.callback, self.failure, self.messages = callback, failure, []
    def complete(self, messages, tools):
        self.calls += 1; self.messages.append(messages)
        assert tools == [] and isinstance(messages[1]['content'], list)
        if self.callback: self.callback()
        if self.failure: raise self.failure
        return ModelReply({'role': 'assistant', 'content': json.dumps(dict(transcription_md='PCA公式 $x^T x$',
            interpretation_md='图中箭头表示投影。', warnings=[]))}, 100, 30)


def ready_pdf(service):
    doc, _ = upload(service, pdf_bytes(('PCA page one', 'Second page')), 'course.pdf')
    tick(service)
    return service.get('doc-a', doc['id'])


def vision_body(doc):
    return dict(request_id=str(uuid4()), expected_revision=doc['revision'], version_id=doc['version']['id'], pages=[1], consent_external=True)


def renderer(manifest, output, **kwargs):
    return {'images': [{'page_number': n, 'image_base64': 'synthetic'} for n in json.loads(manifest.read_text())['pages']]}


def enable(service):
    service.vision_enabled = True
    service.agent = AgentSettings(enabled=True, api_key='synthetic-only-key')


def test_vision_requires_server_enable_and_round_consent(documents):
    doc = ready_pdf(documents)
    body = vision_body(doc)
    with pytest.raises(DocumentError) as denied: documents.mutate('doc-a', doc['id'], body, 'vision')
    assert denied.value.code == 'vision_disabled'
    enable(documents)
    with pytest.raises(DocumentError) as denied: documents.mutate('doc-a', doc['id'], {**body, 'consent_external': False}, 'vision')
    assert denied.value.code == 'external_consent_required'
    assert documents.db.execute("SELECT count(*) FROM document_parse_runs WHERE mode='vision'").fetchone()[0] == 0


def test_vision_is_separate_receipted_transcription_no_bkt_write(documents):
    doc = ready_pdf(documents); enable(documents)
    before = old_facts(documents)
    body = vision_body(doc)
    queued, replay = documents.mutate('doc-a', doc['id'], body, 'vision')
    model = VisionModel(); tick(documents, renderer, model)
    value = documents.units('doc-a', doc['id'], queued['id'])
    assert value['run']['status'] == 'partial' and value['run']['model_calls'] == 1
    assert value['items'][0]['origin'] == 'deepseek_vision'
    assert value['items'][0]['interpretation_md'] != value['items'][0]['text']
    assert documents.mutate('doc-a', doc['id'], body, 'vision')[1]
    assert documents.get('doc-a', doc['id'])['parse']['id'] == doc['parse']['id']
    assert documents.claim() is None and model.calls == 1 and old_facts(documents) == before
    assert documents.get_run('doc-a', doc['id'], queued['id'])['usage'] == {'prompt_tokens': 100, 'completion_tokens': 30}


def test_vision_timeout_and_restart_never_reissue_paid_request(documents):
    doc = ready_pdf(documents); enable(documents)
    queued, _ = documents.mutate('doc-a', doc['id'], vision_body(doc), 'vision')
    model = VisionModel(failure=ModelError('model_timeout'))
    tick(documents, renderer, model); documents.recover()
    assert documents.get_run('doc-a', doc['id'], queued['id'])['status'] == 'uncertain'
    assert documents.claim() is None and model.calls == 1


def test_source_changes_during_vision_leave_only_labeled_historical_result(documents):
    doc = ready_pdf(documents); enable(documents)
    queued, _ = documents.mutate('doc-a', doc['id'], vision_body(doc), 'vision')
    def modify(): documents.mutate('doc-a', doc['id'], dict(request_id=str(uuid4()), expected_revision=doc['revision'], title='新版标题'), 'update')
    tick(documents, renderer, VisionModel(callback=modify))
    run = documents.get_run('doc-a', doc['id'], queued['id'])
    assert run['status'] == 'superseded' and run['current_status'] == 'modified'
    assert documents.units('doc-a', doc['id'], queued['id'])['items'][0]['text']


def test_schema6_explicit_upgrade_and_backup_preserve_all_fifteen_tables(tmp_path, catalog, monkeypatch):
    path = tmp_path / 'v6.sqlite3'
    with SQLiteRepository(path) as repo:
        LearningService(catalog, repo).register('old')
        for table in reversed(migrations.DOCUMENT_TABLES + migrations.ARCHITECTURE_TABLES + migrations.BANK_TABLES + migrations.EXTRACTION_TABLES + migrations.RELEASE_TABLES + migrations.TEACHER_TABLES + migrations.NOTEBOOK_TABLES): repo.connection.execute('DROP TABLE '+table)
        repo.connection.execute('PRAGMA user_version=6')
        before, columns = migrations.preserved_snapshot(repo.connection)
    assert len(before) == 15
    with pytest.raises(ValueError, match='显式迁移'): SQLiteRepository(path, allow_upgrade=False)
    original = migrations.DOCUMENTS
    monkeypatch.setattr(migrations, 'DOCUMENTS', (*original[:1], 'INVALID DDL'))
    with pytest.raises(sqlite3.Error): SQLiteRepository(path)
    with sqlite3.connect(path) as db:
        assert db.execute('PRAGMA user_version').fetchone()[0] == 6
        assert migrations.preserved_snapshot(db)[0] == before
    monkeypatch.setattr(migrations, 'DOCUMENTS', original)
    with SQLiteRepository(path) as repo:
        report = repo.migration_report
        assert report['to_version'] == 14 and migrations.preserved_snapshot(repo.connection, columns)[0] == before
        assert repo.connection.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        assert not repo.connection.execute('PRAGMA foreign_key_check').fetchall()
    with sqlite3.connect(report['backup']) as backup:
        assert migrations.preserved_snapshot(backup)[0] == before


def test_failed_upload_and_publish_remove_only_their_rolled_back_files(documents, monkeypatch):
    with pytest.raises(DocumentError): upload(documents, b'not pdf', 'invalid.pdf')
    assert not list(documents.files.root.glob('staging/*.bin'))
    insert = documents.storage.insert
    def fail_version(table, row):
        if table == 'document_versions': raise OSError('synthetic disk failure')
        return insert(table, row)
    monkeypatch.setattr(documents.storage, 'insert', fail_version)
    with pytest.raises(DocumentError): upload(documents)
    assert not list(documents.files.root.glob('originals/*/*.bin'))
    monkeypatch.setattr(documents.storage, 'insert', insert)
    doc, _ = upload(documents)
    def fail_unit(table, row):
        if table == 'document_units': raise sqlite3.IntegrityError('synthetic rollback')
        return insert(table, row)
    monkeypatch.setattr(documents.storage, 'insert', fail_unit)
    tick(documents)
    assert documents.get('doc-a', doc['id'])['parse']['status'] == 'failed'
    assert documents.original('doc-a', doc['id'])[0].is_file()
    assert not list(documents.files.root.glob('derived/*/*.json'))


def test_vision_duplicate_fields_fail_without_losing_usage(documents):
    doc = ready_pdf(documents); enable(documents)
    queued, _ = documents.mutate('doc-a', doc['id'], vision_body(doc), 'vision')
    class InvalidModel:
        def complete(self, *args):
            return ModelReply({'content': '{"transcription_md":"a","transcription_md":"b","interpretation_md":"","warnings":[]}'}, 10, 20)
    tick(documents, renderer, InvalidModel())
    run = documents.get_run('doc-a', doc['id'], queued['id'])
    assert run['error_code'] == 'invalid_vision_output' and run['usage']['completion_tokens'] == 20
    assert documents.units('doc-a', doc['id'], queued['id'])['items'] == []


def test_restart_detects_missing_derived_and_changed_original(documents):
    doc, _ = upload(documents); run=tick(documents)
    artifact=documents.db.execute('SELECT artifact_key FROM document_parse_runs WHERE id=?',(run['id'],)).fetchone()[0]
    documents.files.path(artifact).unlink()
    documents.recover()
    assert documents.get('doc-a',doc['id'])['parse']['error_code']=='derived_unavailable'
    assert documents.units('doc-a',doc['id'])['items']==[]
    documents.mutate('doc-a',doc['id'],dict(request_id=str(uuid4()),expected_revision=1),'parse'); tick(documents)
    assert documents.get('doc-a',doc['id'])['parse']['status']=='ready'
    documents.original('doc-a',doc['id'])[0].write_bytes(b'changed')
    documents.recover()
    assert documents.get('doc-a',doc['id'])['parse']['error_code']=='original_unavailable'
    assert documents.units('doc-a',doc['id'])['items']==[]


def test_retained_original_quota_includes_soft_deleted_files(documents, monkeypatch):
    import eduagent.services.documents as module
    monkeypatch.setattr(module,'MAX_STORED_BYTES',64)
    doc,_=upload(documents,b'x'*50)
    documents.mutate('doc-a',doc['id'],dict(request_id=str(uuid4()),expected_revision=1),'delete')
    with pytest.raises(DocumentError) as caught: upload(documents,b'y'*20)
    assert caught.value.status==413 and documents.list('doc-a')['items']==[]
