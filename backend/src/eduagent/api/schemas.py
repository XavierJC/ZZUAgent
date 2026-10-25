"""HTTP contracts: client data never owns scores or mastery probabilities."""

from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

from eduagent.services.learning import identifier
from eduagent.domain.models import SubmissionResult


def validate_identifier(value: str) -> str:
    return identifier(value, "标识")


Identifier = Annotated[
    str, StringConstraints(strict=True, min_length=1, max_length=128),
    AfterValidator(validate_identifier),
]


class RequestBody(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class StartLearning(RequestBody):
    student_id: Identifier
    goals: Annotated[list[Identifier], Field(min_length=1, max_length=5)] | None = None


class AnswerSubmission(RequestBody):
    decision_id: Identifier
    event_id: Identifier
    answer: Annotated[str, StringConstraints(min_length=1, max_length=16)]


class TutorQuestion(RequestBody):
    question: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class RetrievalQuery(RequestBody):
    query: Annotated[str, StringConstraints(min_length=1, max_length=1000)]
    knowledge_id: str | None = None


class CitationResponse(BaseModel):
    citation_id: str
    knowledge_id: str
    title: str
    section: str
    source: str
    content: str
    review_status: Literal["pending", "human_verified"]
    score: float


class PublicQuestion(BaseModel):
    # This explicit allowlist remains safe even if a future domain object grows fields.
    id: str
    version: str
    knowledge_id: str
    difficulty: Literal["easy", "medium", "hard"]
    stem: str
    options: dict[str, str]
    source: str
    review_status: Literal["pending", "human_verified", "ai_checked"]


class DecisionResponse(BaseModel):
    decision_id: str
    student_id: str
    revision: int
    action: Literal["diagnose", "review", "practice", "advance", "finish", "stopped"]
    knowledge_id: str | None
    reason: str
    evidence: dict[str, Any]
    question: PublicQuestion | None = None
    stop_reason: str | None = None


class MasteryItem(BaseModel):
    knowledge_id: str
    name: str
    probability: float
    attempts: int
    last_correct: bool | None
    has_evidence: bool


class MasteryResponse(BaseModel):
    student_id: str
    goals: list[str]
    revision: int
    mode: Literal["offline_rules"] = "offline_rules"
    threshold: float
    parameter_version: str
    mastery: list[MasteryItem]


class KnowledgePointResponse(BaseModel):
    id: str
    name: str
    prerequisites: list[str]
    review_tip: str


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    version: str
    mode: Literal["offline_rules"] = "offline_rules"
    question_count: int
    pending_review_count: int
    ai_checked_count: int | None = None
    agent_enabled: bool = False
    retrieval_available: bool = False


class HistoryResponse(BaseModel):
    student_id: str
    revision: int
    items: list[SubmissionResult]


class ToolTrace(BaseModel):
    name: str
    status: Literal["ok", "invalid"]
    citation_ids: list[str]


class TutorResponse(BaseModel):
    run_id: str
    student_id: str
    mode: Literal["deepseek", "offline_fallback"]
    model: str | None
    model_calls: int
    retrieval_policy: str | None = None
    usage: dict[str, int]
    state_revision: int
    answer: str
    citations: list[CitationResponse]
    tools_used: list[ToolTrace]
    fallback_reason: str | None
    next_exercise: DecisionResponse | None
