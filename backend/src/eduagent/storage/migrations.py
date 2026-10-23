"""Versioned, backed-up SQLite initialization. Never rewrite learning facts."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from uuid import uuid4
from eduagent.storage.document_schema import DOCUMENTS, DOCUMENT_TABLES
from eduagent.storage.architecture_schema import ARCHITECTURES, ARCHITECTURE_TABLES
from eduagent.storage.personal_bank_schema import BANK, BANK_TABLES

from eduagent.storage.extraction_schema import EXTRACTION, EXTRACTION_TABLES

from eduagent.storage.course_release_schema import RELEASES, RELEASE_TABLES
from eduagent.storage.teaching_source_schema import TEACHER, TEACHER_TABLES

SCHEMA_VERSION = 12
FACT_TABLES = ("metadata", "students", "mastery", "decisions", "attempts", "tutor_runs")
NOTE_TABLES = ("notes", "note_knowledge_points", "note_index_state")
WORKBENCH_TABLES = ('workbench_runs', 'workbench_note_origins')
STUDY_TABLES = ('self_assessment_batches', 'self_assessment_entries', 'study_guide_runs')
STUDY = (
    """CREATE TABLE self_assessment_batches (
       request_id TEXT PRIMARY KEY, student_id TEXT NOT NULL REFERENCES students(id),
       course_id TEXT NOT NULL CHECK(course_id='machine_learning'),
       assessment_revision INTEGER NOT NULL CHECK(assessment_revision>=1),
       expected_revision INTEGER NOT NULL CHECK(expected_revision>=0),
       request_hash TEXT NOT NULL, payload_json TEXT NOT NULL,
       learning_revision_at_save INTEGER NOT NULL CHECK(learning_revision_at_save>=0), created_at TEXT NOT NULL,
       UNIQUE(student_id,course_id,assessment_revision), UNIQUE(request_id,student_id,course_id))""",
    """CREATE TABLE self_assessment_entries (
       id TEXT PRIMARY KEY, batch_id TEXT NOT NULL, student_id TEXT NOT NULL, course_id TEXT NOT NULL,
       knowledge_id TEXT NOT NULL, level INTEGER NOT NULL CHECK(level BETWEEN 1 AND 4),
       confidence INTEGER CHECK(confidence IS NULL OR confidence BETWEEN 1 AND 5),
       FOREIGN KEY(batch_id,student_id,course_id) REFERENCES self_assessment_batches(request_id,student_id,course_id),
       UNIQUE(batch_id,knowledge_id))""",
    'CREATE INDEX self_assessments_by_scope ON self_assessment_entries(student_id,course_id,knowledge_id,batch_id)',
    """CREATE TABLE study_guide_runs (
       request_id TEXT PRIMARY KEY, student_id TEXT NOT NULL REFERENCES students(id),
       course_id TEXT NOT NULL CHECK(course_id='machine_learning'), request_hash TEXT NOT NULL, request_json TEXT NOT NULL,
       learning_revision INTEGER NOT NULL, assessment_revision INTEGER NOT NULL,
       context_json TEXT NOT NULL, snapshot_json TEXT NOT NULL, recommendations_json TEXT NOT NULL,
       result_json TEXT NOT NULL,
       status TEXT NOT NULL CHECK(status IN ('running','complete','local','uncertain','stale','failed')),
       model_calls INTEGER NOT NULL DEFAULT 0 CHECK(model_calls>=0), created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""",
    'CREATE INDEX study_guides_by_student ON study_guide_runs(student_id,course_id,created_at,request_id)',
)
WORKBENCH = (
    """CREATE TABLE workbench_runs (
       request_id TEXT PRIMARY KEY, student_id TEXT NOT NULL REFERENCES students(id),
       course_id TEXT NOT NULL CHECK(course_id='machine_learning'), request_hash TEXT NOT NULL,
       request_json TEXT NOT NULL, context_json TEXT NOT NULL, result_json TEXT NOT NULL,
       status TEXT NOT NULL CHECK(status IN ('running','complete','local','uncertain','stale','failed')),
       model_calls INTEGER NOT NULL DEFAULT 0 CHECK(model_calls>=0),
       created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""",
    'CREATE INDEX workbench_by_student ON workbench_runs(student_id,course_id,created_at,request_id)',
    """CREATE TABLE workbench_note_origins (
       request_id TEXT PRIMARY KEY REFERENCES workbench_runs(request_id),
       note_id TEXT NOT NULL UNIQUE REFERENCES notes(id), original_revision INTEGER NOT NULL CHECK(original_revision=1),
       original_hash TEXT NOT NULL, generated_at TEXT NOT NULL, saved_at TEXT NOT NULL,
       citations_json TEXT NOT NULL)""",
)
BASE = (
    "CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)",
    """CREATE TABLE students (id TEXT PRIMARY KEY, goals_json TEXT NOT NULL,
       revision INTEGER NOT NULL DEFAULT 0 CHECK(revision>=0), created_at TEXT NOT NULL)""",
    """CREATE TABLE mastery (student_id TEXT NOT NULL REFERENCES students(id), knowledge_id TEXT NOT NULL,
       probability REAL NOT NULL CHECK(probability BETWEEN 0 AND 1), attempts INTEGER NOT NULL CHECK(attempts>0),
       last_correct INTEGER NOT NULL CHECK(last_correct IN (0,1)), PRIMARY KEY(student_id,knowledge_id))""",
    """CREATE TABLE decisions (id TEXT PRIMARY KEY, student_id TEXT NOT NULL REFERENCES students(id),
       revision INTEGER NOT NULL, payload_json TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(student_id,revision))""",
    """CREATE TABLE attempts (event_id TEXT PRIMARY KEY, student_id TEXT NOT NULL REFERENCES students(id),
       decision_id TEXT NOT NULL UNIQUE REFERENCES decisions(id), question_id TEXT NOT NULL, knowledge_id TEXT NOT NULL,
       selected_answer TEXT NOT NULL, correct INTEGER NOT NULL CHECK(correct IN (0,1)), prior REAL NOT NULL,
       posterior REAL NOT NULL, next_mastery REAL NOT NULL, result_json TEXT NOT NULL, created_at TEXT NOT NULL)""",
    "CREATE INDEX attempts_by_student ON attempts(student_id)",
)
TUTOR = """CREATE TABLE tutor_runs (id TEXT PRIMARY KEY, student_id TEXT NOT NULL REFERENCES students(id),
           state_revision INTEGER NOT NULL, mode TEXT NOT NULL, payload_json TEXT NOT NULL, created_at TEXT NOT NULL)"""
NOTES = (
    """CREATE TABLE notes (
       id TEXT PRIMARY KEY, student_id TEXT NOT NULL REFERENCES students(id),
       course_id TEXT NOT NULL CHECK(course_id='machine_learning'),
       title TEXT NOT NULL CHECK(length(title) BETWEEN 1 AND 120),
       content_md TEXT NOT NULL CHECK(length(CAST(content_md AS BLOB))<=65536),
       revision INTEGER NOT NULL CHECK(revision>=1), content_hash TEXT NOT NULL,
       created_via TEXT NOT NULL CHECK(created_via IN ('manual','import')),
       created_at TEXT NOT NULL, updated_at TEXT NOT NULL, deleted_at TEXT)""",
    "CREATE INDEX notes_by_student ON notes(student_id,course_id,deleted_at,updated_at,id)",
    """CREATE TABLE note_knowledge_points (note_id TEXT NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
       knowledge_point_id TEXT NOT NULL, PRIMARY KEY(note_id,knowledge_point_id))""",
    "CREATE INDEX notes_by_knowledge ON note_knowledge_points(knowledge_point_id,note_id)",
    # Metadata reservation only. No vector, chunk, indexing job or retrieval in Phase 2.
    """CREATE TABLE note_index_state (note_id TEXT PRIMARY KEY REFERENCES notes(id) ON DELETE CASCADE,
       status TEXT NOT NULL CHECK(status='disabled'), target_revision INTEGER NOT NULL CHECK(target_revision>=1),
       indexed_revision INTEGER, indexed_hash TEXT, indexer_version TEXT, error_code TEXT,
       chunk_count INTEGER NOT NULL DEFAULT 0 CHECK(chunk_count=0), updated_at TEXT NOT NULL)""",
)

# Rebuild only derived-state metadata to widen its CHECK constraints. Copy every
# old column verbatim; original notes, links and all learning tables stay intact.
PERSONAL_RAG = (
    """CREATE TABLE note_index_state_v4 (note_id TEXT PRIMARY KEY REFERENCES notes(id) ON DELETE CASCADE,
       status TEXT NOT NULL CHECK(status IN ('disabled','pending','building','ready','empty','failed')),
       target_revision INTEGER NOT NULL CHECK(target_revision>=1), indexed_revision INTEGER,
       indexed_hash TEXT, indexer_version TEXT, error_code TEXT,
       chunk_count INTEGER NOT NULL DEFAULT 0 CHECK(chunk_count>=0), updated_at TEXT NOT NULL,
       build_token TEXT, building_started_at TEXT)""",
    """INSERT INTO note_index_state_v4(note_id,status,target_revision,indexed_revision,indexed_hash,
       indexer_version,error_code,chunk_count,updated_at)
       SELECT note_id,status,target_revision,indexed_revision,indexed_hash,indexer_version,error_code,chunk_count,updated_at
       FROM note_index_state""",
    "DROP TABLE note_index_state",
    "ALTER TABLE note_index_state_v4 RENAME TO note_index_state",
    """CREATE TABLE note_chunks (chunk_id TEXT PRIMARY KEY, note_id TEXT NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
       student_id TEXT NOT NULL REFERENCES students(id), course_id TEXT NOT NULL CHECK(course_id='machine_learning'),
       revision INTEGER NOT NULL CHECK(revision>=1), content_hash TEXT NOT NULL, ordinal INTEGER NOT NULL CHECK(ordinal>=0),
       title TEXT NOT NULL, section TEXT NOT NULL, start_offset INTEGER NOT NULL CHECK(start_offset>=0),
       end_offset INTEGER NOT NULL CHECK(end_offset>start_offset), start_line INTEGER NOT NULL CHECK(start_line>=1),
       end_line INTEGER NOT NULL CHECK(end_line>=start_line), raw_md TEXT NOT NULL, content_text TEXT NOT NULL,
       chunk_hash TEXT NOT NULL, indexer_version TEXT NOT NULL, UNIQUE(note_id,revision,ordinal))""",
    "CREATE INDEX chunks_by_scope ON note_chunks(student_id,course_id,note_id,revision)",
)


def table_names(connection: sqlite3.Connection) -> set[str]:
    return {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def fact_snapshot(connection: sqlite3.Connection) -> dict:
    """Only fixed table names enter SQL; report hashes, never personal row content."""
    existing = table_names(connection)
    result = {}
    for name in FACT_TABLES:
        if name in existing:
            rows = [json.dumps(tuple(row), ensure_ascii=False, allow_nan=False) for row in connection.execute(f'SELECT * FROM "{name}"')]
            raw = json.dumps(sorted(rows), ensure_ascii=False).encode("utf-8")
            result[name] = {"rows": len(rows), "sha256": sha256(raw).hexdigest()}
    return result


def preserved_snapshot(connection: sqlite3.Connection, columns: dict | None = None) -> tuple[dict, dict]:
    """Compare all existing project tables, using their pre-migration columns."""
    if columns is None:
        names = table_names(connection)
        columns = {name: [row[1] for row in connection.execute(f'PRAGMA table_info("{name}")')]
                   for name in FACT_TABLES + NOTE_TABLES + ('note_chunks',) + WORKBENCH_TABLES + STUDY_TABLES + DOCUMENT_TABLES + ARCHITECTURE_TABLES + BANK_TABLES + EXTRACTION_TABLES + RELEASE_TABLES + TEACHER_TABLES if name in names}
    result = {}
    for name, fields in columns.items():
        projection = ','.join('"' + field.replace('"', '""') + '"' for field in fields)
        rows = [json.dumps(tuple(row), ensure_ascii=False, allow_nan=False)
                for row in connection.execute(f'SELECT {projection} FROM "{name}"')]
        result[name] = {'rows': len(rows), 'sha256': sha256(json.dumps(sorted(rows), ensure_ascii=False).encode()).hexdigest()}
    return result, columns


def backup_database(connection: sqlite3.Connection, path: str | Path, version: int) -> Path | None:
    if str(path) == ":memory:":
        return None
    source = Path(path).resolve()
    target = source.with_name(f"{source.stem}.before-v{version}-{uuid4().hex[:12]}.sqlite3")
    with target.open("xb"):
        pass
    backup = sqlite3.connect(target)
    try:
        connection.backup(backup)
        if backup.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("迁移备份完整性检查失败，原数据库尚未迁移")
    finally:
        backup.close()
    return target


def migrate(connection: sqlite3.Connection, path: str | Path) -> dict:
    version = connection.execute("PRAGMA user_version").fetchone()[0]
    if version not in range(13):
        raise ValueError(f"不支持的数据库版本: {version}")
    tables = table_names(connection)
    if version == 12:
        if not set(FACT_TABLES + NOTE_TABLES + ('note_chunks',) + WORKBENCH_TABLES + STUDY_TABLES + DOCUMENT_TABLES + ARCHITECTURE_TABLES + BANK_TABLES + EXTRACTION_TABLES + RELEASE_TABLES + TEACHER_TABLES) <= tables:
            raise ValueError("schema 12 数据表不完整，拒绝自动重建")
        return {"from_version": 12, "to_version": 12, "backup": None, "changed": False}
    if version == 0 and tables:
        raise ValueError("未版本化的非空数据库不能自动迁移")
    required = set(FACT_TABLES[:5] if version == 1 else FACT_TABLES + (NOTE_TABLES if version >= 3 else ()) + (('note_chunks',) if version >= 4 else ()) + (WORKBENCH_TABLES if version >= 5 else ()) + (STUDY_TABLES if version >= 6 else ()) + (DOCUMENT_TABLES if version >= 7 else ()))
    if version and not required <= tables:
        raise ValueError("历史数据库结构不完整，拒绝迁移")
    if version >= 10 and not set(EXTRACTION_TABLES) <= tables:
        raise ValueError('schema10提取表不完整，拒绝迁移')
    if version >= 11 and not set(RELEASE_TABLES) <= tables:
        raise ValueError('schema11课程发布表不完整，拒绝迁移')
    if version >= 9 and not set(BANK_TABLES) <= tables:
        raise ValueError('schema9题库表不完整，拒绝迁移')
    if version >= 8 and not set(ARCHITECTURE_TABLES) <= tables:
        raise ValueError('schema8知识体系表不完整，拒绝迁移')
    if (connection.execute('PRAGMA integrity_check').fetchone()[0] != 'ok'
            or connection.execute('PRAGMA foreign_key_check').fetchall()):
        raise ValueError('迁移前完整性或外键检查失败，原数据库未修改')
    before, columns = preserved_snapshot(connection)
    backup = backup_database(connection, path, version) if version else None
    if backup:
        check = sqlite3.connect(backup)
        try:
            if (check.execute('PRAGMA user_version').fetchone()[0] != version or preserved_snapshot(check, columns)[0] != before
                    or check.execute('PRAGMA foreign_key_check').fetchall()):
                raise ValueError('备份与迁移前摘要不一致，原数据库尚未迁移')
        finally:
            check.close()
    # SQLite's documented table-rebuild sequence. Only widen the format CHECK;
    # every existing version column/row is copied and compared before commit.
    # Foreign-key declarations remain intact; foreign_key_check runs before COMMIT.
    connection.execute('PRAGMA foreign_keys=OFF')
    connection.execute("BEGIN EXCLUSIVE")
    try:
        # A writer changing the facts after backup invalidates that backup.
        if connection.execute("PRAGMA user_version").fetchone()[0] != version or preserved_snapshot(connection, columns)[0] != before:
            raise ValueError("备份后数据库发生变化，请停止其他写入后重新迁移")
        if version == 0:
            for statement in BASE:
                connection.execute(statement)
        if version < 2:
            connection.execute(TUTOR)
        if version < 3:
            for statement in NOTES:
                connection.execute(statement)
        for statement in PERSONAL_RAG if version < 4 else ():
            connection.execute(statement)
        for statement in WORKBENCH if version < 5 else ():
            connection.execute(statement)
        for statement in STUDY if version < 6 else ():
            connection.execute(statement)
        for statement in DOCUMENTS if version < 7 else ():
            connection.execute(statement)
        for statement in ARCHITECTURES if version < 8 else ():
            connection.execute(statement)
        if 7 <= version < 9:
            ddl = next(s for s in DOCUMENTS if s.startswith('CREATE TABLE document_versions'))
            connection.execute(ddl.replace('CREATE TABLE document_versions (', 'CREATE TABLE document_versions_v9 ('))
            connection.execute('INSERT INTO document_versions_v9 SELECT * FROM document_versions')
            connection.execute('DROP TABLE document_versions')
            connection.execute('ALTER TABLE document_versions_v9 RENAME TO document_versions')
        for statement in BANK if version < 9 else ():
            connection.execute(statement)
        for statement in EXTRACTION if version < 10 else ():
            connection.execute(statement)
        for statement in RELEASES if version < 11 else ():
            connection.execute(statement)
        for statement in TEACHER:
            connection.execute(statement)
        after = preserved_snapshot(connection, columns)[0]
        if any(after.get(name) != value for name, value in before.items()):
            raise ValueError("原学习事实校验失败，迁移已回滚")
        if connection.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("外键校验失败，迁移已回滚")
        if connection.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('迁移后完整性检查失败，迁移已回滚')
        connection.execute("PRAGMA user_version=12")
        connection.execute("COMMIT")
    except BaseException:
        connection.execute("ROLLBACK")
        raise
    finally:
        connection.execute('PRAGMA foreign_keys=ON')
    return {"from_version": version, "to_version": 12, "backup": str(backup) if backup else None,
            "changed": True, "learning_facts_verified": True, "original_tables_verified": True, "facts": before}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        args.db.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(args.db, isolation_level=None, timeout=10)
        try:
            connection.execute("PRAGMA foreign_keys=ON")
            report = migrate(connection, args.db)
        finally:
            connection.close()
    except (ValueError, OSError, sqlite3.Error) as exc:
        parser.error(str(exc))
    print(json.dumps(report, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
