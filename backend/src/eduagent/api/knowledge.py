"""Local-only retrieval routes; never instantiate an Agent or model client."""

from fastapi import APIRouter

from eduagent.api.schemas import Identifier
from eduagent.api.knowledge_schemas import KnowledgeQuery, KnowledgeResults, SourceList, IndexState, ReindexNote, Course
from eduagent.services.knowledge import KnowledgeService
from eduagent.services.note_index import NoteIndexer


def knowledge_router(learning_service, course_sources, enabled):
    router = APIRouter(prefix='/api/v1/students/{student_id}', tags=['本地知识检索'])

    @router.get('/knowledge/sources', response_model=SourceList)
    def sources(student_id: Identifier, course_id: Course = 'machine_learning'):
        with learning_service() as learning:
            return KnowledgeService(learning.catalog, learning.repository, course_sources(), enabled).sources(student_id, course_id)

    @router.post('/knowledge/search', response_model=KnowledgeResults)
    def search(student_id: Identifier, body: KnowledgeQuery):
        with learning_service() as learning:
            return KnowledgeService(learning.catalog, learning.repository, course_sources(), enabled).search(student_id, **body.model_dump())

    @router.post('/notes/{note_id}/reindex', response_model=IndexState)
    def reindex(student_id: Identifier, note_id: str, body: ReindexNote):
        with learning_service() as learning:
            KnowledgeService(learning.catalog, learning.repository).student(student_id, 'machine_learning')
            return NoteIndexer(learning.repository).rebuild(student_id, note_id, body.expected_revision)

    return router
