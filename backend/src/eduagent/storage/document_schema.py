"""Additive schema7 document tables; assessment tables are untouched."""

DOCUMENT_TABLES = ('courses', 'course_documents', 'document_versions', 'document_parse_runs', 'document_units', 'document_operations')
DOCUMENTS = (
    'CREATE TABLE courses (id TEXT PRIMARY KEY, name TEXT NOT NULL)',
    "INSERT INTO courses VALUES ('machine_learning','机器学习')",
    """CREATE TABLE course_documents (
       id TEXT PRIMARY KEY, student_id TEXT NOT NULL REFERENCES students(id), course_id TEXT NOT NULL REFERENCES courses(id),
       title TEXT NOT NULL, material_role TEXT NOT NULL CHECK(material_role IN ('teaching_slides','textbook','framework','handout')),
       source_note TEXT NOT NULL, local_rights_confirmed INTEGER NOT NULL CHECK(local_rights_confirmed=1),
       revision INTEGER NOT NULL CHECK(revision>=1), file_revision INTEGER NOT NULL CHECK(file_revision>=1),
       parse_generation INTEGER NOT NULL CHECK(parse_generation>=1), current_version_id TEXT, current_parse_id TEXT,
       created_at TEXT NOT NULL, updated_at TEXT NOT NULL, deleted_at TEXT,
       UNIQUE(id,student_id,course_id),
       FOREIGN KEY(current_version_id,id,student_id,course_id) REFERENCES document_versions(id,document_id,student_id,course_id) DEFERRABLE INITIALLY DEFERRED,
       FOREIGN KEY(current_parse_id,current_version_id,id,student_id,course_id) REFERENCES document_parse_runs(id,version_id,document_id,student_id,course_id) DEFERRABLE INITIALLY DEFERRED)""",
    'CREATE INDEX documents_by_scope ON course_documents(student_id,course_id,deleted_at,updated_at,id)',
    """CREATE TABLE document_versions (
       id TEXT PRIMARY KEY, document_id TEXT NOT NULL, student_id TEXT NOT NULL, course_id TEXT NOT NULL,
       file_revision INTEGER NOT NULL CHECK(file_revision>=1), file_name TEXT NOT NULL,
       format TEXT NOT NULL CHECK(format IN ('pdf','pptx','md','txt','png','jpg','jpeg','webp')), size_bytes INTEGER NOT NULL CHECK(size_bytes>=0),
       content_hash TEXT NOT NULL, storage_key TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL,
       UNIQUE(document_id,file_revision), UNIQUE(id,document_id,student_id,course_id),
       FOREIGN KEY(document_id,student_id,course_id) REFERENCES course_documents(id,student_id,course_id))""",
    """CREATE TABLE document_parse_runs (
       id TEXT PRIMARY KEY, document_id TEXT NOT NULL, version_id TEXT NOT NULL, student_id TEXT NOT NULL, course_id TEXT NOT NULL,
       generation INTEGER NOT NULL CHECK(generation>=1), mode TEXT NOT NULL CHECK(mode IN ('local','vision')),
       status TEXT NOT NULL CHECK(status IN ('pending','processing','ready','partial','empty','failed','superseded','uncertain')),
       expected_revision INTEGER NOT NULL, parser_version TEXT NOT NULL, pages_json TEXT NOT NULL DEFAULT '[]',
       external_consent INTEGER NOT NULL DEFAULT 0 CHECK(external_consent IN (0,1)),
       build_token TEXT, recovery_count INTEGER NOT NULL DEFAULT 0, error_code TEXT,
       warnings_json TEXT NOT NULL DEFAULT '[]', artifact_key TEXT, artifact_hash TEXT, artifact_bytes INTEGER NOT NULL DEFAULT 0,
       unit_count INTEGER NOT NULL DEFAULT 0, model_calls INTEGER NOT NULL DEFAULT 0 CHECK(model_calls>=0),
       usage_json TEXT NOT NULL DEFAULT '{"prompt_tokens":0,"completion_tokens":0}', model TEXT,
       created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
       UNIQUE(id,version_id,document_id,student_id,course_id),
       FOREIGN KEY(version_id,document_id,student_id,course_id) REFERENCES document_versions(id,document_id,student_id,course_id),
       CHECK(mode='local' OR external_consent=1))""",
    'CREATE INDEX document_jobs ON document_parse_runs(status,created_at,id)',
    """CREATE TABLE document_units (
       id TEXT PRIMARY KEY, run_id TEXT NOT NULL, version_id TEXT NOT NULL, document_id TEXT NOT NULL,
       student_id TEXT NOT NULL, course_id TEXT NOT NULL, ordinal INTEGER NOT NULL CHECK(ordinal>=1),
       kind TEXT NOT NULL, title TEXT NOT NULL, text TEXT NOT NULL, content_md TEXT NOT NULL, interpretation_md TEXT NOT NULL,
       origin TEXT NOT NULL CHECK(origin IN ('local_extraction','deepseek_vision')), location_json TEXT NOT NULL,
       blocks_json TEXT NOT NULL, warnings_json TEXT NOT NULL, content_hash TEXT NOT NULL,
       UNIQUE(run_id,ordinal),
       FOREIGN KEY(run_id,version_id,document_id,student_id,course_id) REFERENCES document_parse_runs(id,version_id,document_id,student_id,course_id))""",
    """CREATE TABLE document_operations (
       student_id TEXT NOT NULL, course_id TEXT NOT NULL, request_id TEXT NOT NULL, request_hash TEXT NOT NULL,
       operation TEXT NOT NULL, document_id TEXT NOT NULL, result_json TEXT NOT NULL, created_at TEXT NOT NULL,
       PRIMARY KEY(student_id,course_id,request_id),
       FOREIGN KEY(document_id,student_id,course_id) REFERENCES course_documents(id,student_id,course_id))""",
)
