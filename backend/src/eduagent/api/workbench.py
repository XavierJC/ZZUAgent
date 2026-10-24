"""Workbench routes: history reads never instantiate a provider client."""

from typing import Annotated
from dataclasses import replace
from fastapi import APIRouter, Query
from eduagent.api.schemas import Identifier
from eduagent.api.knowledge_schemas import SourceRef
from eduagent.api.workbench_schemas import WorkbenchQuestion, WorkbenchRun, SourceOpen, SourcePreview, SavedAnswer, WorkbenchCapabilities
from eduagent.services.workbench import WorkbenchService


def workbench_router(learning_service, courses, enabled, settings):
    router = APIRouter(prefix='/api/v1/students/{student_id}/workbench', tags=['资料学习工作台'])
    # Keep the legacy tutor/guide budget unchanged. The chat limit is explicit
    # and exposed before submission; failed requests are never auto-retried.
    chat_settings = replace(settings, max_tokens=settings.workbench_max_tokens)

    def service(learning):
        def client():
            from eduagent.agent.deepseek import DeepSeekClient
            return DeepSeekClient(chat_settings, json_output=True)
        return WorkbenchService(learning, courses(), enabled, chat_settings, client)

    @router.get('/capabilities', response_model=WorkbenchCapabilities)
    def capabilities(student_id: Identifier):
        with learning_service() as learning:
            learning.snapshot(student_id)
            return dict(provider='DeepSeek', model=settings.model, model_enabled=settings.enabled, retrieval_enabled=enabled,
                        max_output_tokens=chat_settings.max_tokens, max_model_calls=chat_settings.max_calls)

    @router.post('/questions', response_model=WorkbenchRun)
    def ask(student_id: Identifier, body: WorkbenchQuestion):
        with learning_service() as learning:
            return service(learning).ask(student_id, body.model_dump())

    @router.get('/runs', response_model=list[WorkbenchRun])
    def history(student_id: Identifier, limit: Annotated[int, Query(ge=1, le=50)] = 20):
        with learning_service() as learning:
            return service(learning).history(student_id, limit)

    @router.get('/runs/{request_id}', response_model=WorkbenchRun)
    def get(student_id: Identifier, request_id: str):
        with learning_service() as learning:
            return service(learning).get(student_id, request_id)

    @router.post('/sources/open', response_model=SourcePreview)
    def preview(student_id: Identifier, body: SourceOpen):
        with learning_service() as learning:
            return service(learning).preview(student_id, body.model_dump(exclude={'page'}), body.page)

    @router.post('/runs/{request_id}/note', response_model=SavedAnswer)
    def save(student_id: Identifier, request_id: str):
        with learning_service() as learning:
            return service(learning).save_note(student_id, request_id)

    return router
