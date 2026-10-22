"""Additive schema10. Original question/attempt JSON remains untouched."""
EXTRACTION_TABLES = ('question_extraction_tasks', 'personal_practice_drafts')
EXTRACTION = (
    """CREATE TABLE question_extraction_tasks (
      request_id TEXT PRIMARY KEY, student_id TEXT NOT NULL REFERENCES students(id), course_id TEXT NOT NULL REFERENCES courses(id),
      request_hash TEXT NOT NULL, request_json TEXT NOT NULL, context_json TEXT NOT NULL,
      status TEXT NOT NULL CHECK(status IN ('running','complete','failed','uncertain','stale')),
      model_calls INTEGER NOT NULL DEFAULT 0, result_json TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""",
    'CREATE INDEX extraction_tasks_scope ON question_extraction_tasks(student_id,course_id,created_at,request_id)',
    """CREATE TABLE personal_practice_drafts (
      session_id TEXT PRIMARY KEY, student_id TEXT NOT NULL, course_id TEXT NOT NULL, revision INTEGER NOT NULL,
      response_text TEXT NOT NULL, needs_review INTEGER NOT NULL CHECK(needs_review IN (0,1)), updated_at TEXT NOT NULL,
      FOREIGN KEY(session_id,student_id,course_id) REFERENCES personal_practice_sessions(id,student_id,course_id))""",
)
