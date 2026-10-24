import sqlite3
from uuid import uuid4

import pytest

from eduagent.storage import migrations
from eduagent.storage.sqlite import SQLiteRepository
from eduagent.services.notes import NotesService
from eduagent.services.learning import LearningService


def schema3(path, catalog):
    with SQLiteRepository(path) as repository:
        LearningService(catalog, repository).register('existing')
        NotesService(catalog, repository).create('existing', id=str(uuid4()), title='原笔记', content_md='$w$ 原文', knowledge_point_ids=['gradient_descent'])
        db = repository.connection
        for table in reversed(migrations.DOCUMENT_TABLES + migrations.ARCHITECTURE_TABLES + migrations.BANK_TABLES + migrations.EXTRACTION_TABLES + migrations.RELEASE_TABLES + migrations.TEACHER_TABLES):
            db.execute('DROP TABLE '+table)
        for table in ('study_guide_runs', 'self_assessment_entries', 'self_assessment_batches'):
            db.execute('DROP TABLE '+table)
        db.execute('DROP TABLE workbench_note_origins')
        db.execute('DROP TABLE workbench_runs')
        db.execute('DROP TABLE note_chunks')
        db.execute('DROP TABLE note_index_state')
        db.execute(migrations.NOTES[-1])
        db.execute("INSERT INTO note_index_state(note_id,status,target_revision,chunk_count,updated_at) SELECT id,'disabled',revision,0,updated_at FROM notes")
        db.execute('PRAGMA user_version=3')
        return migrations.preserved_snapshot(db)


def test_schema3_backup_preserves_all_nine_tables(tmp_path, catalog):
    path = tmp_path / 'notes-v3.sqlite3'
    before, columns = schema3(path, catalog)
    assert len(before) == 9
    with SQLiteRepository(path) as repository:
        report = repository.migration_report
        assert report['from_version'] == 3 and report['to_version'] == 13
        assert report['facts'] == before and report['original_tables_verified']
        assert migrations.preserved_snapshot(repository.connection, columns)[0] == before
        assert not repository.connection.execute('PRAGMA foreign_key_check').fetchall()
    with sqlite3.connect(report['backup']) as backup:
        assert backup.execute('PRAGMA user_version').fetchone()[0] == 3
        assert migrations.preserved_snapshot(backup)[0] == before
        assert backup.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'


def test_rebuild_state_ddl_failure_restores_schema3_and_notes(tmp_path, catalog, monkeypatch):
    path = tmp_path / 'failure-v3.sqlite3'
    before, columns = schema3(path, catalog)
    monkeypatch.setattr(migrations, 'PERSONAL_RAG', (*migrations.PERSONAL_RAG[:4], 'INVALID DDL'))
    with pytest.raises(sqlite3.Error):
        SQLiteRepository(path)
    with sqlite3.connect(path) as db:
        assert db.execute('PRAGMA user_version').fetchone()[0] == 3
        assert migrations.preserved_snapshot(db, columns)[0] == before
        assert 'note_index_state_v4' not in migrations.table_names(db)


def test_backup_failure_keeps_schema3_untouched(tmp_path, catalog, monkeypatch):
    path = tmp_path / 'no-backup.sqlite3'
    before, columns = schema3(path, catalog)
    def fail(*args):
        raise OSError('synthetic denied')
    monkeypatch.setattr(migrations, 'backup_database', fail)
    with pytest.raises(OSError):
        SQLiteRepository(path)
    with sqlite3.connect(path) as db:
        assert db.execute('PRAGMA user_version').fetchone()[0] == 3
        assert migrations.preserved_snapshot(db, columns)[0] == before
