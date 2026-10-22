"""Document persistence with explicit owner/course keys on every lookup."""

import json
from eduagent.documents.models import DocumentError, uuid_text


class DocumentRepository:
    def __init__(self, repository):
        self.repository, self.db = repository, repository.connection

    def document(self, student, identifier, course='machine_learning', include_deleted=False):
        uuid_text(identifier)
        row = self.db.execute('SELECT * FROM course_documents WHERE id=? AND student_id=? AND course_id=?',
                              (identifier, student, course)).fetchone()
        if row is None or row['deleted_at'] and not include_deleted:
            raise DocumentError('document_not_found', 404)
        return dict(row)

    def version(self, document, version_id=None):
        row = self.db.execute('''SELECT * FROM document_versions WHERE id=? AND document_id=? AND student_id=? AND course_id=?''',
                              (version_id or document['current_version_id'], document['id'], document['student_id'], document['course_id'])).fetchone()
        if row is None:
            raise DocumentError('document_not_found', 404)
        return dict(row)

    def run(self, document, run_id=None):
        row = self.db.execute('SELECT * FROM document_parse_runs WHERE id=? AND document_id=? AND student_id=? AND course_id=?',
                              (run_id or document['current_parse_id'], document['id'], document['student_id'], document['course_id'])).fetchone()
        if row is None:
            raise DocumentError('document_not_found', 404)
        return dict(row)

    def replay(self, student, course, request_id, digest):
        uuid_text(request_id)
        row = self.db.execute('SELECT * FROM document_operations WHERE student_id=? AND course_id=? AND request_id=?',
                              (student, course, request_id)).fetchone()
        if row is None:
            return None
        if row['request_hash'] != digest:
            raise DocumentError('request_id_conflict', 409)
        return json.loads(row['result_json'])

    def record(self, student, course, request_id, digest, operation, document_id, value, timestamp):
        self.db.execute('INSERT INTO document_operations VALUES (?,?,?,?,?,?,?,?)',
                        (student, course, request_id, digest, operation, document_id,
                         json.dumps(value, ensure_ascii=False, allow_nan=False), timestamp))

    def insert(self, table, values):
        if table not in ('course_documents', 'document_versions', 'document_parse_runs', 'document_units'):
            raise ValueError('无效的内部资料表')
        # Values/column names are built by server code, never copied from a client dictionary.
        columns = ','.join(values)
        self.db.execute(f'INSERT INTO {table} ({columns}) VALUES ({",".join("?" for _ in values)})', tuple(values.values()))
