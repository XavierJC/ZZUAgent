"""Local page mappings and explicit review; no paid processing in these routes."""
from typing import Annotated
from fastapi import APIRouter
from pydantic import Field
from eduagent.api.schemas import RequestBody,Identifier
from eduagent.api.document_schemas import UUIDText
from eduagent.services.teaching_sources import TeachingSources

class CreateLink(RequestBody):
    request_id:UUIDText
    document_id:UUIDText
    run_id:UUIDText
    ordinal:Annotated[int,Field(ge=1,le=200)]
    architecture_id:UUIDText
    concept_id:UUIDText
    start_offset:Annotated[int,Field(ge=0)]
    end_offset:Annotated[int,Field(ge=1)]
    excerpt_md:Annotated[str,Field(max_length=12000)]|None=None

class ReviewLink(RequestBody):
    request_id:UUIDText
    expected_revision:Annotated[int,Field(ge=1)]
    confirmed:bool
    architecture_version:Annotated[int,Field(ge=1)]|None=None
    reviewer:Annotated[str,Field(max_length=120)]=''

def teaching_materials_router(factory):
    router=APIRouter(prefix='/api/v1/students/{student_id}/teaching-material-links',tags=['试点课件片段审核'])
    @router.get('')
    def listing(student_id:Identifier):
        with factory() as l:
            with l.repository.transaction():return TeachingSources(l.repository).listing(student_id)
    @router.post('')
    def create(student_id:Identifier,body:CreateLink):
        with factory() as l:return TeachingSources(l.repository).create(student_id,body.model_dump())
    @router.put('/{key}/review')
    def review(student_id:Identifier,key:UUIDText,body:ReviewLink):
        with factory() as l:return TeachingSources(l.repository).review(student_id,key,body.model_dump())
    @router.get('/requests/{key}')
    def receipt(student_id:Identifier,key:UUIDText):
        from eduagent.domain.personal_bank import fail
        import json
        with factory() as l:
            l._student(student_id)
            row=l.repository.connection.execute('SELECT result_json FROM teaching_material_operations WHERE student_id=? AND request_id=?',(student_id,key)).fetchone()
            if not row:fail('当前标识下没有该请求','request_not_found',404)
            return json.loads(row[0])
    return router
