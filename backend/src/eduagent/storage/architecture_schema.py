"""Additive schema8: scoped identities, drafts and immutable published graphs."""
ARCHITECTURE_TABLES = ('knowledge_architectures','knowledge_entities','knowledge_drafts','knowledge_versions','knowledge_candidate_batches','knowledge_operations')
ARCHITECTURES = (
    """CREATE TABLE knowledge_architectures (
       id TEXT PRIMARY KEY, student_id TEXT NOT NULL REFERENCES students(id), course_id TEXT NOT NULL REFERENCES courses(id),
       title TEXT NOT NULL, revision INTEGER NOT NULL CHECK(revision>=1), published_version INTEGER NOT NULL DEFAULT 0 CHECK(published_version>=0),
       created_at TEXT NOT NULL, updated_at TEXT NOT NULL, UNIQUE(id,student_id,course_id))""",
    'CREATE INDEX architectures_by_student ON knowledge_architectures(student_id,course_id,updated_at,id)',
    """CREATE TABLE knowledge_entities (
       architecture_id TEXT NOT NULL, id TEXT NOT NULL, student_id TEXT NOT NULL, course_id TEXT NOT NULL,
       kind TEXT NOT NULL CHECK(kind IN ('chapter','concept')), created_at TEXT NOT NULL,
       PRIMARY KEY(architecture_id,id), UNIQUE(architecture_id,id,student_id,course_id),
       FOREIGN KEY(architecture_id,student_id,course_id) REFERENCES knowledge_architectures(id,student_id,course_id))""",
    """CREATE TABLE knowledge_drafts (
       architecture_id TEXT PRIMARY KEY, student_id TEXT NOT NULL, course_id TEXT NOT NULL,
       status TEXT NOT NULL CHECK(status IN ('editing','locked')), base_version INTEGER NOT NULL CHECK(base_version>=0),
       graph_json TEXT NOT NULL, updated_at TEXT NOT NULL,
       FOREIGN KEY(architecture_id,student_id,course_id) REFERENCES knowledge_architectures(id,student_id,course_id))""",
    """CREATE TABLE knowledge_versions (
       architecture_id TEXT NOT NULL, version INTEGER NOT NULL CHECK(version>=1), student_id TEXT NOT NULL, course_id TEXT NOT NULL,
       graph_json TEXT NOT NULL, graph_hash TEXT NOT NULL, sources_json TEXT NOT NULL, published_at TEXT NOT NULL,
       PRIMARY KEY(architecture_id,version),
       FOREIGN KEY(architecture_id,student_id,course_id) REFERENCES knowledge_architectures(id,student_id,course_id))""",
    """CREATE TABLE knowledge_candidate_batches (
       id TEXT PRIMARY KEY, architecture_id TEXT NOT NULL, student_id TEXT NOT NULL, course_id TEXT NOT NULL,
       rule_version TEXT NOT NULL, graph_json TEXT NOT NULL, evidence_json TEXT NOT NULL, unclassified_json TEXT NOT NULL, created_at TEXT NOT NULL,
       UNIQUE(id,architecture_id,student_id,course_id),
       FOREIGN KEY(architecture_id,student_id,course_id) REFERENCES knowledge_architectures(id,student_id,course_id))""",
    """CREATE TABLE knowledge_operations (
       student_id TEXT NOT NULL, course_id TEXT NOT NULL, request_id TEXT NOT NULL, architecture_id TEXT NOT NULL,
       request_hash TEXT NOT NULL, result_json TEXT NOT NULL, created_at TEXT NOT NULL,
       PRIMARY KEY(student_id,course_id,request_id),
       FOREIGN KEY(architecture_id,student_id,course_id) REFERENCES knowledge_architectures(id,student_id,course_id))""",
)
