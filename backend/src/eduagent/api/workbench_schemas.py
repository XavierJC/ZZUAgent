"""Independent Phase 3B contract; does not change legacy tutor responses."""

from typing import Annotated, Literal
from pydantic import BaseModel, Field, StringConstraints
from eduagent.api.schemas import RequestBody
from eduagent.api.knowledge_schemas import SourceRef, KnowledgeCitation, Course


class WorkbenchQuestion(RequestBody):
    request_id: str
    question: Annotated[str, StringConstraints(min_length=1, max_length=1000)]
    sources: Annotated[list[SourceRef], Field(min_length=1, max_length=55)]
    course_id: Course = 'machine_learning'
    mode: Literal['local', 'model'] = 'local'
    allow_personal_external: bool = False
    allow_teacher_external: bool = False


class CapturedSource(SourceRef):
    title: str


class SourceStatus(SourceRef):
    current_status: Literal['current', 'modified', 'deleted', 'unavailable']


class RunContext(BaseModel):
    student_id: str
    course_id: Course
    request_id: str
    sources: list[SourceRef]
    allow_personal_external: bool
    state_revision: int
    allow_teacher_external: bool = False


class ToolUse(BaseModel):
    name: str
    status: str
    citation_ids: list[str]


class Usage(BaseModel):
    prompt_tokens: int
    completion_tokens: int


class ValidationSummary(BaseModel):
    root_type: Literal['object', 'array', 'other']
    recognized_fields: list[str]
    unknown_field_count: Annotated[int, Field(ge=0)]


class WorkbenchRun(BaseModel):
    request_id: str
    course_id: Course
    question: str
    status: Literal['complete', 'local', 'uncertain', 'stale', 'failed']
    answer: str
    answer_basis: Literal['selected_sources', 'mixed', 'model_knowledge', 'local_excerpts', 'none'] = 'none'
    validation_error: str | None = None
    validation_summary: ValidationSummary | None = None
    supplement_md: str = ''
    finish_reason: Literal['length', 'content_filter', 'insufficient_system_resource', 'aborted'] | None = None
    max_output_tokens: int | None = None
    citations: list[KnowledgeCitation]
    selected_sources: list[CapturedSource]
    source_statuses: list[SourceStatus]
    context: RunContext
    model: str | None
    provider: str | None
    model_calls: int
    tools_used: list[ToolUse]
    usage: Usage
    reason: str | None
    saved_note_id: str | None
    created_at: str
    updated_at: str


class SourcePreview(SourceRef):
    title: str
    raw_md: str


class SavedAnswer(BaseModel):
    note_id: str
    revision: int
    deleted: bool
    edited: bool
    request_id: str
    generated_at: str


class WorkbenchCapabilities(BaseModel):
    provider: Literal['DeepSeek']
    model: str
    model_enabled: bool
    retrieval_enabled: bool
    max_output_tokens: int = 1500
    max_model_calls: int = 3
