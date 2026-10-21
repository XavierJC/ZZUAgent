"""Append-only self report storage; caller owns the short transaction."""


class SelfAssessmentRepository:
    def __init__(self, repository):
        self.db = repository.connection

    def revision(self, student, course):
        return self.db.execute('SELECT COALESCE(MAX(assessment_revision),0) FROM self_assessment_batches WHERE student_id=? AND course_id=?',
                               (student, course)).fetchone()[0]

    def batch(self, request_id):
        return self.db.execute('SELECT * FROM self_assessment_batches WHERE request_id=?', (request_id,)).fetchone()

    def entries(self, student, course, *, knowledge=None, batch=None, limit=None, offset=0):
        sql = '''SELECT e.*,b.assessment_revision,b.learning_revision_at_save,b.created_at FROM self_assessment_entries e
                 JOIN self_assessment_batches b ON b.request_id=e.batch_id AND b.student_id=e.student_id AND b.course_id=e.course_id
                 WHERE e.student_id=? AND e.course_id=?'''
        params = [student, course]
        if knowledge:
            sql += ' AND e.knowledge_id=?'; params.append(knowledge)
        if batch:
            sql += ' AND e.batch_id=?'; params.append(batch)
        sql += ' ORDER BY b.assessment_revision DESC,e.knowledge_id,e.id'
        if limit is not None:
            sql += ' LIMIT ? OFFSET ?'; params.extend((limit, offset))
        return [dict(row) for row in self.db.execute(sql, params)]

    def latest(self, student, course):
        # At most five current rows; avoid reading an unbounded history into RAM.
        return {row['knowledge_id']: row for row in self._latest_rows(student, course)}

    def _latest_rows(self, student, course):
        sql = '''SELECT e.*,b.assessment_revision,b.learning_revision_at_save,b.created_at
                 FROM self_assessment_entries e JOIN self_assessment_batches b ON b.request_id=e.batch_id
                 WHERE e.student_id=? AND e.course_id=? AND NOT EXISTS (
                   SELECT 1 FROM self_assessment_entries newer JOIN self_assessment_batches nb ON nb.request_id=newer.batch_id
                   WHERE newer.student_id=e.student_id AND newer.course_id=e.course_id AND newer.knowledge_id=e.knowledge_id
                   AND nb.assessment_revision>b.assessment_revision)'''
        return [dict(row) for row in self.db.execute(sql, (student, course))]

    def insert(self, batch, entries):
        self.db.execute('INSERT INTO self_assessment_batches VALUES (?,?,?,?,?,?,?,?,?)', batch)
        self.db.executemany('INSERT INTO self_assessment_entries VALUES (?,?,?,?,?,?,?)', entries)
