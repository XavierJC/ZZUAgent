"""Independent rule suggestions and guide receipts, with explicit fact types."""

from typing import Annotated, Literal
from pydantic import BaseModel, Field, model_validator
from eduagent.api.schemas import RequestBody
from eduagent.api.self_assessment_schemas import AssessmentRecord
from eduagent.api.knowledge_schemas import Course, SourceRef, KnowledgeCitation
from eduagent.api.workbench_schemas import SourceStatus, Usage, ToolUse


class ObjectiveEvidence(BaseModel):
    has_evidence: bool
    probability: float | None
    prior_probability: float
    attempts: int
    last_correct: bool | None
    meets_progress_condition: bool


class RecentEvidence(BaseModel):
    event_id: str
    question_id: str
    correct: bool
    created_at: str
    learning_revision: int


class GuidanceAction(BaseModel):
    kind: Literal['open_formal_practice', 'open_learning_history']
    knowledge_id: str


class GuidancePoint(BaseModel):
    knowledge_id: str
    name: str
    prerequisites: list[str]
    in_goal_path: bool
    self_report: AssessmentRecord | None
    recent_attempts: list[RecentEvidence]
    objective: ObjectiveEvidence
    available_questions: int
    round_limit_reached: bool
    blocked_by: list[str]
    reason_codes: list[str]
    reasons: list[str]
    status: Literal['pending_diagnosis', 'needs_review', 'meets_demo_condition']
    actions: list[GuidanceAction]


class RankedPoint(GuidancePoint):
    priority: int


class EvidenceVersions(BaseModel):
    bkt: str
    policy: str
    knowledge: str
    catalog: str
    bank: str


class LearningGuidance(BaseModel):
    course_id: Course
    learning_revision: int
    assessment_revision: int
    rule_version: str
    threshold: float
    goals: list[str]
    goal_names: list[str]
    items: list[GuidancePoint]
    recommendations: list[RankedPoint]
    versions: EvidenceVersions
    snapshot_hash: str


class GenerateGuide(RequestBody):
    request_id: str
    course_id: Course = 'machine_learning'
    expected_learning_revision: Annotated[int, Field(ge=0)]
    expected_assessment_revision: Annotated[int, Field(ge=0)]
    mode: Literal['rules', 'model'] = 'rules'
    sources: Annotated[list[SourceRef], Field(max_length=55)] = Field(default_factory=list)
    allow_personal_external: bool = False

    @model_validator(mode='after')
    def model_requires_sources(self):
        if self.mode == 'model' and not self.sources:
            raise ValueError('模型模式必须明确选择来源，不能自动查询全库')
        return self


class GuideRun(BaseModel):
    request_id: str
    course_id: Course
    status: Literal['complete', 'local', 'uncertain', 'stale', 'failed']
    snapshot: LearningGuidance
    rules_md: str
    explanation_md: str
    citations: list[KnowledgeCitation]
    sources: list[SourceRef]
    source_statuses: list[SourceStatus]
    stale_reasons: list[str]
    reason: str | None
    model: str | None
    model_calls: int
    usage: Usage
    tools_used: list[ToolUse]
    created_at: str
    updated_at: str
