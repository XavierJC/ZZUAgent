import base64
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from threading import Barrier
from uuid import uuid4

import pytest

from eduagent.domain.notes import NoteConflict, NoteNotFound, NoteTooLarge, MAX_NOTE_BYTES, decode_import
from eduagent.services.learning import LearningService
from eduagent.services.notes import NotesService
from eduagent.storage.migrations import fact_snapshot
from eduagent.storage.sqlite import SQLiteRepository


@pytest.fixture
def notes(service):
    return NotesService(service.catalog, service.repository)


def payload(**changes):
    return {"id": str(uuid4()), "title": "梯度笔记", "content_md": "# 梯度下降\n\n$w=w-\\alpha g$",
            "knowledge_point_ids": ["gradient_descent", "linear_regression_loss"], **changes}


def test_crud_replay_multiple_links_and_learning_facts_remain_unchanged(service, notes):
    decision = service.next_action("student-a")
    service.submit("student-a", decision.decision_id, "B", "before-notes")
    before = fact_snapshot(service.repository.connection)
    data = payload()
    first, replayed = notes.create("student-a", **data)
    assert not replayed and first["revision"] == 1 and first["index_status"] == "ready"
    assert first["content_hash"] == sha256(data["content_md"].encode()).hexdigest()
    assert notes.create("student-a", **data) == (first, True)
    assert notes.list("student-a")["total"] == 1
    assert "content_md" not in notes.list("student-a")["items"][0]
    edited = notes.update("student-a", first["id"], 1, {"title": "更新标题", "content_md": "**新内容** $x^2$"})
    assert edited["revision"] == 2 and edited["created_at"] == first["created_at"]
    assert notes.update("student-a", first["id"], 2, {"content_md": edited["content_md"]}) == edited
    with pytest.raises(NoteConflict):
        notes.update("student-a", first["id"], 1, {"content_md": "旧内容"})
    with pytest.raises(NoteConflict):
        notes.delete("student-a", first["id"], 1)
    assert notes.get("student-a", first["id"])["content_md"] == edited["content_md"]
    notes.delete("student-a", first["id"], 2)
    assert notes.list("student-a")["items"] == []
    with pytest.raises(NoteNotFound):
        notes.get("student-a", first["id"])
    with pytest.raises(NoteConflict):
        notes.create("student-a", **data)  # A replay cannot resurrect a tombstone.
    assert fact_snapshot(service.repository.connection) == before


def test_scope_title_literal_filter_knowledge_filter_and_restore(notes, service):
    service.register("student-b")
    first, _ = notes.create("student-a", **payload(title="100%_完成"))
    notes.create("student-a", **payload(title="100其他完成", knowledge_point_ids=[]))
    notes.create("student-b", **payload(title="100%_完成", content_md="另一个学生"))
    assert notes.list("student-a", query="%_")["total"] == 1
    assert notes.list("student-a", knowledge_id="gradient_descent")["total"] == 1
    assert notes.list("student-a", limit=1, offset=1)["items"]
    assert notes.list("student-b")["total"] == 1
    for operation in (lambda: notes.get("student-b", first["id"]),
                      lambda: notes.update("student-b", first["id"], 1, {"title": "偷改"}),
                      lambda: notes.delete("student-b", first["id"], 1)):
        with pytest.raises(NoteNotFound):
            operation()
    db_file = service.repository.connection.execute("PRAGMA database_list").fetchone()[2]
    with SQLiteRepository(db_file) as restored:
        assert NotesService(service.catalog, restored).get("student-a", first["id"]) == first


@pytest.mark.parametrize("changes", [
    {"id": "not-a-uuid"}, {"title": " "}, {"content_md": "\x00"}, {"content_md": "\ud800"},
    {"knowledge_point_ids": ["unknown"]}, {"knowledge_point_ids": ["gradient_descent"] * 2},
    {"course_id": "another"},
])
def test_invalid_note_input_does_not_create_partial_data(notes, changes):
    with pytest.raises(ValueError):
        notes.create("student-a", **payload(**changes))
    assert notes.list("student-a")["total"] == 0


def test_per_note_and_active_collection_quotas_are_enforced(notes):
    with pytest.raises(NoteTooLarge):
        notes.create("student-a", **payload(content_md="中" * (MAX_NOTE_BYTES // 3 + 1)))
    for position in range(50):
        notes.create("student-a", **payload(title=str(position), content_md=""))
    with pytest.raises(NoteTooLarge):
        notes.create("student-a", **payload())


def test_total_utf8_budget_and_update_budget(notes):
    for _ in range(16):
        notes.create("student-a", **payload(content_md="x" * MAX_NOTE_BYTES))
    empty, _ = notes.create("student-a", **payload(content_md=""))
    with pytest.raises(NoteTooLarge):
        notes.update("student-a", empty["id"], 1, {"content_md": "x"})
    assert notes.get("student-a", empty["id"])["revision"] == 1


def test_link_failure_rolls_back_entire_note(service, notes):
    service.repository.connection.execute("""CREATE TRIGGER fail_note_link BEFORE INSERT ON note_knowledge_points
        BEGIN SELECT RAISE(ABORT,'synthetic link failure'); END""")
    import sqlite3
    with pytest.raises(sqlite3.IntegrityError):
        notes.create("student-a", **payload())
    assert notes.list("student-a")["total"] == 0
    assert service.repository.connection.execute("SELECT count(*) FROM note_index_state").fetchone()[0] == 0


def test_concurrent_updates_have_exactly_one_winner(notes, service):
    first, _ = notes.create("student-a", **payload())
    path = service.repository.connection.execute("PRAGMA database_list").fetchone()[2]
    barrier = Barrier(2)
    def update(text):
        with SQLiteRepository(path) as repository:
            candidate = NotesService(service.catalog, repository)
            barrier.wait()
            try:
                return candidate.update("student-a", first["id"], 1, {"content_md": text})
            except NoteConflict:
                return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(update, ["first", "second"]))
    winners = [result for result in results if result is not None]
    assert len(winners) == 1 and notes.get("student-a", first["id"]) == winners[0]
    assert winners[0]["revision"] == 2


@pytest.mark.parametrize("name,raw", [("file.md", b"%PDF-pretend"), ("file.txt", b"PK\x03\x04data"),
    ("file.txt", b"\xffinvalid"), ("file.txt", b"NUL\x00data"), ("../file.md", b"text"),
    ("C:\\private.md", b"text"), ("file.png", b"text"), ("file.md", b"x" * (MAX_NOTE_BYTES + 1))],
    ids=["pdf", "zip", "invalid-utf8", "nul", "relative-path", "windows-path", "extension", "too-large"])
def test_import_validates_real_content_encoding_size_and_file_name(name, raw):
    with pytest.raises(ValueError):
        decode_import(name, base64.b64encode(raw).decode())


def test_utf8_import_is_replayable_and_reports_normalization(notes):
    data = dict(id=str(uuid4()), file_name="机器学习.MD", knowledge_point_ids=["gradient_descent"],
                content_base64=base64.b64encode(b"\xef\xbb\xbf# title\r\n$x$\r\n").decode())
    note, replayed = notes.import_note("student-a", **data)
    assert not replayed and note["title"] == "机器学习"
    assert note["content_md"] == "# title\n$x$\n" and note["created_via"] == "import"
    assert len(note["import_warnings"]) == 2
    assert notes.import_note("student-a", **data) == (note, True)


def test_long_import_name_has_a_bounded_default_title_and_invalid_unicode_is_rejected():
    heading, body, warnings = decode_import("学" * 130 + ".md", base64.b64encode(b"text").decode())
    assert heading == "学" * 120 and body == "text" and len(warnings) == 1
    from eduagent.domain.notes import title
    with pytest.raises(ValueError, match="Unicode"):
        title("bad\ud800title")
