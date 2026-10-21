"""Scoped note SQL. The service owns transactions; no learning tables are written."""

from eduagent.storage.sqlite import SQLiteRepository


class NoteRepository:
    def __init__(self, repository: SQLiteRepository):
        self.db = repository.connection

    def get(self, student_id: str, course_id: str, identifier: str):
        return self.db.execute(
            "SELECT * FROM notes WHERE id=? AND student_id=? AND course_id=? AND deleted_at IS NULL",
            (identifier, student_id, course_id),
        ).fetchone()

    def id_used(self, identifier: str) -> bool:
        return self.db.execute("SELECT 1 FROM notes WHERE id=?", (identifier,)).fetchone() is not None

    def links(self, identifier: str) -> list[str]:
        return [row[0] for row in self.db.execute(
            "SELECT knowledge_point_id FROM note_knowledge_points WHERE note_id=? ORDER BY knowledge_point_id", (identifier,))]

    def set_links(self, identifier: str, links: list[str]) -> None:
        self.db.execute("DELETE FROM note_knowledge_points WHERE note_id=?", (identifier,))
        self.db.executemany("INSERT INTO note_knowledge_points VALUES (?,?)", [(identifier, key) for key in links])

    def usage(self, student_id: str, course_id: str) -> tuple[int, int]:
        row = self.db.execute(
            "SELECT count(*),coalesce(sum(length(CAST(content_md AS BLOB))),0) FROM notes "
            "WHERE student_id=? AND course_id=? AND deleted_at IS NULL", (student_id, course_id),
        ).fetchone()
        return row[0], row[1]

    def list(self, student_id: str, course_id: str, query: str, knowledge_id: str | None, limit: int, offset: int):
        where = "n.student_id=? AND n.course_id=? AND n.deleted_at IS NULL"
        values = [student_id, course_id]
        if query:
            where += " AND n.title LIKE ? ESCAPE '\\'"
            values.append('%' + query.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%')
        if knowledge_id:
            where += " AND EXISTS (SELECT 1 FROM note_knowledge_points k WHERE k.note_id=n.id AND k.knowledge_point_id=?)"
            values.append(knowledge_id)
        total = self.db.execute(f"SELECT count(*) FROM notes n WHERE {where}", values).fetchone()[0]
        rows = self.db.execute(f"SELECT n.* FROM notes n WHERE {where} ORDER BY n.updated_at DESC,n.id LIMIT ? OFFSET ?",
                               [*values, limit, offset]).fetchall()
        return rows, total

    def insert(self, row: dict) -> None:
        self.db.execute("""INSERT INTO notes
            (id,student_id,course_id,title,content_md,revision,content_hash,created_via,created_at,updated_at)
            VALUES (:id,:student_id,:course_id,:title,:content_md,1,:content_hash,:created_via,:created_at,:updated_at)""", row)

    def update(self, student_id: str, course_id: str, identifier: str, expected_revision: int,
               title: str, content_md: str, content_hash: str, timestamp: str) -> bool:
        cursor = self.db.execute("""UPDATE notes SET title=?,content_md=?,content_hash=?,revision=revision+1,updated_at=?
            WHERE id=? AND student_id=? AND course_id=? AND revision=? AND deleted_at IS NULL""",
            (title, content_md, content_hash, timestamp, identifier, student_id, course_id, expected_revision))
        return cursor.rowcount == 1

    def delete(self, student_id: str, course_id: str, identifier: str, expected_revision: int, timestamp: str) -> bool:
        cursor = self.db.execute("""UPDATE notes SET deleted_at=?,updated_at=?,revision=revision+1
            WHERE id=? AND student_id=? AND course_id=? AND revision=? AND deleted_at IS NULL""",
            (timestamp, timestamp, identifier, student_id, course_id, expected_revision))
        return cursor.rowcount == 1
