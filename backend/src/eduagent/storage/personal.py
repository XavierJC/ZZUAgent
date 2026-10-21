"""Version-fenced derived chunks. Every public operation starts with ownership."""

from eduagent.domain.notes import NoteConflict, NoteNotFound, course, note_id, revision
from eduagent.retrieval.note_chunks import INDEXER_VERSION
from eduagent.services.learning import now


class PersonalRepository:
    def __init__(self, repository):
        self.repository = repository
        self.db = repository.connection

    def note(self, student_id, identifier, course_id='machine_learning'):
        course(course_id)
        note_id(identifier)
        row = self.db.execute('SELECT * FROM notes WHERE id=? AND student_id=? AND course_id=? AND deleted_at IS NULL',
                              (identifier, student_id, course_id)).fetchone()
        if row is None:
            raise NoteNotFound('当前学习标识下没有该笔记')
        return dict(row)

    def state(self, identifier):
        row = self.db.execute('SELECT * FROM note_index_state WHERE note_id=?', (identifier,)).fetchone()
        return dict(row) if row else None

    def invalidate(self, identifier, target_revision, timestamp, deleted=False):
        self.db.execute('DELETE FROM note_chunks WHERE note_id=?', (identifier,))
        self.db.execute('''INSERT INTO note_index_state(note_id,status,target_revision,chunk_count,updated_at)
            VALUES (?,?,?,0,?) ON CONFLICT(note_id) DO UPDATE SET status=excluded.status,
            target_revision=excluded.target_revision,indexed_revision=NULL,indexed_hash=NULL,indexer_version=NULL,
            error_code=NULL,chunk_count=0,updated_at=excluded.updated_at,build_token=NULL,building_started_at=NULL''',
            (identifier, 'disabled' if deleted else 'pending', target_revision, timestamp))

    def claim(self, student_id, identifier, expected_revision, token):
        revision(expected_revision)
        with self.repository.transaction():
            current = self.note(student_id, identifier)
            if current['revision'] != expected_revision:
                raise NoteConflict('笔记版本已变化，请刷新后重试')
            self.invalidate(identifier, expected_revision, now())
            self.db.execute("UPDATE note_index_state SET status='building',build_token=?,building_started_at=? WHERE note_id=?",
                            (token, now(), identifier))
            return current

    def matching(self, snapshot, token):
        row = self.db.execute('''SELECT 1 FROM notes n JOIN note_index_state s ON s.note_id=n.id
            WHERE n.id=? AND n.student_id=? AND n.course_id=? AND n.deleted_at IS NULL
            AND n.revision=? AND n.content_hash=? AND s.target_revision=n.revision
            AND s.status='building' AND s.build_token=?''',
            (snapshot['id'], snapshot['student_id'], snapshot['course_id'], snapshot['revision'], snapshot['content_hash'], token)).fetchone()
        return row is not None

    def publish(self, snapshot, token, chunks):
        with self.repository.transaction():
            if not self.matching(snapshot, token):
                raise NoteConflict('构建期间笔记或索引任务已变化，旧任务未发布')
            self.db.execute('DELETE FROM note_chunks WHERE note_id=?', (snapshot['id'],))
            for chunk in chunks:
                fields = list(chunk)
                self.db.execute('INSERT INTO note_chunks(' + ','.join(fields) + ') VALUES (' + ','.join(':' + key for key in fields) + ')', chunk)
            self.db.execute('''UPDATE note_index_state SET status=?,indexed_revision=?,indexed_hash=?,indexer_version=?,
                chunk_count=?,error_code=NULL,build_token=NULL,building_started_at=NULL,updated_at=? WHERE note_id=?''',
                ('ready' if chunks else 'empty', snapshot['revision'], snapshot['content_hash'], INDEXER_VERSION,
                 len(chunks), now(), snapshot['id']))
            return self.state(snapshot['id'])

    def fail(self, snapshot, token, code):
        with self.repository.transaction():
            if self.matching(snapshot, token):
                self.db.execute("UPDATE note_index_state SET status='failed',error_code=?,build_token=NULL,building_started_at=NULL,updated_at=? WHERE note_id=?",
                                (code, now(), snapshot['id']))

    def chunks(self, student_id, course_id, identifiers):
        if not identifiers:
            return []
        marks = ','.join('?' for _ in identifiers)
        return [dict(row) for row in self.db.execute(f'''SELECT c.* FROM note_chunks c JOIN notes n ON n.id=c.note_id
            JOIN note_index_state s ON s.note_id=n.id WHERE n.student_id=? AND n.course_id=? AND n.deleted_at IS NULL
            AND c.student_id=n.student_id AND c.course_id=n.course_id AND c.revision=n.revision AND c.content_hash=n.content_hash
            AND s.status='ready' AND s.indexed_revision=n.revision AND s.indexed_hash=n.content_hash
            AND s.target_revision=n.revision AND c.indexer_version=? AND s.indexer_version=? AND n.id IN ({marks})
            ORDER BY c.note_id,c.ordinal''', (student_id, course_id, INDEXER_VERSION, INDEXER_VERSION, *identifiers))]
