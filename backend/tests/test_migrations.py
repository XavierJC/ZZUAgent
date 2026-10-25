import sqlite3

import pytest

from eduagent.services.learning import LearningService
from eduagent.storage import migrations
from eduagent.storage.sqlite import SQLiteRepository


def legacy_database(path, catalog, version=2):
    with SQLiteRepository(path) as repository:
        service = LearningService(catalog, repository)
        service.register("existing", ("logistic_regression",))
        first = service.next_action("existing")
        service.submit("existing", first.decision_id, "B", "existing-answer")
        for table in reversed(migrations.DOCUMENT_TABLES + migrations.ARCHITECTURE_TABLES + migrations.BANK_TABLES + migrations.EXTRACTION_TABLES + migrations.RELEASE_TABLES + migrations.TEACHER_TABLES + migrations.NOTEBOOK_TABLES):
            repository.connection.execute(f'DROP TABLE {table}')
        for table in ("study_guide_runs", "self_assessment_entries", "self_assessment_batches", "workbench_note_origins", "workbench_runs", "note_chunks", "note_index_state", "note_knowledge_points", "notes"):
            repository.connection.execute(f"DROP TABLE {table}")
        if version == 1:
            repository.connection.execute("DROP TABLE tutor_runs")
        repository.connection.execute(f"PRAGMA user_version={version}")
        return migrations.fact_snapshot(repository.connection)


@pytest.mark.parametrize("version", [1, 2])
def test_migration_backs_up_and_preserves_all_legacy_facts(tmp_path, catalog, version):
    path = tmp_path / "legacy.sqlite3"
    expected = legacy_database(path, catalog, version)
    with SQLiteRepository(path) as repository:
        report = repository.migration_report
        assert report["from_version"] == version and report["to_version"] == 14
        assert report["learning_facts_verified"]
        assert all(migrations.fact_snapshot(repository.connection)[key] == value for key, value in expected.items())
        assert repository.connection.execute("PRAGMA user_version").fetchone()[0] == 14
        assert LearningService(catalog, repository).snapshot("existing").revision == 1
        backup_path = report["backup"]
    with sqlite3.connect(backup_path) as backup:
        assert backup.execute("PRAGMA user_version").fetchone()[0] == version
        assert migrations.fact_snapshot(backup) == expected
        assert backup.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    with SQLiteRepository(path) as reopened:
        assert not reopened.migration_report["changed"] and reopened.migration_report["backup"] is None


def test_ddl_failure_rolls_back_schema_and_retains_backup(tmp_path, catalog, monkeypatch):
    path = tmp_path / "failure.sqlite3"
    before = legacy_database(path, catalog)
    monkeypatch.setattr(migrations, "NOTES", (migrations.NOTES[0], "SYNTHETIC INVALID SQL"))
    with pytest.raises(sqlite3.Error):
        SQLiteRepository(path)
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 2
        assert "notes" not in migrations.table_names(connection)
        assert migrations.fact_snapshot(connection) == before
    assert len(list(tmp_path.glob("failure.before-v2-*.sqlite3"))) == 1


def test_backup_failure_prevents_all_migration_writes(tmp_path, catalog, monkeypatch):
    path = tmp_path / "no-backup.sqlite3"
    before = legacy_database(path, catalog)
    def fail(*args):
        raise OSError("synthetic backup unavailable")
    monkeypatch.setattr(migrations, "backup_database", fail)
    with pytest.raises(OSError):
        SQLiteRepository(path)
    with sqlite3.connect(path) as connection:
        assert migrations.fact_snapshot(connection) == before
        assert "notes" not in migrations.table_names(connection)


@pytest.mark.parametrize("version", [0, 99, 3])
def test_unknown_or_incomplete_database_is_not_silently_reinitialized(tmp_path, version):
    path = tmp_path / "bad.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE untouched (value TEXT)")
        connection.execute(f"PRAGMA user_version={version}")
    with pytest.raises(ValueError):
        SQLiteRepository(path)
    with sqlite3.connect(path) as connection:
        assert migrations.table_names(connection) == {"untouched"}
