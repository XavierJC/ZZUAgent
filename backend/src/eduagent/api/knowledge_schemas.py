"""Strict Phase 3A local-only source/search contracts."""

from typing import Annotated, Literal
from pydantic import BaseModel, Field, StringConstraints

from eduagent.api.schemas import RequestBody

SourceType = Literal['course_material', 'personal_note', 'teaching_material', 'uploaded_document']
IndexStatus = Literal['disabled', 'pending', 'building', 'ready', 'empty', 'failed']
Course = Literal['machine_learning']


class SourceRef(RequestBody):
    source_type: SourceType
    source_id: Annotated[str, StringConstraints(min_length=1, max_length=128)]
    source_version: Annotated[str, StringConstraints(min_length=1, max_length=100)]


class KnowledgeQuery(RequestBody):
    query: Annotated[str, StringConstraints(min_length=1, max_length=1000)]
    sources: Annotated[list[SourceRef], Field(min_length=1, max_length=55)]
    course_id: Course = 'machine_learning'
    knowledge_id: str | None = None
    top_k: Annotated[int, Field(ge=1, le=5)] = 3


class ReindexNote(RequestBody):
    expected_revision: Annotated[int, Field(ge=1)]


class IndexState(BaseModel):
    note_id: str
    status: IndexStatus
    target_revision: int
    indexed_revision: int | None
    indexed_hash: str | None
    indexer_version: str | None
    chunk_count: int
    error_code: str | None
    updated_at: str


class SourceSummary(SourceRef):
    file_format: str | None = None
    readable_units: int | None = None
    total_units: int | None = None
    document_id: str | None = None
    version_id: str | None = None
    run_id: str | None = None
    source_revision: int | None
    content_hash: str
    title: str
    knowledge_point_ids: list[str]
    review_status: Literal['pending', 'human_verified', 'personal_unverified', 'document_unverified']
    index_status: IndexStatus
    error_code: str | None


class SourceList(BaseModel):
    course_id: Course
    retrieval_enabled: bool
    items: list[SourceSummary]


class KnowledgeCitation(BaseModel):
    file_format: str | None = None
    document_id: str | None = None
    version_id: str | None = None
    page_number: int | None = None
    concept_id: str | None = None
    architecture_id: str | None = None
    architecture_version: int | None = None
    excerpt_origin: str | None = None
    original_text_snapshot: str | None = None
    source_type: SourceType
    source_id: str
    source_version: str
    source_revision: int | None
    content_hash: str
    chunk_hash: str
    chunk_id: str
    citation_id: str
    title: str
    section: str
    knowledge_point_ids: list[str]
    review_status: Literal['pending', 'human_verified', 'personal_unverified', 'document_unverified']
    raw_md: str
    content_text: str
    start_offset: int
    end_offset: int
    start_line: int
    end_line: int
    retrieval_score: float
    fusion_score: float | None


class KnowledgeResults(BaseModel):
    course_id: Course
    query: str
    sources: list[SourceRef]
    items: list[KnowledgeCitation]
    model_calls: Literal[0]
    retrieval_policy: str
    fusion: str | None
