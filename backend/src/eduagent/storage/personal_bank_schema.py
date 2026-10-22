"""Schema9: resource metadata and a bank completely separate from assessment facts."""
BANK_TABLES = ('course_resources', 'question_extractions', 'personal_questions',
              'personal_question_revisions', 'personal_practice_sessions', 'personal_practice_attempts', 'personal_bank_operations')
BANK = (
    """CREATE TABLE course_resources (
      id TEXT PRIMARY KEY, student_id TEXT NOT NULL REFERENCES students(id), course_id TEXT NOT NULL REFERENCES courses(id),
      source_type TEXT NOT NULL CHECK(source_type IN ('document','personal_note','course_material','text')),
      source_id TEXT NOT NULL, resource_type TEXT NOT NULL, title TEXT NOT NULL, revision INTEGER NOT NULL CHECK(revision>=1),
      links_json TEXT NOT NULL DEFAULT '[]', content_md TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
      UNIQUE(student_id,course_id,source_type,source_id), UNIQUE(id,student_id,course_id))""",
    """CREATE TABLE question_extractions (
      id TEXT PRIMARY KEY, student_id TEXT NOT NULL REFERENCES students(id), course_id TEXT NOT NULL REFERENCES courses(id),
      resource_id TEXT NOT NULL, source_version TEXT NOT NULL, source_json TEXT NOT NULL,
      warnings_json TEXT NOT NULL, rule_version TEXT NOT NULL, created_at TEXT NOT NULL,
      FOREIGN KEY(resource_id,student_id,course_id) REFERENCES course_resources(id,student_id,course_id))""",
    """CREATE TABLE personal_questions (
      id TEXT PRIMARY KEY, student_id TEXT NOT NULL REFERENCES students(id), course_id TEXT NOT NULL REFERENCES courses(id),
      extraction_id TEXT, resource_id TEXT, source_version TEXT, source_json TEXT NOT NULL,
      payload_json TEXT NOT NULL, revision INTEGER NOT NULL CHECK(revision>=1),
      status TEXT NOT NULL CHECK(status IN ('draft','practice','archived')), created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
      UNIQUE(id,student_id,course_id),
      FOREIGN KEY(resource_id,student_id,course_id) REFERENCES course_resources(id,student_id,course_id),
      FOREIGN KEY(extraction_id) REFERENCES question_extractions(id))""",
    """CREATE TABLE personal_question_revisions (
      question_id TEXT NOT NULL, revision INTEGER NOT NULL, student_id TEXT NOT NULL, course_id TEXT NOT NULL,
      payload_json TEXT NOT NULL, status TEXT NOT NULL, review_json TEXT NOT NULL, created_at TEXT NOT NULL,
      PRIMARY KEY(question_id,revision),
      FOREIGN KEY(question_id,student_id,course_id) REFERENCES personal_questions(id,student_id,course_id))""",
    """CREATE TABLE personal_practice_sessions (
      id TEXT PRIMARY KEY, student_id TEXT NOT NULL, course_id TEXT NOT NULL, question_id TEXT NOT NULL,
      question_revision INTEGER NOT NULL, snapshot_json TEXT NOT NULL, source_json TEXT NOT NULL,
      status TEXT NOT NULL CHECK(status IN ('open','answered')), created_at TEXT NOT NULL,
      UNIQUE(id,student_id,course_id),
      FOREIGN KEY(question_id,student_id,course_id) REFERENCES personal_questions(id,student_id,course_id))""",
    """CREATE TABLE personal_practice_attempts (
      session_id TEXT PRIMARY KEY, student_id TEXT NOT NULL, course_id TEXT NOT NULL, selected_answer TEXT NOT NULL,
      correct INTEGER CHECK(correct IS NULL OR correct IN (0,1)), result_json TEXT NOT NULL, created_at TEXT NOT NULL,
      FOREIGN KEY(session_id,student_id,course_id) REFERENCES personal_practice_sessions(id,student_id,course_id))""",
    """CREATE TABLE personal_bank_operations (
      student_id TEXT NOT NULL REFERENCES students(id), course_id TEXT NOT NULL REFERENCES courses(id), request_id TEXT NOT NULL,
      request_hash TEXT NOT NULL, result_json TEXT NOT NULL, created_at TEXT NOT NULL,
      PRIMARY KEY(student_id,course_id,request_id))""",
    'CREATE INDEX personal_bank_scope ON personal_questions(student_id,course_id,status,updated_at,id)',
    'CREATE INDEX personal_practice_scope ON personal_practice_sessions(student_id,course_id,created_at,id)',
)
