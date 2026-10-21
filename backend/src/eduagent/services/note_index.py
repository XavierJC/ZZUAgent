"""Synchronous, recoverable derived indexing; no provider or task infrastructure."""

from uuid import uuid4

from eduagent.domain.notes import NoteConflict, NoteNotFound
from eduagent.retrieval.note_chunks import chunk_markdown, ChunkingError, INDEXER_VERSION
from eduagent.storage.personal import PersonalRepository


class NoteIndexer:
    def __init__(self, repository, builder=chunk_markdown):
        self.storage = PersonalRepository(repository)
        self.builder = builder

    def rebuild(self, student_id, identifier, expected_revision):
        token = uuid4().hex
        snapshot = self.storage.claim(student_id, identifier, expected_revision, token)
        try:
            chunks = self.builder(snapshot)
            return self.storage.publish(snapshot, token, chunks)
        except NoteConflict:
            raise
        except Exception as exc:
            # Do not persist exception text or raw Markdown to logs/errors.
            code = exc.code if isinstance(exc, ChunkingError) else 'index_build_failed'
            self.storage.fail(snapshot, token, code)
            return self.storage.state(identifier)

    def recover(self):
        """Restart recovery of active incomplete/outdated chunks, never failed loops."""
        rows = self.storage.db.execute('''SELECT n.id,n.student_id,n.revision FROM notes n
            LEFT JOIN note_index_state s ON s.note_id=n.id WHERE n.deleted_at IS NULL AND
            (s.note_id IS NULL OR s.status IN ('disabled','pending','building') OR
             (s.status IN ('ready','empty') AND (s.indexed_revision!=n.revision OR s.indexed_hash!=n.content_hash
              OR s.indexer_version IS NULL OR s.indexer_version!=?))) ORDER BY n.id''', (INDEXER_VERSION,)).fetchall()
        result = {'recovered': 0, 'failed': 0, 'superseded': 0}
        for row in rows:
            try:
                state = self.rebuild(row['student_id'], row['id'], row['revision'])
                result['failed' if state['status'] == 'failed' else 'recovered'] += 1
            except (NoteConflict, NoteNotFound):
                result['superseded'] += 1
        return result
