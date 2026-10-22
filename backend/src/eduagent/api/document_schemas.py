"""Strict independent Phase4B-1 upload/parse contracts."""

from typing import Annotated, Literal, Any
from pydantic import BaseModel, Field, AfterValidator, StringConstraints, model_validator
from eduagent.api.schemas import RequestBody
from eduagent.documents.models import uuid_text

UUIDText = Annotated[str, AfterValidator(uuid_text)]
Title = Annotated[str, StringConstraints(min_length=1, max_length=120, strip_whitespace=True)]
Revision = Annotated[int, Field(ge=1)]


class UploadDocument(RequestBody):
    request_id: UUIDText
    course_id: Literal['machine_learning'] = 'machine_learning'
    title: Title
    material_role: Literal['teaching_slides', 'textbook', 'framework', 'handout'] = 'teaching_slides'
    source_note: Annotated[str, StringConstraints(max_length=500)] = ''
    local_rights_confirmed: bool

    @model_validator(mode='after')
    def rights(self):
        if self.local_rights_confirmed is not True:
            raise ValueError('请确认有权本地保存与处理该资料')
        return self


class Mutation(RequestBody):
    request_id: UUIDText
    expected_revision: Revision


class UploadVersion(Mutation):
    course_id: Literal['machine_learning'] = 'machine_learning'


class UpdateDocument(Mutation):
    title: Title | None = None
    source_note: Annotated[str, StringConstraints(max_length=500)] | None = None

    @model_validator(mode='after')
    def changed(self):
        if self.title is None and self.source_note is None:
            raise ValueError('至少修改标题或来源说明')
        return self


class VisionRequest(Mutation):
    version_id: UUIDText
    pages: Annotated[list[Annotated[int, Field(ge=1, le=200)]], Field(min_length=1, max_length=3)]
    consent_external: bool = False


class DocumentVersion(BaseModel):
    id: str
    document_id: str
    file_revision: int
    file_name: str
    format: Literal['pdf', 'pptx', 'md', 'txt', 'png', 'jpg', 'jpeg', 'webp']
    size_bytes: int
    content_hash: str
    created_at: str


class DocumentRun(BaseModel):
    id: str
    document_id: str
    version_id: str
    generation: int
    mode: Literal['local', 'vision']
    status: Literal['pending', 'processing', 'ready', 'partial', 'empty', 'failed', 'superseded', 'uncertain']
    current_status: Literal['current', 'modified']
    parser_version: str
    pages: list[int]
    unit_count: int
    warnings: list[str]
    error_code: str | None
    model_calls: int
    usage: dict[str, int]
    model: str | None
    max_output_tokens: int | None
    created_at: str
    updated_at: str


class CourseDocument(BaseModel):
    id: str
    course_id: str
    title: str
    material_role: str
    source_note: str
    revision: int
    created_at: str
    updated_at: str
    source_type: Literal['teaching_material']
    review_status: Literal['imported_unverified']
    local_rights_confirmed: bool
    index_status: Literal['not_implemented']
    version: DocumentVersion
    parse: DocumentRun


class DocumentList(BaseModel):
    course_id: str
    items: list[CourseDocument]


class DocumentUnit(BaseModel):
    id: str
    ordinal: int
    kind: str
    title: str
    text: str
    content_md: str
    interpretation_md: str
    origin: Literal['local_extraction', 'deepseek_vision']
    content_hash: str
    location: dict[str, Any]
    blocks: list[dict[str, Any]]
    warnings: list[str]


class UnitList(BaseModel):
    run: DocumentRun
    items: list[DocumentUnit]
    total: int
