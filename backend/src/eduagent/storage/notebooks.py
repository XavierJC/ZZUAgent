"""Notebook persistence; no provider, grading or document parsing dependencies."""
import json
from eduagent.storage.sqlite import encode


class NotebookRepository:
    def __init__(self, repository):
        self.repository, self.db = repository, repository.connection

    def get(self, student, key):
        row = self.db.execute('SELECT * FROM notebooks WHERE id=? AND student_id=?', (key, student)).fetchone()
        return dict(row) if row else None

    def list(self, student, archived):
        return [dict(r) for r in self.db.execute('SELECT n.*,(SELECT count(*) FROM notebook_sources s WHERE s.notebook_id=n.id) AS item_count,(SELECT count(*) FROM notebook_runs r WHERE r.notebook_id=n.id) AS conversation_count FROM notebooks n WHERE n.student_id=? AND n.archived=? ORDER BY n.updated_at DESC,n.id', (student, int(archived)))]

    def sources(self, student, key):
        return [dict(r) for r in self.db.execute('SELECT * FROM notebook_sources WHERE student_id=? AND notebook_id=? ORDER BY added_at,source_type,source_id', (student, key))]

    def operation(self, student, request_id):
        row = self.db.execute('SELECT * FROM notebook_operations WHERE student_id=? AND request_id=?', (student, request_id)).fetchone()
        return dict(row) if row else None

    def record_operation(self, student, request_id, key, checksum, result, stamp):
        self.db.execute('INSERT INTO notebook_operations VALUES (?,?,?,?,?,?)', (student, request_id, key, checksum, encode(result), stamp))

    def run(self, student, key, request_id):
        row = self.db.execute('SELECT * FROM notebook_runs WHERE student_id=? AND notebook_id=? AND request_id=?', (student, key, request_id)).fetchone()
        return dict(row) if row else None

    def runs(self, student, key):
        return [dict(r) for r in self.db.execute('SELECT * FROM notebook_runs WHERE student_id=? AND notebook_id=? ORDER BY created_at DESC,request_id DESC LIMIT 50', (student, key))]
