"""Local workspaces, immutable releases, and explicit teaching actions."""
from dataclasses import replace
from typing import Annotated,Literal
from fastapi import APIRouter
from pydantic import Field
from eduagent.api.schemas import RequestBody,Identifier
from eduagent.api.document_schemas import UUIDText
from eduagent.api.workbench_schemas import WorkbenchQuestion
from eduagent.services.course_releases import CourseReleases
from eduagent.services.teaching import TeachingService
from eduagent.services.workbench import WorkbenchService

class Command(RequestBody):request_id:UUIDText
class Draft(Command):
    payload:dict
    expected_revision:Annotated[int,Field(ge=1)]|None=None
class Publish(Command):
    expected_revision:Annotated[int,Field(ge=1)]
    snapshot_hash:Annotated[str,Field(min_length=64,max_length=64)]
    kind:Literal['demo','reviewed']
    confirmed:bool=False
class Begin(Command):
    release_id:UUIDText
    goals:Annotated[list[str],Field(min_length=1,max_length=5)]
class Allocate(Command):expected_learning_revision:Annotated[int,Field(ge=0)]
class Submit(Command):
    decision_id:str
    answer:Annotated[str,Field(min_length=1,max_length=8)]

def course_workspace_router(factory,settings,courses,client_factory=None):
    router=APIRouter(tags=['课程构建与学生教学闭环']);prefix='/api/v1/students/{student_id}'
    def releases(learning):return CourseReleases(learning,settings.data_dir)
    def teaching(learning):
        def wb(current):
            chat=replace(settings.agent,max_tokens=settings.agent.workbench_max_tokens)
            def client():
                if client_factory:return client_factory()
                from eduagent.agent.deepseek import DeepSeekClient
                return DeepSeekClient(chat,json_output=True)
            return WorkbenchService(current,courses(),settings.retrieval_enabled,chat,client)
        return TeachingService(learning,settings.data_dir,wb)
    @router.get('/api/v1/courses/published')
    def public_courses():
        with factory() as learning:
            service=releases(learning)
            return dict(items=[service.view(dict(r)) for r in service.db.execute("SELECT * FROM course_releases WHERE scope_key='*' ORDER BY release_version DESC")])
    @router.get(prefix+'/course-releases')
    def published(student_id:Identifier):
        with factory() as learning:return releases(learning).list(student_id)
    @router.get(prefix+'/course-releases/{key}')
    def release(student_id:Identifier,key:str):
        with factory() as learning:
            service=releases(learning);return service.view(service.row(student_id,key))
    @router.get(prefix+'/course-builder')
    def builder(student_id:Identifier):
        with factory() as learning:return releases(learning).builder(student_id)
    @router.post(prefix+'/course-builder/drafts')
    def create(student_id:Identifier,body:Draft):
        with factory() as learning:return releases(learning).save(student_id,body.model_dump())
    @router.get(prefix+'/course-builder/drafts/{key}')
    def get_draft(student_id:Identifier,key:str):
        with factory() as learning:return releases(learning).check(student_id,key)
    @router.put(prefix+'/course-builder/drafts/{key}')
    def edit(student_id:Identifier,key:str,body:Draft):
        from eduagent.domain.personal_bank import fail
        if body.expected_revision is None:fail('修改草稿必须提供revision')
        with factory() as learning:return releases(learning).save(student_id,body.model_dump(),key)
    @router.post(prefix+'/course-builder/drafts/{key}/publish')
    def publish(student_id:Identifier,key:str,body:Publish):
        with factory() as learning:return releases(learning).publish(student_id,key,body.model_dump())
    @router.get(prefix+'/course-workflow/requests/{key}')
    def receipt(student_id:Identifier,key:str):
        from eduagent.domain.personal_bank import fail
        import json
        with factory() as learning:
            learning._student(student_id)
            r=learning.repository.connection.execute('SELECT result_json FROM course_workflow_operations WHERE student_id=? AND request_id=?',(student_id,key)).fetchone()
            if not r:fail('当前标识下没有该请求','workflow_request_not_found',404)
            return json.loads(r[0])
    @router.get(prefix+'/current-decision')
    def current(student_id:Identifier):
        with factory() as learning:return teaching(learning).current_decision(student_id)
    @router.get(prefix+'/teaching-history')
    def history(student_id:Identifier):
        with factory() as learning:return teaching(learning).history(student_id)
    @router.get(prefix+'/teaching-explanations')
    def explanation_contexts(student_id:Identifier):
        with factory() as learning:return teaching(learning).explanation_contexts(student_id)
    @router.get(prefix+'/teaching-sessions')
    def latest(student_id:Identifier):
        with factory() as learning:return teaching(learning).latest(student_id)
    @router.post(prefix+'/teaching-sessions')
    def begin(student_id:Identifier,body:Begin):
        with factory() as learning:return teaching(learning).begin(student_id,body.model_dump())
    @router.get(prefix+'/teaching-sessions/{key}')
    def state(student_id:Identifier,key:str):
        with factory() as learning:return teaching(learning).state(student_id,key)
    @router.post(prefix+'/teaching-sessions/{key}/next')
    def allocate(student_id:Identifier,key:str,body:Allocate):
        with factory() as learning:return teaching(learning).allocate(student_id,key,body.model_dump())
    @router.post(prefix+'/teaching-sessions/{key}/answers')
    def submit(student_id:Identifier,key:str,body:Submit):
        with factory() as learning:return teaching(learning).submit(student_id,key,body.model_dump())
    @router.post(prefix+'/teaching-sessions/{key}/explain')
    def explain(student_id:Identifier,key:str,body:WorkbenchQuestion):
        with factory() as learning:return teaching(learning).explain(student_id,key,body.model_dump())
    return router
