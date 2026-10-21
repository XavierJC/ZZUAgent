from typing import Annotated
from fastapi import APIRouter, Query
from eduagent.api.schemas import Identifier
from eduagent.api.study_guide_schemas import GenerateGuide, GuideRun, LearningGuidance
from eduagent.services.guidance import GuidanceService
from eduagent.services.study_guides import StudyGuideService


def study_guides_router(learning_service, courses, enabled, settings):
    router = APIRouter(prefix='/api/v1/students/{student_id}', tags=['学习建议与指南'])
    def service(learning):
        def client():
            from eduagent.agent.deepseek import DeepSeekClient
            return DeepSeekClient(settings)
        return StudyGuideService(learning, courses(), enabled, settings, client)

    @router.get('/learning-guidance', response_model=LearningGuidance)
    def guidance(student_id: Identifier):
        with learning_service() as learning:
            return GuidanceService(learning).snapshot(student_id)

    @router.post('/study-guides', response_model=GuideRun)
    def generate(student_id: Identifier, body: GenerateGuide):
        with learning_service() as learning:
            return service(learning).generate(student_id, body.model_dump())

    @router.get('/study-guides', response_model=list[GuideRun])
    def history(student_id: Identifier, limit: Annotated[int, Query(ge=1, le=50)] = 20):
        with learning_service() as learning:
            return service(learning).history(student_id, limit)

    @router.get('/study-guides/{request_id}', response_model=GuideRun)
    def get(student_id: Identifier, request_id: str):
        with learning_service() as learning:
            return service(learning).get(student_id, request_id)

    return router
