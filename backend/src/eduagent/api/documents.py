"""Private document routes. Multipart files never enter the model implicitly."""

from hashlib import sha256
from importlib.util import find_spec
import json
from typing import Annotated

from fastapi import APIRouter, Request, Query, Response
from fastapi.responses import FileResponse, JSONResponse
from pydantic import ValidationError
from starlette.datastructures import UploadFile

from eduagent.api.schemas import Identifier
from eduagent.api.document_schemas import (UploadDocument, UploadVersion, Mutation, UpdateDocument, VisionRequest,
    CourseDocument, DocumentList, DocumentVersion, DocumentRun, UnitList)
from eduagent.documents.models import DocumentError, filename, MAX_FILE, MAX_TEXT_FILE
from eduagent.documents.vision import VISION_MODEL, VISION_MAX_TOKENS, VISION_MAX_PAGES

MULTIPART = {'requestBody': {'required': True, 'content': {'multipart/form-data': {'schema': {
    'type': 'object', 'required': ['metadata', 'file'], 'additionalProperties': False, 'properties': {
        'metadata': {'type': 'string', 'description': '严格JSON元数据；新建含request_id/title/local_rights_confirmed，版本更新含request_id/expected_revision'},
        'file': {'type': 'string', 'format': 'binary'}}}}}}}


def documents_router(service_factory, settings):
    router = APIRouter(prefix='/api/v1/students/{student_id}/documents', tags=['课程资料解析'])

    @router.get('/capabilities')
    def capabilities(student_id: Identifier):
        with service_factory() as service:
            service.student(student_id)
        return dict(formats={'md': True, 'txt': True, 'pdf': find_spec('pypdf') is not None,
                             'pptx': find_spec('pptx') is not None, 'png': True, 'jpg': True, 'jpeg': True, 'webp': True},
                    vision_enabled=settings.document_vision_enabled and bool(settings.agent.api_key), vision_provider='DeepSeek',
                    vision_model=VISION_MODEL, vision_max_pages=VISION_MAX_PAGES, vision_max_output_tokens=VISION_MAX_TOKENS,
                    max_file_bytes=MAX_FILE, max_text_file_bytes=MAX_TEXT_FILE, max_pages=200,
                    retrieval_connected=False, identity_mode='local_demo_scope')

    @router.get('', response_model=DocumentList)
    def listing(student_id: Identifier, limit: Annotated[int, Query(ge=1, le=25)] = 25, offset: Annotated[int, Query(ge=0)] = 0):
        with service_factory() as service:
            return service.list(student_id, limit=limit, offset=offset)

    @router.get('/operations/{request_id}')
    def receipt(student_id: Identifier, request_id: str):
        from eduagent.documents.models import uuid_text
        uuid_text(request_id)
        with service_factory() as service:
            service.student(student_id)
            row = service.db.execute('SELECT operation,result_json FROM document_operations WHERE student_id=? AND course_id=? AND request_id=?', (student_id, 'machine_learning', request_id)).fetchone()
            if row is None:
                raise DocumentError('document_not_found', 404)
            return dict(request_id=request_id, operation=row['operation'], result=json.loads(row['result_json']))

    async def upload(student_id, request, document_id=None):
        with service_factory() as service:
            service.student(student_id)
            async with request.form(max_files=1, max_fields=1, max_part_size=256 * 1024) as form:
                if len(form.multi_items()) != 2 or set(form) != {'file', 'metadata'} or not isinstance(form['file'], UploadFile) or not isinstance(form['metadata'], str):
                    raise ValueError('上传须包含一个file和一个metadata字段')
                try:
                    body = (UploadVersion if document_id else UploadDocument).model_validate_json(form['metadata']).model_dump()
                except ValidationError:
                    raise ValueError('上传元数据字段无效，请核对请求编号、标题和本地使用权确认') from None
                file = form['file']
                name, kind = filename(file.filename)
                allowed_mime = {'pdf': {'application/pdf'}, 'pptx': {'application/vnd.openxmlformats-officedocument.presentationml.presentation', 'application/zip'},
                                'md': {'text/markdown', 'text/x-markdown', 'text/plain'}, 'txt': {'text/plain'},
                                'png': {'image/png'}, 'jpg': {'image/jpeg'}, 'jpeg': {'image/jpeg'}, 'webp': {'image/webp'}}
                mime = (file.content_type or 'application/octet-stream').split(';', 1)[0].strip().lower()
                if mime not in allowed_mime[kind] | {'application/octet-stream'}:
                    raise DocumentError('invalid_document', 415)
                key, path = service.files.stage()
                try:
                    size, checksum = 0, sha256()
                    with path.open('xb') as target:
                        while chunk := await file.read(65536):
                            size += len(chunk)
                            if size > (MAX_TEXT_FILE if kind in ('md', 'txt') else MAX_FILE):
                                raise DocumentError('document_too_large', 413)
                            checksum.update(chunk); target.write(chunk)
                    value, replayed = service.upload(student_id, body, key, name, size, checksum.hexdigest(), document_id)
                finally:
                    service.files.discard_stage(key)
                return JSONResponse(status_code=200 if replayed else 202, content=value)

    @router.post('', response_model=CourseDocument, status_code=202, openapi_extra=MULTIPART)
    async def create(student_id: Identifier, request: Request):
        return await upload(student_id, request)

    @router.post('/{document_id}/versions', response_model=CourseDocument, status_code=202, openapi_extra=MULTIPART)
    async def version(student_id: Identifier, document_id: str, request: Request):
        return await upload(student_id, request, document_id)

    @router.get('/{document_id}', response_model=CourseDocument)
    def detail(student_id: Identifier, document_id: str):
        with service_factory() as service:
            return service.get(student_id, document_id)

    @router.get('/{document_id}/versions', response_model=list[DocumentVersion])
    def versions(student_id: Identifier, document_id: str):
        with service_factory() as service:
            return service.versions(student_id, document_id)

    @router.get('/{document_id}/preview')
    def preview(student_id:Identifier,document_id:str,version_id:str|None=None,page:Annotated[int,Query(ge=1,le=200)]=1):
        with service_factory() as service:
            raw=service.preview(student_id,document_id,version_id,page)
        return Response(raw,media_type='image/png',headers={'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'})

    @router.patch('/{document_id}', response_model=CourseDocument)
    def update(student_id: Identifier, document_id: str, body: UpdateDocument):
        with service_factory() as service:
            return service.mutate(student_id, document_id, body.model_dump(exclude_none=True), 'update')[0]

    @router.delete('/{document_id}')
    def delete(student_id: Identifier, document_id: str, body: Mutation):
        with service_factory() as service:
            return service.mutate(student_id, document_id, body.model_dump(), 'delete')[0]

    @router.post('/{document_id}/parse', response_model=CourseDocument, status_code=202)
    def retry(student_id: Identifier, document_id: str, body: Mutation, response: Response):
        with service_factory() as service:
            value, replayed = service.mutate(student_id, document_id, body.model_dump(), 'parse')
            response.status_code = 200 if replayed else 202
            return value

    @router.post('/{document_id}/vision', response_model=DocumentRun, status_code=202)
    def vision(student_id: Identifier, document_id: str, body: VisionRequest, response: Response):
        with service_factory() as service:
            value, replayed = service.mutate(student_id, document_id, body.model_dump(), 'vision')
            response.status_code = 200 if replayed else 202
            return value

    @router.get('/{document_id}/parse-runs', response_model=list[DocumentRun])
    def runs(student_id: Identifier, document_id: str):
        with service_factory() as service:
            return service.runs(student_id, document_id)

    @router.get('/{document_id}/parse-runs/{run_id}', response_model=DocumentRun)
    def run(student_id: Identifier, document_id: str, run_id: str):
        with service_factory() as service:
            return service.get_run(student_id, document_id, run_id)

    @router.get('/{document_id}/units', response_model=UnitList)
    def units(student_id: Identifier, document_id: str, run_id: str | None = None,
              limit: Annotated[int, Query(ge=1, le=20)] = 10, offset: Annotated[int, Query(ge=0)] = 0):
        with service_factory() as service:
            return service.units(student_id, document_id, run_id, limit, offset)

    @router.get('/{document_id}/original', response_class=FileResponse)
    def original(student_id: Identifier, document_id: str, version_id: str | None = None):
        with service_factory() as service:
            path, name = service.original(student_id, document_id, version_id)
        return FileResponse(path, media_type='application/octet-stream', filename=name,
                            headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})

    return router
