"""Strict note contracts: only Markdown input, no client score/index fields."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, model_validator

from eduagent.api.schemas import RequestBody

Title = Annotated[str, StringConstraints(min_length=1, max_length=120)]
Body = str  # UTF-8 byte limit is enforced by the domain, not character length.
Links = Annotated[list[str], Field(max_length=5)]
Revision = Annotated[int, Field(ge=1)]
Course = Literal["machine_learning"]


class CreateNote(RequestBody):
    id: str
    title: Title
    content_md: Body = ""
    knowledge_point_ids: Links = Field(default_factory=list)
    course_id: Course = "machine_learning"


class UpdateNote(RequestBody):
    expected_revision: Revision
    title: Title | None = None
    content_md: Body | None = None
    knowledge_point_ids: Links | None = None

    @model_validator(mode="after")
    def valid_changes(self):
        fields = self.model_fields_set - {"expected_revision"}
        if not fields or any(getattr(self, name) is None for name in fields):
            raise ValueError("至少提供一个非空更新字段，不能使用 null 覆盖内容")
        return self


class ImportNote(RequestBody):
    id: str
    file_name: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    content_base64: str
    title: Title | None = None
    knowledge_point_ids: Links = Field(default_factory=list)
    course_id: Course = "machine_learning"


class NoteSummary(BaseModel):
    id: str
    student_id: str
    course_id: Course
    title: str
    revision: int
    content_hash: str
    created_via: Literal["manual", "import"]
    created_at: str
    updated_at: str
    content_bytes: int
    knowledge_point_ids: list[str]
    index_status: Literal["disabled", "pending", "building", "ready", "empty", "failed"]


class GenerationOrigin(BaseModel):
    request_id: str
    generated_at: str
    original_revision: Literal[1]
    edited: bool


class NoteDetail(NoteSummary):
    content_md: str
    generation_origin: GenerationOrigin | None = None


class ImportedNote(NoteDetail):
    import_warnings: list[str]


class NoteList(BaseModel):
    items: list[NoteSummary]
    total: int
    limit: int
    offset: int
