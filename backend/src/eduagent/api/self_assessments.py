from typing import Annotated
from fastapi import APIRouter, Query, Response
from eduagent.api.schemas import Identifier
from eduagent.api.knowledge_schemas import Course
from eduagent.api.self_assessment_schemas import SaveAssessments, LatestAssessments, AssessmentHistory, AssessmentReceipt
from eduagent.services.self_assessments import SelfAssessmentService


def self_assessments_router(learning_service):
    router = APIRouter(prefix='/api/v1/students/{student_id}/self-assessments', tags=['学习自评'])

    @router.get('/latest', response_model=LatestAssessments)
    def latest(student_id: Identifier, course_id: Course = 'machine_learning'):
        with learning_service() as learning:
            return SelfAssessmentService(learning).latest(student_id, course_id)

    @router.post('', response_model=AssessmentReceipt, status_code=201)
    def save(student_id: Identifier, body: SaveAssessments, response: Response):
        with learning_service() as learning:
            result = SelfAssessmentService(learning).save(student_id, **body.model_dump())
            response.status_code = 200 if result['replayed'] else 201
            return result

    @router.get('', response_model=AssessmentHistory)
    def history(student_id: Identifier, course_id: Course = 'machine_learning', knowledge_id: str | None = None,
                limit: Annotated[int, Query(ge=1, le=50)] = 20, offset: Annotated[int, Query(ge=0)] = 0):
        with learning_service() as learning:
            return SelfAssessmentService(learning).history(student_id, course_id, knowledge_id, limit, offset)

    @router.get('/requests/{request_id}', response_model=AssessmentReceipt)
    def receipt(student_id: Identifier, request_id: str, course_id: Course = 'machine_learning'):
        with learning_service() as learning:
            return SelfAssessmentService(learning).receipt(student_id, request_id, course_id)

    return router
