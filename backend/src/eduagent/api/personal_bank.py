"""Scoped resource, review and ordinary-practice contracts, independent from /answers."""
from typing import Annotated,Literal
from fastapi import APIRouter,Query
from pydantic import Field,model_validator
from eduagent.api.schemas import RequestBody,Identifier
from eduagent.api.document_schemas import UUIDText,Title
from eduagent.services.personal_bank import PersonalBankService
from eduagent.domain.personal_bank import QUESTION_TYPES


class Command(RequestBody):
    request_id:UUIDText


class ResourceEdit(Command):
    expected_revision:Annotated[int,Field(ge=0)]
    resource_type:Literal['teaching_material','reference','personal_note','exercise_material']
    links:Annotated[list[dict],Field(max_length=24)]=[]


class Extraction(Command):
    auto_import:bool=False
    resource_id:UUIDText|None=None
    source_version:Annotated[str,Field(max_length=160)]|None=None
    run_id:UUIDText|None=None
    ordinals:Annotated[list[Annotated[int,Field(ge=1,le=200)]],Field(max_length=30)]|None=None
    text:Annotated[str,Field(max_length=60000)]|None=None
    title:Title='粘贴习题'

    @model_validator(mode='after')
    def selection(self):
        if bool(self.resource_id)==bool(self.text):raise ValueError('资源和粘贴文本须二选一')
        if self.resource_id and not self.source_version:raise ValueError('必须指定资源版本')
        if self.text and (self.run_id or self.ordinals or self.source_version):raise ValueError('粘贴文本不接受文件版本或页码')
        if self.ordinals is not None and (not self.ordinals or len(set(self.ordinals))!=len(self.ordinals)):raise ValueError('选页不能为空或重复')
        return self


class SemanticExtraction(Extraction):
    consent:bool=False
    include_images:bool=False
    target_question_id:UUIDText|None=None
    target_revision:Annotated[int,Field(ge=1)]|None=None

    @model_validator(mode='after')
    def target(self):
        if bool(self.target_question_id)!=bool(self.target_revision):raise ValueError('重识别必须同时提供题目ID和版本')
        return self


class SaveQuestion(Command):
    expected_revision:Annotated[int,Field(ge=1)]|None=None
    payload:dict
    status:Literal['draft','practice']='draft'
    reviewed:bool=False
    confirm_answer:bool=False
    acknowledge_source_change:bool=False


class Revision(Command):
    expected_revision:Annotated[int,Field(ge=1)]

class AcceptProposal(Revision):
    proposal_id:UUIDText
    proposal_revision:Annotated[int,Field(ge=1)]


class Original(RequestBody):
    question_id:UUIDText
    expected_revision:Annotated[int,Field(ge=1)]


class Restructure(Command):
    originals:Annotated[list[Original],Field(min_length=1,max_length=8)]
    questions:Annotated[list[dict],Field(min_length=1,max_length=8)]


class StartPractice(Command):
    question_id:UUIDText|None=None
    concept_id:UUIDText|None=None
    acknowledge_source_change:bool=False

class OrganizeQuestions(Command):
    question_ids:Annotated[list[UUIDText],Field(min_length=1,max_length=50)]|None=None


class SubmitPractice(Command):
    selected_answer:Annotated[str,Field(min_length=1,max_length=16000)]
    needs_review:bool=False


class PracticeDraft(Command):
    expected_revision:Annotated[int,Field(ge=0)]
    response_text:Annotated[str,Field(max_length=16000)]
    needs_review:bool=False


def personal_bank_router(learning_factory,materials,extraction_service=None):
    router=APIRouter(prefix='/api/v1/students/{student_id}',tags=['课程资源与个人普通练习'])
    def service(learning):return PersonalBankService(learning,materials)
    @router.get('/course-resources')
    def resources(student_id:Identifier):
        with learning_factory() as learning:return service(learning).catalogue(student_id)
    @router.get('/course-resources/{key}')
    def resource(student_id:Identifier,key:str):
        with learning_factory() as learning:return service(learning).resource(student_id,key)
    @router.put('/course-resources/{key}')
    def tag(student_id:Identifier,key:str,body:ResourceEdit):
        with learning_factory() as learning:return service(learning).tag_resource(student_id,key,body.model_dump())
    @router.get('/personal-bank/requests/{key}')
    def receipt(student_id:Identifier,key:str):
        with learning_factory() as learning:return service(learning).receipt(student_id,key)
    @router.post('/personal-bank/extractions')
    def extraction(student_id:Identifier,body:Extraction):
        with learning_factory() as learning:return service(learning).extract(student_id,body.model_dump())
    @router.get('/personal-bank/questions')
    def listing(student_id:Identifier,q:Annotated[str,Query(max_length=200)]='',status:Literal['draft','practice','archived']|None=None,
                question_type:Literal['single_choice','multiple_choice','true_false','fill_blank','short_answer','calculation','proof','unknown','other']|None=None,resource_id:UUIDText|None=None,concept_id:UUIDText|None=None,chapter_id:UUIDText|None=None):
        with learning_factory() as learning:return service(learning).listing(student_id,q=q,status=status,question_type=question_type,resource_id=resource_id,concept_id=concept_id,chapter_id=chapter_id)
    @router.post('/personal-bank/questions')
    def create(student_id:Identifier,body:SaveQuestion):
        with learning_factory() as learning:return service(learning).save(student_id,body.model_dump())
    @router.post('/personal-bank/organize')
    def organize(student_id:Identifier,body:OrganizeQuestions):
        from eduagent.services.question_intake import organize
        with learning_factory() as learning:return organize(service(learning),student_id,body.model_dump())
    @router.post('/personal-bank/restructure')
    def restructure(student_id:Identifier,body:Restructure):
        with learning_factory() as learning:return service(learning).restructure(student_id,body.model_dump())
    @router.get('/personal-bank/questions/{key}')
    def detail(student_id:Identifier,key:str):
        with learning_factory() as learning:return service(learning).get(student_id,key)
    @router.put('/personal-bank/questions/{key}')
    def update(student_id:Identifier,key:str,body:SaveQuestion):
        with learning_factory() as learning:
            if body.expected_revision is None:raise ValueError('修改须提供题目revision')
            return service(learning).save(student_id,body.model_dump(),key)
    @router.delete('/personal-bank/questions/{key}')
    def archive(student_id:Identifier,key:str,body:Revision):
        with learning_factory() as learning:return service(learning).archive(student_id,key,body.model_dump())
    @router.post('/personal-bank/questions/{key}/accept-proposal')
    def accept_proposal(student_id:Identifier,key:str,body:AcceptProposal):
        with learning_factory() as learning:return service(learning).accept_proposal(student_id,key,body.model_dump())
    @router.get('/personal-bank/questions/{key}/revisions')
    def revisions(student_id:Identifier,key:str):
        with learning_factory() as learning:return service(learning).revisions(student_id,key)
    @router.post('/personal-bank/practice')
    def start(student_id:Identifier,body:StartPractice):
        with learning_factory() as learning:return service(learning).start(student_id,body.model_dump())
    @router.get('/personal-bank/practice')
    def sessions(student_id:Identifier,wrong_only:bool=False):
        with learning_factory() as learning:return service(learning).sessions(student_id,wrong_only)
    @router.get('/personal-bank/practice/{key}')
    def session(student_id:Identifier,key:str):
        with learning_factory() as learning:return service(learning).session(student_id,key)
    @router.post('/personal-bank/practice/{key}/answer')
    def submit(student_id:Identifier,key:str,body:SubmitPractice):
        with learning_factory() as learning:return service(learning).submit(student_id,key,body.model_dump())
    @router.put('/personal-bank/practice/{key}/draft')
    def save_draft(student_id:Identifier,key:str,body:PracticeDraft):
        with learning_factory() as learning:return service(learning).save_practice_draft(student_id,key,body.model_dump())
    if extraction_service:
        @router.get('/personal-bank/extraction-capabilities')
        def extraction_capabilities(student_id:Identifier):
            with learning_factory() as learning:
                learning._student(student_id)
                return extraction_service(learning).capabilities()
        @router.post('/personal-bank/extraction-tasks',status_code=202)
        def semantic_extract(student_id:Identifier,body:SemanticExtraction):
            with learning_factory() as learning:return extraction_service(learning).create(student_id,body.model_dump())
        @router.get('/personal-bank/extraction-tasks')
        def extraction_tasks(student_id:Identifier):
            with learning_factory() as learning:return extraction_service(learning).list(student_id)
        @router.get('/personal-bank/extraction-tasks/{key}')
        def extraction_task(student_id:Identifier,key:str):
            with learning_factory() as learning:return extraction_service(learning).get(student_id,key)
    return router
