"""Durable guide claims/results, independent from both tutor histories."""

from eduagent.storage.sqlite import encode


class StudyGuideRepository:
    def __init__(self, repository):
        self.db = repository.connection

    def find(self, request_id):
        return self.db.execute('SELECT * FROM study_guide_runs WHERE request_id=?', (request_id,)).fetchone()

    def recent(self, student, course, limit):
        return self.db.execute('SELECT * FROM study_guide_runs WHERE student_id=? AND course_id=? ORDER BY created_at DESC,request_id DESC LIMIT ?',
                               (student, course, limit)).fetchall()

    def claim(self, student, request_id, digest, body, context, snapshot, result, timestamp):
        self.db.execute('INSERT INTO study_guide_runs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
            (request_id, student, context['course_id'], digest, encode(body), snapshot['learning_revision'], snapshot['assessment_revision'],
             encode(context), encode(snapshot), encode(snapshot['recommendations']), encode(result), 'running', 0, timestamp, timestamp))

    def attempted(self, student, request_id, timestamp):
        return self.db.execute("UPDATE study_guide_runs SET model_calls=model_calls+1,updated_at=? WHERE request_id=? AND student_id=? AND status='running'",
                               (timestamp, request_id, student)).rowcount

    def finish(self, request_id, status, result, timestamp):
        self.db.execute("UPDATE study_guide_runs SET status=?,result_json=?,updated_at=? WHERE request_id=? AND status='running'",
                        (status, encode(result), timestamp, request_id))
