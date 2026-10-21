"""Student-scoped routes. Connections are opened inside each sync handler."""

from typing import Annotated, Literal

from fastapi import APIRouter, Query, Response

from eduagent.api.note_schemas import CreateNote, UpdateNote, ImportNote, NoteDetail, ImportedNote, NoteList
from eduagent.api.schemas import Identifier
from eduagent.services.notes import NotesService

CourseQuery = Literal["machine_learning"]


def notes_router(learning_service) -> APIRouter:
    router = APIRouter(prefix="/api/v1/students/{student_id}/notes", tags=["个人笔记"])

    @router.get("", response_model=NoteList)
    def list_notes(student_id: Identifier, course_id: CourseQuery = "machine_learning",
                   q: Annotated[str, Query(max_length=100)] = "", knowledge_id: str | None = None,
                   limit: Annotated[int, Query(ge=1, le=50)] = 20, offset: Annotated[int, Query(ge=0)] = 0):
        with learning_service() as learning:
            return NotesService(learning.catalog, learning.repository).list(
                student_id, course_id=course_id, query=q, knowledge_id=knowledge_id, limit=limit, offset=offset)

    @router.post("", response_model=NoteDetail, status_code=201)
    def create_note(student_id: Identifier, body: CreateNote, response: Response):
        with learning_service() as learning:
            note, replayed = NotesService(learning.catalog, learning.repository).create(student_id, **body.model_dump())
            response.status_code = 200 if replayed else 201
            return note

    @router.post("/import", response_model=ImportedNote, status_code=201)
    def import_note(student_id: Identifier, body: ImportNote, response: Response):
        with learning_service() as learning:
            note, replayed = NotesService(learning.catalog, learning.repository).import_note(student_id, **body.model_dump())
            response.status_code = 200 if replayed else 201
            return note

    @router.get("/{note_id}", response_model=NoteDetail)
    def get_note(student_id: Identifier, note_id: str, course_id: CourseQuery = "machine_learning"):
        with learning_service() as learning:
            return NotesService(learning.catalog, learning.repository).get(student_id, note_id, course_id)

    @router.patch("/{note_id}", response_model=NoteDetail)
    def update_note(student_id: Identifier, note_id: str, body: UpdateNote, course_id: CourseQuery = "machine_learning"):
        changes = body.model_dump(exclude_unset=True, exclude={"expected_revision"})
        with learning_service() as learning:
            return NotesService(learning.catalog, learning.repository).update(
                student_id, note_id, body.expected_revision, changes, course_id)

    @router.delete("/{note_id}", status_code=204)
    def delete_note(student_id: Identifier, note_id: str, expected_revision: Annotated[int, Query(ge=1)],
                    course_id: CourseQuery = "machine_learning"):
        with learning_service() as learning:
            NotesService(learning.catalog, learning.repository).delete(student_id, note_id, expected_revision, course_id)
        return Response(status_code=204)

    return router
