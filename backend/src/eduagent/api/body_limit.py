"""Bound note JSON before parsing, including requests without Content-Length."""

import re

from fastapi.responses import JSONResponse

from eduagent.domain.notes import MAX_REQUEST_BYTES


class NotesBodyLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not re.fullmatch(r"/api/v1/students/[^/]+/(?:notes(?:/.*)?|knowledge(?:/.*)?|knowledge-architectures(?:/.*)?|workbench(?:/.*)?|self-assessments(?:/.*)?|study-guides(?:/.*)?)", scope["path"]):
            return await self.app(scope, receive, send)
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            if len(body) + len(chunk) > MAX_REQUEST_BYTES:
                response = JSONResponse(status_code=413, content={"error": {
                    "code": "content_too_large", "message": "笔记请求体最多 256 KiB"}})
                return await response(scope, receive, send)
            body.extend(chunk)
            if not message.get("more_body", False):
                break
        delivered = False

        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        return await self.app(scope, replay, send)
