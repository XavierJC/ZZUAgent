"""Course-architecture routes; no model, grading or practice-allocation tools."""
from typing import Annotated
from fastapi import APIRouter, Query, Path
from pydantic import Field
from eduagent.api.schemas import RequestBody, Identifier
from eduagent.api.document_schemas import UUIDText, Title
from eduagent.services.architectures import ArchitectureService


class CreateArchitecture(RequestBody):
    request_id: UUIDText
    name: Title
    description: Annotated[str,Field(max_length=2000)] = ''


class ArchitectureMutation(RequestBody):
    request_id: UUIDText
    expected_revision: Annotated[int,Field(ge=1)]


class SaveArchitecture(ArchitectureMutation):
    graph: dict


class ForkArchitecture(ArchitectureMutation):
    version: Annotated[int,Field(ge=1)]


class PublishArchitecture(ArchitectureMutation):
    confirmed: bool = False


class DocumentSelection(RequestBody):
    document_id: UUIDText
    version_id: UUIDText
    run_id: UUIDText


class ExtractArchitecture(ArchitectureMutation):
    documents: Annotated[list[DocumentSelection],Field(min_length=1,max_length=3)]


def architectures_router(learning_factory):
    router=APIRouter(prefix='/api/v1/students/{student_id}/knowledge-architectures',tags=['课程知识体系'])
    @router.get('')
    def listing(student_id:Identifier):
        with learning_factory() as learning: return ArchitectureService(learning).listing(student_id)
    @router.post('')
    def create(student_id:Identifier,body:CreateArchitecture):
        with learning_factory() as learning: return ArchitectureService(learning).create(student_id,body.model_dump())
    @router.get('/requests/{request_id}')
    def receipt(student_id:Identifier,request_id:str):
        with learning_factory() as learning: return ArchitectureService(learning).receipt(student_id,request_id)
    @router.get('/{architecture_id}')
    def get(student_id:Identifier,architecture_id:str):
        with learning_factory() as learning: return ArchitectureService(learning).get(student_id,architecture_id)
    @router.put('/{architecture_id}/draft')
    def save(student_id:Identifier,architecture_id:str,body:SaveArchitecture):
        with learning_factory() as learning: return ArchitectureService(learning).save(student_id,architecture_id,body.model_dump())
    @router.post('/{architecture_id}/draft')
    def fork(student_id:Identifier,architecture_id:str,body:ForkArchitecture):
        with learning_factory() as learning: return ArchitectureService(learning).fork(student_id,architecture_id,body.model_dump())
    @router.post('/{architecture_id}/publish')
    def publish(student_id:Identifier,architecture_id:str,body:PublishArchitecture):
        with learning_factory() as learning: return ArchitectureService(learning).publish(student_id,architecture_id,body.model_dump())
    @router.get('/{architecture_id}/published')
    def current(student_id:Identifier,architecture_id:str):
        with learning_factory() as learning: return ArchitectureService(learning).published(student_id,architecture_id)
    @router.get('/{architecture_id}/versions/{version}')
    def version(student_id:Identifier,architecture_id:str,version:Annotated[int,Path(ge=1)]):
        with learning_factory() as learning: return ArchitectureService(learning).published(student_id,architecture_id,version)
    @router.post('/{architecture_id}/candidates')
    def candidates(student_id:Identifier,architecture_id:str,body:ExtractArchitecture):
        with learning_factory() as learning: return ArchitectureService(learning).candidates(student_id,architecture_id,body.model_dump())
    @router.get('/{architecture_id}/candidates/{batch_id}')
    def evidence(student_id:Identifier,architecture_id:str,batch_id:str):
        with learning_factory() as learning: return ArchitectureService(learning).batch(student_id,architecture_id,batch_id)
    @router.get('/{architecture_id}/concepts/{concept_id}/learning-state')
    def states(student_id:Identifier,architecture_id:str,concept_id:str,version:Annotated[int|None,Query(ge=1)]=None,draft:bool=False):
        with learning_factory() as learning: return ArchitectureService(learning).states(student_id,architecture_id,concept_id,version,draft)
    return router
