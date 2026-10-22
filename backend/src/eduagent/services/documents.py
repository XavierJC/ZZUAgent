"""Independent document workflow: never assigns exercises or writes mastery."""

from hashlib import sha256
import json
from uuid import uuid4

from eduagent.documents.files import DocumentFiles
from eduagent.documents.models import (DocumentError, PARSER_VERSION, ROLES, MAX_DOCUMENTS, MAX_STORED_BYTES,
                                      MAX_DERIVED_BYTES, uuid_text, filename, result)
from eduagent.documents.preflight import signature
from eduagent.documents.vision import VISION_VERSION, VISION_MAX_PAGES, VISION_MAX_TOKENS, VISION_MODEL, default_client, transcribe
from eduagent.services.learning import identifier, now, StudentNotFound
from eduagent.storage.documents import DocumentRepository
from eduagent.domain.notes import course


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


def digest(value):
    return sha256(encode(value).encode('utf8')).hexdigest()


class DocumentsService:
    def __init__(self, repository, directory, *, vision_enabled=False, agent_settings=None):
        self.repository, self.storage = repository, DocumentRepository(repository)
        self.db, self.files = repository.connection, DocumentFiles(directory)
        self.vision_enabled, self.agent = vision_enabled, agent_settings

    def student(self, student, course_id='machine_learning'):
        identifier(student, '学生标识'); course(course_id)
        if self.repository.student(student) is None:
            raise StudentNotFound('学生标识不存在，请先创建学习记录')

    def _document(self, student, key, course_id='machine_learning'):
        self.student(student, course_id)
        return self.storage.document(student, key, course_id)

    @staticmethod
    def version_view(version):
        return {key: version[key] for key in ('id', 'document_id', 'file_revision', 'file_name', 'format',
                                              'size_bytes', 'content_hash', 'created_at')}

    def run_view(self, run, document):
        current = (not document['deleted_at'] and run['version_id'] == document['current_version_id']
                   and run['generation'] == document['parse_generation']
                   and (run['mode'] == 'local' or run['expected_revision'] == document['revision']))
        return dict(id=run['id'], document_id=run['document_id'], version_id=run['version_id'], generation=run['generation'],
                    mode=run['mode'], status=run['status'], current_status='current' if current else 'modified',
                    parser_version=run['parser_version'], pages=json.loads(run['pages_json']), unit_count=run['unit_count'],
                    warnings=json.loads(run['warnings_json']), error_code=run['error_code'], model_calls=run['model_calls'],
                    usage=json.loads(run['usage_json']), model=run['model'], created_at=run['created_at'], updated_at=run['updated_at'],
                    max_output_tokens=VISION_MAX_TOKENS if run['mode'] == 'vision' else None)

    def view(self, document):
        output = {key: document[key] for key in ('id', 'course_id', 'title', 'material_role', 'source_note', 'revision',
                                                'created_at', 'updated_at')}
        output.update(source_type='teaching_material', review_status='imported_unverified', local_rights_confirmed=True,
                      index_status='not_implemented', version=self.version_view(self.storage.version(document)),
                      parse=self.run_view(self.storage.run(document), document))
        return output

    def list(self, student, course_id='machine_learning', limit=25, offset=0):
        with self.repository.transaction():
            self.student(student, course_id)
            rows = self.db.execute('SELECT * FROM course_documents WHERE student_id=? AND course_id=? AND deleted_at IS NULL ORDER BY updated_at DESC,id LIMIT ? OFFSET ?',
                                   (student, course_id, limit, offset)).fetchall()
            return {'items': [self.view(dict(row)) for row in rows], 'course_id': course_id}

    def get(self, student, key):
        with self.repository.transaction():
            return self.view(self._document(student, key))

    def versions(self, student, key):
        with self.repository.transaction():
            doc = self._document(student, key)
            return [self.version_view(dict(row)) for row in self.db.execute(
                'SELECT * FROM document_versions WHERE document_id=? AND student_id=? AND course_id=? ORDER BY file_revision DESC',
                (key, student, doc['course_id']))]

    def get_run(self, student, key, run_id):
        with self.repository.transaction():
            doc = self._document(student, key)
            return self.run_view(self.storage.run(doc, run_id), doc)

    def runs(self, student, key):
        with self.repository.transaction():
            doc = self._document(student, key)
            return [self.run_view(dict(row), doc) for row in self.db.execute(
                'SELECT * FROM document_parse_runs WHERE document_id=? AND student_id=? ORDER BY created_at DESC,id LIMIT 30', (key, student))]

    def units(self, student, key, run_id=None, limit=10, offset=0):
        with self.repository.transaction():
            doc = self._document(student, key)
            run = self.storage.run(doc, run_id)
            unavailable = run['status'] == 'failed' and run['error_code'] in ('original_unavailable', 'derived_unavailable')
            rows = self.db.execute('SELECT * FROM document_units WHERE run_id=? AND document_id=? AND student_id=? ORDER BY ordinal LIMIT ? OFFSET ?',
                                   (run['id'], key, student, limit, offset)).fetchall() if not unavailable else []
            units = []
            for row in rows:
                item = {field: row[field] for field in ('id', 'ordinal', 'kind', 'title', 'text', 'content_md', 'interpretation_md', 'origin', 'content_hash')}
                item.update(location=json.loads(row['location_json']), blocks=json.loads(row['blocks_json']), warnings=json.loads(row['warnings_json']))
                units.append(item)
            return dict(run=self.run_view(run, doc), items=units, total=0 if unavailable else run['unit_count'])

    def original(self, student, key, version_id=None):
        with self.repository.transaction():
            doc = self._document(student, key)
            version = self.storage.version(doc, version_id)
        path = self.files.verified(version['storage_key'], version['content_hash'], version['size_bytes'])
        return path, version['file_name']

    def preview(self,student,key,version_id,page):
        """Re-encode one private original page in the existing bounded worker."""
        from eduagent.documents.limits import run_worker
        import base64
        with self.repository.transaction():
            doc=self._document(student,key);version=self.storage.version(doc,version_id)
            if version['format'] not in ('pdf','png','jpg','jpeg','webp'):raise DocumentError('unsupported_document_type',415)
        path=self.files.verified(**self._file_args(version))
        a,manifest=self.files.stage();b,output=self.files.stage()
        try:
            manifest.write_text(encode(dict(path=str(path),mode='render',pages=[page])),encoding='utf-8')
            payload=run_worker(manifest,output)
            return base64.b64decode(payload['images'][0]['image_base64'],validate=True)
        finally:
            self.files.discard_stage(a);self.files.discard_stage(b)

    def _quota(self, student, byte_count, creating):
        active = self.db.execute('SELECT count(*) FROM course_documents WHERE student_id=? AND deleted_at IS NULL', (student,)).fetchone()[0]
        used = self.db.execute('SELECT coalesce(sum(size_bytes),0) FROM document_versions WHERE student_id=?', (student,)).fetchone()[0]
        if creating and active >= MAX_DOCUMENTS or used + byte_count > MAX_STORED_BYTES:
            raise DocumentError('document_too_large', 413)

    @staticmethod
    def _revision(doc, expected):
        if type(expected) is not int or expected != doc['revision']:
            raise DocumentError('revision_conflict', 409)

    def _new_run(self, doc, version_id, mode='local', pages=()):
        key, timestamp = str(uuid4()), now()
        self.storage.insert('document_parse_runs', dict(id=key, document_id=doc['id'], version_id=version_id,
            student_id=doc['student_id'], course_id=doc['course_id'], generation=doc['parse_generation'], mode=mode,
            status='pending', expected_revision=doc['revision'], parser_version=VISION_VERSION if mode == 'vision' else PARSER_VERSION,
            pages_json=encode(list(pages)), external_consent=int(mode == 'vision'), created_at=timestamp, updated_at=timestamp))
        return key

    def upload(self, student, metadata, staged_key, file_name, byte_count, file_hash, document_id=None):
        """Caller owns a bounded, hashed staging file; finally always consumes it."""
        committed_key = None
        try:
            file_name, kind = filename(file_name)
            signature(self.files.path(staged_key), kind)
            payload = dict(operation='version' if document_id else 'upload', document_id=document_id, metadata=metadata,
                           file_name=file_name, size_bytes=byte_count, content_hash=file_hash)
            request_hash = digest(payload)
            with self.repository.transaction():
                self.student(student, metadata['course_id'])
                replay = self.storage.replay(student, metadata['course_id'], metadata['request_id'], request_hash)
                if replay is not None:
                    return replay, True
                if document_id:
                    doc = self._document(student, document_id)
                    self._revision(doc, metadata['expected_revision'])
                    current = self.storage.version(doc)
                    if current['content_hash'] == file_hash:
                        value = self.view(doc)
                        self.storage.record(student, doc['course_id'], metadata['request_id'], request_hash, 'version', doc['id'], value, now())
                        return value, False
                    doc.update(revision=doc['revision'] + 1, file_revision=doc['file_revision'] + 1,
                               parse_generation=doc['parse_generation'] + 1, updated_at=now())
                else:
                    if self.db.execute('''SELECT 1 FROM document_versions v JOIN course_documents d ON d.current_version_id=v.id
                        WHERE d.student_id=? AND d.course_id=? AND d.deleted_at IS NULL AND v.content_hash=?''',
                                       (student, metadata['course_id'], file_hash)).fetchone():
                        raise DocumentError('duplicate_document', 409)
                    self._quota(student, byte_count, True)
                    timestamp = now()
                    doc = dict(id=str(uuid4()), student_id=student, course_id=metadata['course_id'], title=metadata['title'],
                               material_role=metadata['material_role'], source_note=metadata['source_note'], local_rights_confirmed=1,
                               revision=1, file_revision=1, parse_generation=1, created_at=timestamp, updated_at=timestamp, deleted_at=None)
                    self.storage.insert('course_documents', doc)
                self._quota(student, byte_count, False)
                version_id = str(uuid4())
                committed_key = self.files.commit(staged_key, doc['id'], version_id)
                self.storage.insert('document_versions', dict(id=version_id, document_id=doc['id'], student_id=student,
                    course_id=doc['course_id'], file_revision=doc['file_revision'], file_name=file_name, format=kind,
                    size_bytes=byte_count, content_hash=file_hash, storage_key=committed_key, created_at=now()))
                run_id = self._new_run(doc, version_id)
                self.db.execute('''UPDATE course_documents SET revision=?,file_revision=?,parse_generation=?,current_version_id=?,
                    current_parse_id=?,updated_at=? WHERE id=? AND student_id=?''',
                    (doc['revision'], doc['file_revision'], doc['parse_generation'], version_id, run_id, doc['updated_at'], doc['id'], student))
                self.db.execute("UPDATE document_parse_runs SET status='superseded',updated_at=? WHERE document_id=? AND id!=? AND status='pending'", (now(), doc['id'], run_id))
                value = self.view(self.storage.document(student, doc['id']))
                self.storage.record(student, doc['course_id'], metadata['request_id'], request_hash, payload['operation'], doc['id'], value, now())
            return value, False
        except BaseException as exc:
            # Only this operation's newly allocated, rolled-back file is removed.
            if committed_key and not self.db.execute('SELECT 1 FROM document_versions WHERE storage_key=?', (committed_key,)).fetchone():
                self.files.path(committed_key).unlink(missing_ok=True)
            if isinstance(exc, OSError):
                raise DocumentError('document_storage_unavailable', 503) from None
            raise
        finally:
            self.files.discard_stage(staged_key)

    def mutate(self, student, key, body, operation):
        request_hash = digest(dict(operation=operation, document_id=key, body=body))
        with self.repository.transaction():
            self.student(student)
            replay = self.storage.replay(student, 'machine_learning', body['request_id'], request_hash)
            if replay is not None:
                return replay, True
            doc = self._document(student, key)
            self._revision(doc, body['expected_revision'])
            if operation == 'delete':
                self.db.execute('UPDATE course_documents SET deleted_at=?,updated_at=?,revision=revision+1 WHERE id=? AND student_id=?', (now(), now(), key, student))
                self.db.execute("UPDATE document_parse_runs SET status='superseded',updated_at=? WHERE document_id=? AND status='pending'", (now(), key))
                value = dict(id=key, deleted=True)
            elif operation == 'update':
                self.db.execute('UPDATE course_documents SET title=?,source_note=?,updated_at=?,revision=revision+1 WHERE id=? AND student_id=?',
                                (body.get('title', doc['title']), body.get('source_note', doc['source_note']), now(), key, student))
                value = self.view(self.storage.document(student, key))
            elif operation == 'parse':
                self.files.verified(**self._file_args(self.storage.version(doc)))
                doc.update(parse_generation=doc['parse_generation'] + 1, revision=doc['revision'] + 1)
                run_id = self._new_run(doc, doc['current_version_id'])
                self.db.execute('UPDATE course_documents SET parse_generation=?,revision=?,current_parse_id=?,updated_at=? WHERE id=? AND student_id=?',
                                (doc['parse_generation'], doc['revision'], run_id, now(), key, student))
                self.db.execute("UPDATE document_parse_runs SET status='superseded' WHERE document_id=? AND mode='local' AND id!=? AND status='pending'", (key, run_id))
                value = self.view(self.storage.document(student, key))
            elif operation == 'vision':
                if not self.vision_enabled or not self.agent or not self.agent.api_key:
                    raise DocumentError('vision_disabled', 503)
                if body.get('consent_external') is not True:
                    raise DocumentError('external_consent_required', 422)
                version = self.storage.version(doc)
                if version['format'] not in ('pdf','png','jpg','jpeg','webp'):
                    raise DocumentError('vision_requires_pdf')
                if body['version_id'] != version['id']:
                    raise DocumentError('revision_conflict', 409)
                pages = body['pages']
                available = self.storage.run(doc)['unit_count']
                if (not 1 <= len(pages) <= VISION_MAX_PAGES or len(set(pages)) != len(pages)
                        or any(type(page) is not int or not 1 <= page <= available for page in pages)):
                    raise ValueError('请选择1～3个已解析的有效PDF页码')
                run_id = self._new_run(doc, version['id'], 'vision', pages)
                value = self.run_view(self.storage.run(doc, run_id), doc)
            else:
                raise ValueError('无效的资料操作')
            self.storage.record(student, doc['course_id'], body['request_id'], request_hash, operation, key, value, now())
            return value, False

    @staticmethod
    def _file_args(version):
        return dict(key=version['storage_key'], digest=version['content_hash'], size=version['size_bytes'])

    def recover(self):
        with self.repository.transaction():
            self.db.execute("UPDATE document_parse_runs SET status='uncertain',error_code='execution_unconfirmed',updated_at=? WHERE mode='vision' AND status='processing'", (now(),))
            self.db.execute("UPDATE document_parse_runs SET status='failed',error_code='parse_interrupted',updated_at=? WHERE mode='local' AND status='processing' AND recovery_count>=1", (now(),))
            self.db.execute("UPDATE document_parse_runs SET status='pending',recovery_count=recovery_count+1,build_token=NULL,updated_at=? WHERE mode='local' AND status='processing'", (now(),))
        # Startup integrity audit is outside write transactions. A matching head
        # is rechecked before changing state; no model requests are recovered.
        for row in self.db.execute('SELECT * FROM course_documents WHERE deleted_at IS NULL').fetchall():
            doc = dict(row); version = self.storage.version(doc); run = self.storage.run(doc)
            code = None
            try:
                self.files.verified(**self._file_args(version))
            except DocumentError:
                code = 'original_unavailable'
            if not code and run['status'] in ('ready', 'partial', 'empty'):
                try:
                    self.files.verified(run['artifact_key'], run['artifact_hash'], run['artifact_bytes'])
                except (DocumentError, TypeError):
                    code = 'derived_unavailable'
            if code:
                with self.repository.transaction():
                    self.db.execute('''UPDATE document_parse_runs SET status='failed',error_code=?,updated_at=?
                        WHERE id=? AND EXISTS (SELECT 1 FROM course_documents WHERE id=? AND current_parse_id=? AND current_version_id=? AND deleted_at IS NULL)''',
                        (code, now(), run['id'], doc['id'], run['id'], version['id']))

    def _current(self, run):
        doc = self.storage.document(run['student_id'], run['document_id'], include_deleted=True)
        return (not doc['deleted_at'] and doc['current_version_id'] == run['version_id']
                and doc['parse_generation'] == run['generation']
                and (run['mode'] == 'local' or doc['revision'] == run['expected_revision']))

    def claim(self):
        with self.repository.transaction():
            row = self.db.execute("SELECT * FROM document_parse_runs WHERE status='pending' ORDER BY created_at,id LIMIT 1").fetchone()
            if row is None:
                return None
            run = dict(row)
            if not self._current(run) or run['mode'] == 'vision' and not self.vision_enabled:
                self.db.execute("UPDATE document_parse_runs SET status='superseded',updated_at=? WHERE id=?", (now(), run['id']))
                return None
            run.update(build_token=str(uuid4()), status='processing')
            self.db.execute("UPDATE document_parse_runs SET status='processing',build_token=?,updated_at=? WHERE id=? AND status='pending'", (run['build_token'], now(), run['id']))
            return run

    def _owned_run(self, run):
        row = self.db.execute("SELECT * FROM document_parse_runs WHERE id=? AND build_token=? AND status='processing'", (run['id'], run['build_token'])).fetchone()
        return dict(row) if row else None

    def before_model(self, run):
        with self.repository.transaction():
            current = self._owned_run(run)
            if not current or not self._current(current) or current['model_calls'] >= len(json.loads(run['pages_json'])):
                raise DocumentError('revision_conflict', 409)
            if not self.vision_enabled or not current['external_consent']:
                raise DocumentError('external_consent_required')
            self.db.execute('UPDATE document_parse_runs SET model_calls=model_calls+1,updated_at=? WHERE id=?', (now(), run['id']))

    def publish(self, run, payload, usage=None):
        from eduagent.documents.models import MAX_OUTPUT
        if len(encode(payload).encode('utf8')) > MAX_OUTPUT:
            raise DocumentError('document_too_large', 413)
        artifact_key = None
        try:
            with self.repository.transaction():
                if not self._owned_run(run):
                    return
                current = self._current(run)
                used = self.db.execute('SELECT coalesce(sum(artifact_bytes),0) FROM document_parse_runs WHERE student_id=?', (run['student_id'],)).fetchone()[0]
                if used + len(encode(payload).encode('utf8')) > MAX_DERIVED_BYTES:
                    raise DocumentError('document_too_large', 413)
                artifact_key, artifact_hash, size = self.files.artifact(run['id'], payload)
                for item in payload['units']:
                    self.storage.insert('document_units', dict(id=str(uuid4()), run_id=run['id'], version_id=run['version_id'],
                        document_id=run['document_id'], student_id=run['student_id'], course_id=run['course_id'],
                        ordinal=item['ordinal'], kind=item['kind'], title=item['title'], text=item['text'], content_md=item['content_md'],
                        interpretation_md=item.get('interpretation_md', ''), origin=item['origin'], location_json=encode(item['location']),
                        blocks_json=encode(item['blocks']), warnings_json=encode(item['warnings']), content_hash=digest(item)))
                self.db.execute('''UPDATE document_parse_runs SET status=?,unit_count=?,warnings_json=?,artifact_key=?,artifact_hash=?,artifact_bytes=?,
                    usage_json=?,model=?,updated_at=? WHERE id=? AND build_token=?''',
                    (payload['status'] if current else 'superseded', len(payload['units']), encode(payload['warnings']), artifact_key, artifact_hash, size,
                     encode(usage or dict(prompt_tokens=0, completion_tokens=0)), VISION_MODEL if run['mode'] == 'vision' else None,
                     now(), run['id'], run['build_token']))
        except BaseException:
            if artifact_key and not self.db.execute('SELECT 1 FROM document_parse_runs WHERE artifact_key=?', (artifact_key,)).fetchone():
                self.files.path(artifact_key).unlink(missing_ok=True)
            raise

    def fail(self, run, code, *, uncertain=False, usage=None):
        with self.repository.transaction():
            if self._owned_run(run):
                self.db.execute('UPDATE document_parse_runs SET status=?,error_code=?,usage_json=?,updated_at=? WHERE id=? AND build_token=?',
                    ('uncertain' if uncertain else 'failed' if self._current(run) else 'superseded', code,
                     encode(usage or dict(prompt_tokens=0, completion_tokens=0)), now(), run['id'], run['build_token']))

    def execute(self, run, runner, vision_factory=None, cancel=None):
        """CPU parsing and network requests are outside write transactions."""
        from eduagent.agent.deepseek import ModelError
        from eduagent.documents.limits import run_worker
        runner = runner or run_worker
        usage = dict(prompt_tokens=0, completion_tokens=0)
        paths = []
        try:
            doc = self.storage.document(run['student_id'], run['document_id'], include_deleted=True)
            version = self.storage.version(doc, run['version_id'])
            path = self.files.verified(**self._file_args(version))
            manifest_key, manifest = self.files.stage(); output_key, output = self.files.stage()
            paths = [manifest_key, output_key]
            request = dict(path=str(path), kind=version['format'], mode='render' if run['mode'] == 'vision' else 'local', pages=json.loads(run['pages_json']))
            manifest.write_text(encode(request), encoding='utf8')
            payload = runner(manifest, output, cancel=cancel)
            if run['mode'] == 'vision':
                units = []
                client = vision_factory() if vision_factory else default_client(self.agent)
                for image in payload['images']:
                    self.before_model(run)
                    item, tokens = transcribe(client, image)
                    units.append(item)
                    for name in usage:
                        usage[name] += tokens[name]
                payload = result(units, ['model_extraction_requires_review'])
            # Recheck immutable original bytes before publishing derived content.
            self.files.verified(**self._file_args(version))
            self.publish(run, payload, usage)
        except ModelError as exc:
            usage['prompt_tokens'] += exc.prompt_tokens
            usage['completion_tokens'] += exc.completion_tokens
            self.fail(run, exc.code, uncertain=exc.code in ('model_timeout', 'network_error', 'upstream_error'), usage=usage)
        except DocumentError as exc:
            for key, value in getattr(exc, 'usage', {}).items():
                usage[key] += value
            self.fail(run, exc.code, usage=usage)
        except Exception:
            self.fail(run, 'parse_failed', usage=usage)
        finally:
            for key in paths:
                self.files.discard_stage(key)
