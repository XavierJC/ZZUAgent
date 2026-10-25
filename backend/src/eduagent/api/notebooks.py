"""Notebook routes compose existing services behind an immutable source scope."""
from dataclasses import replace
from typing import Annotated, Literal
from fastapi import APIRouter
from pydantic import Field, StringConstraints, field_validator

from eduagent.api.schemas import RequestBody, Identifier
from eduagent.api.workbench_schemas import WorkbenchQuestion, SourceOpen
from eduagent.api.personal_bank import SubmitPractice, PracticeDraft
from eduagent.services.personal_bank import PersonalBankService
from eduagent.services.workbench import WorkbenchService
from eduagent.services.study_workspace.notebooks import NotebookService

UUIDText = Annotated[str, StringConstraints(pattern=r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')]
Title = Annotated[str, StringConstraints(min_length=1, max_length=120)]


class CreateNotebook(RequestBody):
    request_id: UUIDText
    id: UUIDText
    title: Title
    description: Annotated[str, StringConstraints(max_length=1000)] = ''

    @field_validator('title')
    @classmethod
    def not_blank(cls, value):
        if not value.strip(): raise ValueError('笔记本名称不能为空')
        return value


class EditNotebook(CreateNotebook):
    expected_revision: Annotated[int, Field(strict=True, ge=1)]
    archived: bool = False


class NotebookRef(RequestBody):
    source_type: Literal['course_material', 'uploaded_document', 'teaching_material', 'personal_note', 'personal_question']
    source_id: Annotated[str, StringConstraints(min_length=1, max_length=128)]
    source_version: Annotated[str, StringConstraints(min_length=1, max_length=100)]


class NotebookSources(RequestBody):
    request_id: UUIDText
    expected_revision: Annotated[int, Field(strict=True, ge=1)]
    sources: Annotated[list[NotebookRef], Field(max_length=150)]


class NotebookQuestion(WorkbenchQuestion):
    expected_revision: Annotated[int, Field(strict=True, ge=1)]


class NotebookOpen(SourceOpen):
    expected_revision: Annotated[int, Field(strict=True, ge=1)]


class NotebookPractice(RequestBody):
    request_id: UUIDText
    question_id: UUIDText
    expected_revision: Annotated[int, Field(strict=True, ge=1)]


def notebooks_router(learning_service, settings, courses, client_factory=None):
    router = APIRouter(prefix='/api/v1/students/{student_id}/notebooks', tags=['学习笔记本'])
    chat_settings = replace(settings.agent, max_tokens=settings.agent.workbench_max_tokens)

    def service(learning):
        def provider():
            from eduagent.agent.deepseek import DeepSeekClient
            return DeepSeekClient(chat_settings, json_output=True)
        workbench = WorkbenchService(learning, courses(), settings.retrieval_enabled, chat_settings, client_factory or provider)
        return NotebookService(learning, workbench, PersonalBankService(learning, settings.data_dir / 'materials'))

    @router.get('')
    def list_notebooks(student_id: Identifier, archived: bool = False):
        with learning_service() as learning: return service(learning).list(student_id, archived)

    @router.post('', status_code=201)
    def create(student_id: Identifier, body: CreateNotebook):
        with learning_service() as learning: return service(learning).create(student_id, body.model_dump())

    @router.get('/requests/{request_id}')
    def receipt(student_id: Identifier, request_id: UUIDText):
        with learning_service() as learning: return service(learning).receipt(student_id, request_id)

    @router.get('/{notebook_id}')
    def get(student_id: Identifier, notebook_id: UUIDText):
        with learning_service() as learning: return service(learning).get(student_id, notebook_id)

    @router.patch('/{notebook_id}')
    def update(student_id: Identifier, notebook_id: UUIDText, body: EditNotebook):
        if body.id != notebook_id: raise ValueError('笔记本编号不匹配')
        with learning_service() as learning: return service(learning).update(student_id, notebook_id, body.model_dump())

    @router.put('/{notebook_id}/sources')
    def sources(student_id: Identifier, notebook_id: UUIDText, body: NotebookSources):
        with learning_service() as learning: return service(learning).set_sources(student_id, notebook_id, body.model_dump())

    @router.post('/{notebook_id}/questions')
    def ask(student_id: Identifier, notebook_id: UUIDText, body: NotebookQuestion):
        with learning_service() as learning: return service(learning).ask(student_id, notebook_id, body.model_dump())

    @router.get('/{notebook_id}/runs')
    def history(student_id: Identifier, notebook_id: UUIDText):
        with learning_service() as learning: return service(learning).history(student_id, notebook_id)

    @router.get('/{notebook_id}/runs/{request_id}')
    def run(student_id: Identifier, notebook_id: UUIDText, request_id: UUIDText):
        with learning_service() as learning: return service(learning).run(student_id, notebook_id, request_id)

    @router.post('/{notebook_id}/runs/{request_id}/note')
    def save(student_id: Identifier, notebook_id: UUIDText, request_id: UUIDText):
        with learning_service() as learning: return service(learning).save_answer(student_id, notebook_id, request_id)

    @router.post('/{notebook_id}/sources/open')
    def preview(student_id: Identifier, notebook_id: UUIDText, body: NotebookOpen):
        with learning_service() as learning: return service(learning).preview(student_id, notebook_id, body.model_dump())

    @router.get('/{notebook_id}/practice/questions')
    def questions(student_id: Identifier, notebook_id: UUIDText):
        with learning_service() as learning: return service(learning).questions(student_id, notebook_id)

    @router.post('/{notebook_id}/practice')
    def practice(student_id: Identifier, notebook_id: UUIDText, body: NotebookPractice):
        with learning_service() as learning: return service(learning).start_practice(student_id, notebook_id, body.model_dump())

    @router.get('/{notebook_id}/practice/questions/{question_id}')
    def question(student_id: Identifier, notebook_id: UUIDText, question_id: UUIDText):
        with learning_service() as learning: return service(learning).question(student_id, notebook_id, question_id)

    @router.get('/{notebook_id}/practice/sessions')
    def practice_history(student_id: Identifier, notebook_id: UUIDText):
        with learning_service() as learning: return service(learning).practice_history(student_id, notebook_id)

    @router.get('/{notebook_id}/practice/requests/{request_id}')
    def practice_receipt(student_id: Identifier, notebook_id: UUIDText, request_id: UUIDText):
        with learning_service() as learning: return service(learning).practice_receipt(student_id, notebook_id, request_id)

    @router.get('/{notebook_id}/practice/sessions/{session_id}')
    def practice_session(student_id: Identifier, notebook_id: UUIDText, session_id: UUIDText):
        with learning_service() as learning: return service(learning).practice_session(student_id, notebook_id, session_id)

    @router.post('/{notebook_id}/practice/sessions/{session_id}/answer')
    def practice_answer(student_id: Identifier, notebook_id: UUIDText, session_id: UUIDText, body: SubmitPractice):
        with learning_service() as learning: return service(learning).submit_practice(student_id, notebook_id, session_id, body.model_dump())

    @router.put('/{notebook_id}/practice/sessions/{session_id}/draft')
    def practice_draft(student_id: Identifier, notebook_id: UUIDText, session_id: UUIDText, body: PracticeDraft):
        with learning_service() as learning: return service(learning).submit_practice(student_id, notebook_id, session_id, body.model_dump(), draft=True)

    return router
