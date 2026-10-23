"""Reviewed page-to-concept mappings; the small TF-IDF index is rebuildable in memory."""
TEACHER_TABLES = ('teaching_material_links', 'teaching_material_operations')
TEACHER = (
    """CREATE TABLE teaching_material_links (
      id TEXT PRIMARY KEY, student_id TEXT NOT NULL REFERENCES students(id),
      course_id TEXT NOT NULL REFERENCES courses(id), document_id TEXT NOT NULL REFERENCES course_documents(id),
      version_id TEXT NOT NULL REFERENCES document_versions(id), run_id TEXT NOT NULL REFERENCES document_parse_runs(id),
      parse_head_id TEXT NOT NULL REFERENCES document_parse_runs(id),
      unit_id TEXT NOT NULL REFERENCES document_units(id), unit_hash TEXT NOT NULL,
      architecture_id TEXT NOT NULL REFERENCES knowledge_architectures(id), concept_id TEXT NOT NULL,
      architecture_version INTEGER, start_offset INTEGER NOT NULL, end_offset INTEGER NOT NULL,
      original_text TEXT NOT NULL, excerpt_md TEXT NOT NULL, excerpt_origin TEXT NOT NULL,
      status TEXT NOT NULL CHECK(status IN ('candidate','confirmed','rejected')),
      revision INTEGER NOT NULL CHECK(revision>=1), reviewer TEXT NOT NULL DEFAULT '',
      created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""",
    'CREATE INDEX teaching_links_scope ON teaching_material_links(student_id,document_id,status)',
    """CREATE TABLE teaching_material_operations (
      student_id TEXT NOT NULL REFERENCES students(id), request_id TEXT NOT NULL,
      request_hash TEXT NOT NULL, result_json TEXT NOT NULL, created_at TEXT NOT NULL,
      PRIMARY KEY(student_id,request_id))""",
)
