"""Server-generated storage keys. Never serve this directory as static files."""

from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
from uuid import uuid4

from eduagent.documents.models import DocumentError, MAX_OUTPUT


class DocumentFiles:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, key):
        relative = PurePosixPath(key)
        if relative.is_absolute() or any(part in ('..', '.') for part in relative.parts) or '\\' in key:
            raise DocumentError('document_storage_unavailable', 503)
        target = self.root.joinpath(*relative.parts)
        if not target.resolve().is_relative_to(self.root) or any(p.is_symlink() for p in [target, *target.parents] if p != self.root.parent):
            raise DocumentError('document_storage_unavailable', 503)
        return target

    def stage(self):
        key = f'staging/{uuid4()}.bin'
        path = self.path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        return key, path

    def commit(self, staged_key, document_id, version_id):
        key = f'originals/{document_id}/{version_id}.bin'
        target = self.path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            raise DocumentError('document_storage_unavailable', 503)
        os.replace(self.path(staged_key), target)
        return key

    def discard_stage(self, key):
        if key.startswith('staging/'):
            self.path(key).unlink(missing_ok=True)

    def verified(self, key, digest, size):
        path = self.path(key)
        try:
            if path.stat().st_size != size:
                raise DocumentError('original_unavailable', 503)
            checksum = sha256()
            with path.open('rb') as file:
                for block in iter(lambda: file.read(65536), b''):
                    checksum.update(block)
            if checksum.hexdigest() != digest:
                raise DocumentError('original_unavailable', 503)
        except OSError:
            raise DocumentError('original_unavailable', 503) from None
        return path

    def artifact(self, run_id, payload):
        value = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode('utf8')
        if len(value) > MAX_OUTPUT:
            raise DocumentError('document_too_large', 413)
        key = f'derived/{run_id}/{uuid4()}.json'
        target = self.path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        # A run is published once; a stale worker can never replace another run.
        try:
            with target.open('xb') as file:
                file.write(value)
                file.flush()
                os.fsync(file.fileno())
        except BaseException:
            target.unlink(missing_ok=True)
            raise
        return key, sha256(value).hexdigest(), len(value)
