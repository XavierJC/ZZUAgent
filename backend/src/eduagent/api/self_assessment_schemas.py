"""Subjective report input never accepts objective state or client time."""

from typing import Annotated
from pydantic import BaseModel, Field
from eduagent.api.schemas import RequestBody
from eduagent.api.knowledge_schemas import Course


class AssessmentInput(RequestBody):
    knowledge_id: str
    level: Annotated[int, Field(ge=1, le=4)]
    confidence: Annotated[int, Field(ge=1, le=5)] | None = None


class SaveAssessments(RequestBody):
    request_id: str
    course_id: Course = 'machine_learning'
    expected_revision: Annotated[int, Field(ge=0)]
    items: Annotated[list[AssessmentInput], Field(min_length=1, max_length=5)]


class AssessmentRecord(BaseModel):
    id: str
    batch_id: str
    student_id: str
    course_id: Course
    knowledge_id: str
    level: int
    confidence: int | None
    assessment_revision: int
    learning_revision_at_save: int
    created_at: str


class AssessmentSlot(BaseModel):
    knowledge_id: str
    assessment: AssessmentRecord | None


class LatestAssessments(BaseModel):
    course_id: Course
    assessment_revision: int
    items: list[AssessmentSlot]


class AssessmentReceipt(BaseModel):
    request_id: str
    course_id: Course
    committed_revision: int
    current_revision: int
    learning_revision_at_save: int
    created_at: str
    replayed: bool
    items: list[AssessmentRecord]


class AssessmentHistory(BaseModel):
    course_id: Course
    assessment_revision: int
    items: list[AssessmentRecord]
    limit: int
    offset: int
