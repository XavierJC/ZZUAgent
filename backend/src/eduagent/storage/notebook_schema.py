"""Additive notebook membership. Original learning and content stay authoritative."""
NOTEBOOK_TABLES = ('notebooks', 'notebook_sources', 'notebook_operations', 'notebook_runs', 'notebook_practice')
NOTEBOOKS = (
    """CREATE TABLE notebooks (
       id TEXT PRIMARY KEY, student_id TEXT NOT NULL REFERENCES students(id),
       course_id TEXT NOT NULL CHECK(course_id='machine_learning'),
       title TEXT NOT NULL CHECK(length(title) BETWEEN 1 AND 120),
       description TEXT NOT NULL CHECK(length(description)<=1000),
       revision INTEGER NOT NULL CHECK(revision>=1), archived INTEGER NOT NULL DEFAULT 0 CHECK(archived IN (0,1)),
       created_at TEXT NOT NULL, updated_at TEXT NOT NULL, UNIQUE(id,student_id,course_id))""",
    'CREATE INDEX notebooks_by_student ON notebooks(student_id,archived,updated_at,id)',
    """CREATE TABLE notebook_sources (
       notebook_id TEXT NOT NULL, student_id TEXT NOT NULL, course_id TEXT NOT NULL,
       source_type TEXT NOT NULL CHECK(source_type IN ('course_material','uploaded_document','teaching_material','personal_note','personal_question')),
       source_id TEXT NOT NULL, source_version TEXT NOT NULL, title_snapshot TEXT NOT NULL,
       added_at TEXT NOT NULL, PRIMARY KEY(notebook_id,source_type,source_id),
       FOREIGN KEY(notebook_id,student_id,course_id) REFERENCES notebooks(id,student_id,course_id))""",
    """CREATE TABLE notebook_operations (
       student_id TEXT NOT NULL REFERENCES students(id), request_id TEXT NOT NULL,
       notebook_id TEXT NOT NULL, request_hash TEXT NOT NULL, result_json TEXT NOT NULL, created_at TEXT NOT NULL,
       PRIMARY KEY(student_id,request_id), FOREIGN KEY(notebook_id) REFERENCES notebooks(id))""",
    """CREATE TABLE notebook_runs (
       request_id TEXT PRIMARY KEY, notebook_id TEXT NOT NULL, student_id TEXT NOT NULL,
       course_id TEXT NOT NULL, notebook_revision INTEGER NOT NULL, request_hash TEXT NOT NULL,
       request_json TEXT NOT NULL, context_json TEXT NOT NULL, created_at TEXT NOT NULL,
       FOREIGN KEY(notebook_id,student_id,course_id) REFERENCES notebooks(id,student_id,course_id))""",
    'CREATE INDEX notebook_runs_by_scope ON notebook_runs(student_id,notebook_id,created_at,request_id)',
    """CREATE TABLE notebook_practice (
       session_id TEXT PRIMARY KEY REFERENCES personal_practice_sessions(id),
       notebook_id TEXT NOT NULL, student_id TEXT NOT NULL, course_id TEXT NOT NULL,
       created_at TEXT NOT NULL,
       FOREIGN KEY(notebook_id,student_id,course_id) REFERENCES notebooks(id,student_id,course_id))""",
)
