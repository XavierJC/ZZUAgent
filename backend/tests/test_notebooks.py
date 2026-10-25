"""Notebook behavior, scoped simulated providers, and additive migration tests."""
import json
import sqlite3
from uuid import uuid4
import pytest
from eduagent.services.study_workspace.notebooks import NotebookService
from eduagent.services.personal_bank import PersonalBankService
from eduagent.services.notes import NotesService
from eduagent.services.knowledge import SourceChanged
from eduagent.domain.notes import NoteConflict, NoteNotFound
from eduagent.storage import migrations
from eduagent.storage.notebook_schema import NOTEBOOK_TABLES
from test_workbench import bench, ref, body, note
from test_personal_bank import payload

def uid(): return str(uuid4())
def command(**kw): return dict(request_id=uid(), **kw)

@pytest.fixture
def books(bench, data_dir):
    bench.learning.register('student-b')
    bank = PersonalBankService(bench.learning, data_dir / 'materials')
    service = NotebookService(bench.learning, bench, bank)
    service.fake = bench.fake
    return service

def create(books, student='student-a', **kw):
    key = uid()
    books.create(student, command(id=key, title='合成笔记本', description='', **kw))
    return key

def link(books, key, refs, student='student-a'):
    row = books.get(student, key)
    books.set_sources(student, key, command(expected_revision=row['revision'], sources=refs))
    return books.get(student, key)

def ask(books, key, refs, **kw):
    return dict(body(refs, **kw), expected_revision=books.get('student-a', key)['revision'])

def test_create_edit_archive_and_idempotence(books):
    key = uid(); request = command(id=key, title='微积分资料', description='我的章节资料')
    result = books.create('student-a', request)
    assert books.create('student-a', request)['replayed']
    with pytest.raises(NoteConflict): books.create('student-a', dict(request, title='different'))
    edit = command(id=key, title='梯度下降', description='', expected_revision=1, archived=True)
    assert books.update('student-a', key, edit)['revision'] == 2
    assert books.list('student-a')['items'] == []
    assert len(books.list('student-a', True)['items']) == 1
    assert books.receipt('student-a', request['request_id'])['id'] == key
    with pytest.raises(NoteNotFound): books.get('student-b', key)
    with pytest.raises(NoteNotFound): books.receipt('student-b', request['request_id'])
    assert books.get('student-a', key)['archived'] == 1
    with pytest.raises(NoteConflict): books.set_sources('student-a', key, command(expected_revision=2, sources=[]))

def test_source_membership_conflicts_and_empty_do_not_expand(books):
    key = create(books); selected = ref(books.workbench, 'gradient')
    foreign = ref(books.workbench, 'linear')
    row = link(books, key, [selected])
    with pytest.raises(NoteConflict): books.ask('student-a', key, ask(books, key, [foreign]))
    with pytest.raises(ValueError): books.ask('student-a', key, ask(books, key, []))
    with pytest.raises(NoteConflict): books.set_sources('student-a', key, command(expected_revision=1, sources=[]))
    with pytest.raises(ValueError): books.set_sources('student-a', key, command(expected_revision=2, sources=[selected, selected]))
    assert books.get('student-a', key)['revision'] == row['revision']
    assert books.fake.calls == 0

def test_chat_history_is_per_notebook_and_replay_never_calls_provider(books):
    key, other = create(books), create(books)
    selected = ref(books.workbench, 'gradient'); link(books, key, [selected]); link(books, other, [selected])
    request = ask(books, key, [selected]); run = books.ask('student-a', key, request)
    assert run['status'] == 'complete' and books.fake.calls == 1
    assert books.ask('student-a', key, request)['answer'] == run['answer']
    assert books.fake.calls == 1 and books.history('student-a', other) == []
    with pytest.raises(NoteNotFound): books.run('student-a', other, request['request_id'])
    with pytest.raises(NoteConflict): books.ask('student-a', other, dict(request, expected_revision=2))
    with pytest.raises(NoteConflict): books.ask('student-a', key, dict(request, question='different'))
    link(books, key, [])
    assert books.run('student-a', key, request['request_id'])['notebook_context_stale']
    assert books.ask('student-a', key, request)['status'] == 'stale'
    assert books.fake.calls == 1

def test_private_note_needs_its_own_turn_permission_and_never_reads_other_student(books):
    own = note(books.workbench)
    selected = ref(books.workbench, own['id']); key = create(books)
    link(books, key, [selected])
    run = books.ask('student-a', key, ask(books, key, [selected]))
    assert run['model_calls'] == 0 and books.fake.calls == 0
    assert run['reason'] == 'personal_consent_required'
    other = create(books, 'student-b')
    with pytest.raises(NoteNotFound): link(books, other, [selected], 'student-b')
    assert books.get('student-b', other)['sources'] == []

def test_source_update_invalidates_current_but_keeps_history(books):
    own = note(books.workbench); selected = ref(books.workbench, own['id']); key = create(books)
    link(books, key, [selected])
    request = ask(books, key, [selected], mode='local')
    run = books.ask('student-a', key, request)
    notes = NotesService(books.learning.catalog, books.repository)
    notes.update('student-a', own['id'], 1, dict(title='新版', content_md='新的解释与之前不同。', knowledge_point_ids=[]))
    assert books.get('student-a', key)['sources'][0]['current_status'] == 'modified'
    with pytest.raises(SourceChanged): books.ask('student-a', key, ask(books, key, [selected]))
    assert books.run('student-a', key, request['request_id'])['citations'] == run['citations']

def test_reservation_after_interruption_is_not_reexecuted(books, monkeypatch):
    key = create(books); selected = ref(books.workbench, 'gradient'); link(books, key, [selected])
    request = ask(books, key, [selected])
    def interrupted(*args): raise RuntimeError('synthetic interruption')
    monkeypatch.setattr(books.workbench, 'ask', interrupted)
    with pytest.raises(RuntimeError): books.ask('student-a', key, request)
    restored = books.ask('student-a', key, request)
    assert restored['status'] == 'uncertain' and restored['reason'] == 'execution_unconfirmed'
    assert books.fake.calls == 0

def test_notebook_change_during_model_is_stale_and_no_fact_writes(books):
    key = create(books); selected = ref(books.workbench, 'gradient'); link(books, key, [selected])
    before = migrations.fact_snapshot(books.db)
    books.fake.mutate = lambda: link(books, key, [])
    run = books.ask('student-a', key, ask(books, key, [selected]))
    assert run['notebook_context_stale'] and run['status'] in ('stale', 'uncertain')
    assert migrations.fact_snapshot(books.db) == before

def test_saved_answer_attaches_once_and_archived_notebook_cannot_write_notes(books):
    key = create(books); selected = ref(books.workbench, 'gradient'); link(books, key, [selected])
    run = books.ask('student-a', key, ask(books, key, [selected], mode='local'))
    result = books.save_answer('student-a', key, run['request_id'])
    assert books.save_answer('student-a', key, run['request_id'])['note_id'] == result['note_id']
    assert len([s for s in books.get('student-a', key)['sources'] if s['source_type'] == 'personal_note']) == 1
    request = ask(books, key, [selected], mode='local'); run2 = books.ask('student-a', key, request)
    row = books.get('student-a', key)
    books.update('student-a', key, command(id=key, title=row['title'], description='', archived=True, expected_revision=row['revision']))
    count = books.db.execute('SELECT count(*) FROM notes').fetchone()[0]
    with pytest.raises(NoteConflict): books.save_answer('student-a', key, run2['request_id'])
    assert books.db.execute('SELECT count(*) FROM notes').fetchone()[0] == count

def test_scoped_practice_does_not_adopt_foreign_session_or_change_bkt(books):
    key, other = create(books), create(books)
    q = books.bank.save('student-a', command(payload=payload(), status='practice', reviewed=True, confirm_answer=True))['question_id']
    link(books, key, [dict(source_type='personal_question', source_id=q, source_version='r1')])
    before = migrations.fact_snapshot(books.db)
    request = command(question_id=q, expected_revision=2)
    sid = books.start_practice('student-a', key, request)['session_id']
    assert books.start_practice('student-a', key, request)['session_id'] == sid
    with pytest.raises(NoteNotFound): books.practice_session('student-a', other, sid)
    with pytest.raises(NoteConflict): books.start_practice('student-a', other, command(question_id=q, expected_revision=1))
    result = books.submit_practice('student-a', key, sid, command(selected_answer='A'))
    assert result['result']['correct'] and not result['result']['bkt_updated']
    assert len(books.practice_history('student-a', key)['items']) == 1
    assert books.practice_history('student-a', other)['items'] == []
    assert migrations.fact_snapshot(books.db) == before

def test_additive_migration_from_realistic_v13_preserves_all_old_tables(service, tmp_path):
    path = tmp_path / 'migration.sqlite3'
    db = sqlite3.connect(path, isolation_level=None)
    service.repository.connection.backup(db)
    db.execute('PRAGMA foreign_keys=OFF')
    for name in reversed(NOTEBOOK_TABLES): db.execute('DROP TABLE ' + name)
    db.execute('PRAGMA user_version=13'); db.execute('PRAGMA foreign_keys=ON')
    before, columns = migrations.preserved_snapshot(db)
    assert len(before) == 45
    result = migrations.migrate(db, path)
    assert result['from_version'] == 13 and result['to_version'] == 14 and result['backup']
    assert migrations.preserved_snapshot(db, columns)[0] == before
    assert len(migrations.preserved_snapshot(db)[0]) == 50
    assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    assert not db.execute('PRAGMA foreign_key_check').fetchall()
    db.close()
