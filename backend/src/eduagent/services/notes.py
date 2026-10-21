"""Personal note CRUD only: no model, retrieval, score or BKT capability."""

from __future__ import annotations

from eduagent.domain import notes as rules
from eduagent.domain.catalog import Catalog
from eduagent.services.learning import StudentNotFound, identifier, now
from eduagent.storage.notes import NoteRepository
from eduagent.storage.sqlite import SQLiteRepository
from eduagent.storage.personal import PersonalRepository
from eduagent.services.note_index import NoteIndexer


class NotesService:
    def __init__(self, catalog: Catalog, repository: SQLiteRepository):
        self.catalog, self.repository = catalog, repository
        self.notes = NoteRepository(repository)
        self.indexer = NoteIndexer(repository)

    def _student(self, student_id: str, course_id: str) -> None:
        identifier(student_id, "学生标识")
        rules.course(course_id)
        if self.repository.student(student_id) is None:
            raise StudentNotFound("学生标识不存在，请先创建学习记录")

    def _links(self, values: list[str]) -> list[str]:
        if (not isinstance(values, list) or len(values) > 5
                or any(not isinstance(value, str) or value not in self.catalog.knowledge for value in values)
                or len(set(values)) != len(values)):
            raise ValueError("关联需为 0～5 个不重复的现有知识点")
        return sorted(values)

    def _get(self, student_id: str, course_id: str, note_id: str):
        row = self.notes.get(student_id, course_id, rules.note_id(note_id))
        if row is None:
            raise rules.NoteNotFound("当前学习标识下没有该笔记")
        return row

    def _view(self, row, detail: bool = True) -> dict:
        result = {key: row[key] for key in (
            "id", "student_id", "course_id", "title", "revision", "content_hash", "created_via", "created_at", "updated_at")}
        state = PersonalRepository(self.repository).state(row["id"])
        result.update(knowledge_point_ids=self.notes.links(row["id"]), index_status=state["status"] if state else "pending",
                      content_bytes=len(row["content_md"].encode("utf-8")))
        if detail:
            result["content_md"] = row["content_md"]
            origin = self.repository.connection.execute('SELECT * FROM workbench_note_origins WHERE note_id=?', (row['id'],)).fetchone()
            result['generation_origin'] = ({'request_id': origin['request_id'], 'generated_at': origin['generated_at'],
                'original_revision': origin['original_revision'], 'edited': row['revision'] != origin['original_revision']
                    or row['content_hash'] != origin['original_hash']} if origin else None)
        return result

    def _quota(self, student_id: str, course_id: str, size_delta: int, creating: bool) -> None:
        count, total = self.notes.usage(student_id, course_id)
        if (creating and count >= rules.MAX_ACTIVE_NOTES) or total + size_delta > rules.MAX_TOTAL_BYTES:
            raise rules.NoteTooLarge("每个学习标识最多保存 50 篇有效笔记，正文合计最多 1 MiB")

    def get(self, student_id: str, note_id: str, course_id: str = rules.COURSE_ID) -> dict:
        with self.repository.transaction():
            self._student(student_id, course_id)
            return self._view(self._get(student_id, course_id, note_id))

    def list(self, student_id: str, *, course_id: str = rules.COURSE_ID, query: str = "",
             knowledge_id: str | None = None, limit: int = 20, offset: int = 0) -> dict:
        if type(limit) is not int or not 1 <= limit <= 50 or type(offset) is not int or offset < 0:
            raise ValueError("笔记分页参数无效")
        if not isinstance(query, str) or len(query) > 100:
            raise ValueError("标题查询最多 100 字符")
        if knowledge_id is not None and knowledge_id not in self.catalog.knowledge:
            raise ValueError("筛选知识点不存在")
        with self.repository.transaction():
            self._student(student_id, course_id)
            rows, total = self.notes.list(student_id, course_id, query, knowledge_id, limit, offset)
            return {"items": [self._view(row, False) for row in rows], "total": total, "limit": limit, "offset": offset}

    def create(self, student_id: str, *, id: str, title: str, content_md: str,
               knowledge_point_ids: list[str], course_id: str = rules.COURSE_ID, created_via: str = "manual",
               _on_create=None) -> tuple[dict, bool]:
        note_id, heading, body = rules.note_id(id), rules.title(title), rules.content(content_md)
        links = self._links(knowledge_point_ids)
        if created_via not in ("manual", "import"):
            raise ValueError("笔记创建来源无效")
        with self.repository.transaction():
            self._student(student_id, course_id)
            existing = self.notes.get(student_id, course_id, note_id)
            if existing is not None:
                if (existing["revision"] == 1 and existing["title"] == heading and existing["content_md"] == body
                        and self.notes.links(note_id) == links and existing["created_via"] == created_via):
                    return self._view(existing), True
                raise rules.NoteConflict("该编号已有不同或更新的笔记，请读取服务器版本后处理")
            if self.notes.id_used(note_id):
                raise rules.NoteConflict("该笔记编号已使用，请为新笔记生成新的编号")
            self._quota(student_id, course_id, len(body.encode("utf-8")), True)
            timestamp = now()
            self.notes.insert(dict(id=note_id, student_id=student_id, course_id=course_id, title=heading,
                                   content_md=body, content_hash=rules.content_hash(body), created_via=created_via,
                                   created_at=timestamp, updated_at=timestamp))
            self.notes.set_links(note_id, links)
            PersonalRepository(self.repository).invalidate(note_id, 1, timestamp)
            # Internal transaction hook: workbench provenance commits with the
            # original note. Never accepted from the public note request body.
            if _on_create:
                _on_create(note_id, rules.content_hash(body), timestamp)
        self._build(student_id, note_id, 1)
        return self.get(student_id, note_id, course_id), False

    def update(self, student_id: str, note_id: str, expected_revision: int, changes: dict,
               course_id: str = rules.COURSE_ID) -> dict:
        rules.revision(expected_revision)
        if not changes or set(changes) - {"title", "content_md", "knowledge_point_ids"}:
            raise ValueError("更新必须提供标题、正文或关联知识点；其他字段不能修改")
        with self.repository.transaction():
            self._student(student_id, course_id)
            current = self._get(student_id, course_id, note_id)
            if current["revision"] != expected_revision:
                raise rules.NoteConflict("笔记已被更新，本地内容已保留，请先读取服务器版本")
            heading = rules.title(changes.get("title", current["title"]))
            body = rules.content(changes.get("content_md", current["content_md"]))
            old_links = self.notes.links(note_id)
            links = self._links(changes.get("knowledge_point_ids", old_links))
            if (heading, body, links) == (current["title"], current["content_md"], old_links):
                return self._view(current)
            self._quota(student_id, course_id, len(body.encode("utf-8")) - len(current["content_md"].encode("utf-8")), False)
            timestamp = now()
            if not self.notes.update(student_id, course_id, note_id, expected_revision, heading, body, rules.content_hash(body), timestamp):
                raise rules.NoteConflict("笔记版本冲突")
            self.notes.set_links(note_id, links)
            PersonalRepository(self.repository).invalidate(note_id, expected_revision + 1, timestamp)
        self._build(student_id, note_id, expected_revision + 1)
        return self.get(student_id, note_id, course_id)

    def delete(self, student_id: str, note_id: str, expected_revision: int, course_id: str = rules.COURSE_ID) -> None:
        rules.revision(expected_revision)
        with self.repository.transaction():
            self._student(student_id, course_id)
            current = self._get(student_id, course_id, note_id)
            if current["revision"] != expected_revision:
                raise rules.NoteConflict("笔记已更新，请核对最新版本后再删除")
            timestamp = now()
            if not self.notes.delete(student_id, course_id, note_id, expected_revision, timestamp):
                raise rules.NoteConflict("笔记版本冲突")
            PersonalRepository(self.repository).invalidate(note_id, expected_revision + 1, timestamp, deleted=True)

    def _build(self, student_id, note_id, expected_revision):
        # The original Markdown transaction is already committed. A newer save
        # may supersede this build without letting its chunks overwrite it.
        try:
            self.indexer.rebuild(student_id, note_id, expected_revision)
        except (rules.NoteConflict, rules.NoteNotFound):
            pass

    def import_note(self, student_id: str, *, id: str, file_name: str, content_base64: str,
                    knowledge_point_ids: list[str], title: str | None = None, course_id: str = rules.COURSE_ID) -> tuple[dict, bool]:
        default_title, body, warnings = rules.decode_import(file_name, content_base64)
        note, replayed = self.create(student_id, id=id, title=default_title if title is None else title,
                                     content_md=body, knowledge_point_ids=knowledge_point_ids, course_id=course_id,
                                     created_via="import")
        return {**note, "import_warnings": warnings}, replayed
