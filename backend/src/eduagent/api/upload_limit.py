"""Count streaming upload bytes before multipart parsing; no large body buffer."""

import re
from fastapi.responses import JSONResponse
from eduagent.documents.models import DocumentError, MAX_BODY


class DocumentBodyLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or not re.fullmatch(r'/api/v1/students/[^/]+/documents(?:/.*)?', scope['path']):
            return await self.app(scope, receive, send)
        upload = scope['method'] == 'POST' and (scope['path'].endswith('/documents') or scope['path'].endswith('/versions'))
        limit = MAX_BODY if upload else 256 * 1024
        headers = dict(scope.get('headers', []))
        try:
            if int(headers.get(b'content-length', b'0')) > limit:
                response = JSONResponse(status_code=413, content={'error': {'code': 'document_too_large', 'message': '资料请求体超过限额'}})
                return await response(scope, receive, send)
        except ValueError:
            response = JSONResponse(status_code=400, content={'error': {'code': 'invalid_input', 'message': '请求长度无效'}})
            return await response(scope, receive, send)
        size = 0

        async def bounded_receive():
            nonlocal size
            message = await receive()
            size += len(message.get('body', b''))
            if size > limit:
                raise DocumentError('document_too_large', 413)
            return message

        return await self.app(scope, bounded_receive, send)
