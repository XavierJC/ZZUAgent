"""Schema11 adds release and teaching provenance without rewriting old facts."""
RELEASE_TABLES = ('course_release_drafts','course_releases','teaching_sessions','teaching_decisions','teaching_events','teaching_explanations','course_workflow_operations')
RELEASES = (
    """CREATE TABLE course_release_drafts (
      id TEXT PRIMARY KEY, student_id TEXT NOT NULL REFERENCES students(id), course_id TEXT NOT NULL REFERENCES courses(id),
      revision INTEGER NOT NULL CHECK(revision>=1), payload_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
      UNIQUE(id,student_id,course_id))""",
    """CREATE TABLE course_releases (
      id TEXT PRIMARY KEY, owner_id TEXT REFERENCES students(id), scope_key TEXT NOT NULL, course_id TEXT NOT NULL REFERENCES courses(id),
      release_version INTEGER NOT NULL CHECK(release_version>=1), kind TEXT NOT NULL CHECK(kind IN ('demo','reviewed')),
      draft_id TEXT REFERENCES course_release_drafts(id), draft_revision INTEGER, snapshot_json TEXT NOT NULL, content_hash TEXT NOT NULL,
      published_at TEXT NOT NULL, UNIQUE(scope_key,course_id,release_version), UNIQUE(draft_id,draft_revision))""",
    """CREATE TABLE teaching_sessions (
      id TEXT PRIMARY KEY, student_id TEXT NOT NULL REFERENCES students(id), course_id TEXT NOT NULL REFERENCES courses(id),
      release_id TEXT NOT NULL REFERENCES course_releases(id), goals_json TEXT NOT NULL, started_revision INTEGER NOT NULL,
      stage TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, UNIQUE(id,student_id))""",
    """CREATE TABLE teaching_decisions (
      decision_id TEXT PRIMARY KEY REFERENCES decisions(id), session_id TEXT NOT NULL REFERENCES teaching_sessions(id),
      student_id TEXT NOT NULL REFERENCES students(id), release_id TEXT REFERENCES course_releases(id),
      origin TEXT NOT NULL CHECK(origin IN ('allocated_in_session','legacy_unbound')), question_json TEXT NOT NULL, created_at TEXT NOT NULL)""",
    """CREATE TABLE teaching_events (
      event_id TEXT PRIMARY KEY REFERENCES attempts(event_id), session_id TEXT NOT NULL REFERENCES teaching_sessions(id),
      student_id TEXT NOT NULL REFERENCES students(id), release_id TEXT NOT NULL REFERENCES course_releases(id),
      allocation_origin TEXT NOT NULL, question_snapshot_json TEXT NOT NULL, created_at TEXT NOT NULL)""",
    """CREATE TABLE teaching_explanations (
      request_id TEXT PRIMARY KEY, student_id TEXT NOT NULL REFERENCES students(id), session_id TEXT NOT NULL REFERENCES teaching_sessions(id),
      request_hash TEXT NOT NULL, request_json TEXT NOT NULL, context_json TEXT NOT NULL,
      status TEXT NOT NULL CHECK(status IN ('running','complete','uncertain')), created_at TEXT NOT NULL)""",
    """CREATE TABLE course_workflow_operations (
      student_id TEXT NOT NULL REFERENCES students(id), request_id TEXT NOT NULL, request_hash TEXT NOT NULL,
      result_json TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY(student_id,request_id))""",
    'CREATE INDEX teaching_sessions_scope ON teaching_sessions(student_id,created_at,id)',
    'CREATE INDEX course_releases_scope ON course_releases(scope_key,course_id,release_version)',
)
