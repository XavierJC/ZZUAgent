"""Persistent notebooks, explicit membership, and bounded capability composition.

Open Notebook's notebook/source/note relationship is implemented with the local
SQLite repository. It does not copy content, replace the retrieval engine, or
relax EduAgent's stricter empty-scope and per-turn transmission contracts.
"""
from dataclasses import asdict
from hashlib import sha256
import json
from uuid import uuid4

from eduagent.documents.models import uuid_text
from eduagent.domain.architecture import ArchitectureError
from eduagent.domain.notes import NoteConflict, NoteNotFound
from eduagent.domain.personal_bank import fail
from eduagent.services.knowledge import SourceChanged, IndexUnavailable, note_version
from eduagent.services.learning import now
from eduagent.services.study_workspace.context import NotebookContext
from eduagent.storage.notebooks import NotebookRepository
from eduagent.storage.sqlite import encode

COURSE = 'machine_learning'
SOURCE_FIELDS = ('source_type', 'source_id', 'source_version')


class NotebookService:
    def __init__(self, learning, workbench, bank):
        self.learning, self.workbench, self.bank = learning, workbench, bank
        self.repository = learning.repository
        self.store = NotebookRepository(self.repository)
        self.db = self.repository.connection

    def notebook(self, student, key, *, active=False):
        self.learning._student(student)
        uuid_text(key)
        row = self.store.get(student, key)
        if row is None: raise NoteNotFound('当前学习标识下没有该笔记本')
        if active and row['archived']: raise NoteConflict('笔记本已归档，请先恢复再继续')
        return row

    def list(self, student, archived=False):
        with self.repository.transaction():
            self.learning._student(student)
            return dict(items=self.store.list(student, archived))

    def receipt(self, student, request_id):
        with self.repository.transaction():
            self.learning._student(student); uuid_text(request_id)
            row = self.store.operation(student, request_id)
            if row is None: raise NoteNotFound('当前学习标识下没有该笔记本操作回执')
            return json.loads(row['result_json'])

    def _resolve(self, student, ref):
        kind, key = ref['source_type'], ref['source_id']
        knowledge = self.workbench.knowledge
        if kind == 'personal_question':
            row = self.bank.row(student, key)
            return dict(source_type=kind, source_id=key, source_version=f"r{row['revision']}",
                        title=json.loads(row['payload_json'])['stem'][:120], index_status='ready' if row['status'] == 'practice' else 'pending')
        if kind == 'personal_note':
            row = self.db.execute('SELECT id,title,revision,content_hash FROM notes WHERE id=? AND student_id=? AND course_id=? AND deleted_at IS NULL', (key, student, COURSE)).fetchone()
            if row is None: raise NoteNotFound('当前学习标识下没有该资料')
            state = self.db.execute('SELECT status FROM note_index_state WHERE note_id=?', (key,)).fetchone()
            return dict(source_type=kind, source_id=key, source_version=note_version(row), title=row['title'],
                        source_revision=row['revision'], content_hash=row['content_hash'], knowledge_point_ids=[],
                        review_status='personal_unverified', index_status=state['status'] if state else 'pending', error_code=None)
        if kind == 'course_material':
            if knowledge.courses is None: raise IndexUnavailable('课程资料不可用')
            knowledge.courses.verify()
            source = next((s for s in knowledge.courses.sources() if s['source_id'] == key), None)
            if source is None: raise NoteNotFound('当前学习标识下没有该资料')
            return source
        provider = knowledge.documents if kind == 'uploaded_document' else knowledge.teachers if kind == 'teaching_material' else None
        if provider is None: raise ValueError('来源类型无效')
        source = provider.source(student, key)
        return {k: v for k, v in source.items() if k not in ('units', 'preview_units', 'links', 'document')}

    def get(self, student, key):
        with self.repository.transaction():
            row = self.notebook(student, key)
            items = []
            for ref in self.store.sources(student, key):
                item = {k: ref[k] for k in SOURCE_FIELDS}
                try:
                    source = self._resolve(student, ref)
                    status = 'current' if source['source_version'] == ref['source_version'] else 'modified'
                    item.update(source, source_version=ref['source_version'], current_version=source['source_version'], current_status=status)
                except (ArchitectureError, NoteNotFound, SourceChanged, IndexUnavailable, ValueError):
                    item.update(title=ref['title_snapshot'], current_status='unavailable', index_status='failed', error_code='source_unavailable')
                items.append(item)
            return {**row, 'sources': items, 'item_count': len(items), 'conversation_count': len(self.store.runs(student, key))}

    def _write(self, student, key, body, operation, apply):
        uuid_text(body['request_id'])
        checksum = sha256(encode([operation, key, body]).encode()).hexdigest()
        with self.repository.transaction():
            self.learning._student(student)
            previous = self.store.operation(student, body['request_id'])
            if previous:
                if previous['request_hash'] != checksum: raise NoteConflict('请求编号已用于其他内容')
                return {**json.loads(previous['result_json']), 'replayed': True}
            result = apply()
            self.store.record_operation(student, body['request_id'], key, checksum, result, now())
            return {**result, 'replayed': False}

    def create(self, student, body):
        key = body['id']; uuid_text(key)
        def apply():
            if self.db.execute('SELECT 1 FROM notebooks WHERE id=?', (key,)).fetchone(): raise NoteConflict('笔记本编号不可用')
            if self.db.execute('SELECT count(*) FROM notebooks WHERE student_id=?', (student,)).fetchone()[0] >= 100:
                fail('每个演示标识最多保留100个笔记本', status=413)
            stamp = now()
            self.db.execute('INSERT INTO notebooks VALUES (?,?,?,?,?,?,?,?,?)', (key, student, COURSE, body['title'].strip(), body['description'].strip(), 1, 0, stamp, stamp))
            return dict(id=key, revision=1)
        return self._write(student, key, body, 'create', apply)

    def update(self, student, key, body):
        def apply():
            row = self.notebook(student, key)
            if row['revision'] != body['expected_revision']: raise NoteConflict('笔记本已有新版本，请刷新后保存')
            self.db.execute('UPDATE notebooks SET title=?,description=?,archived=?,revision=revision+1,updated_at=? WHERE id=? AND student_id=?',
                            (body['title'].strip(), body['description'].strip(), int(body['archived']), now(), key, student))
            return dict(id=key, revision=row['revision'] + 1)
        return self._write(student, key, body, 'update', apply)

    def set_sources(self, student, key, body):
        def apply():
            row = self.notebook(student, key, active=True)
            if row['revision'] != body['expected_revision']: raise NoteConflict('笔记本已有新版本，请刷新后选择')
            refs = body['sources']; seen = set(); resolved = []
            for ref in refs:
                identity = (ref['source_type'], ref['source_id'])
                if identity in seen: raise ValueError('同一来源不能重复关联')
                seen.add(identity)
                source = self._resolve(student, ref)
                if source['source_version'] != ref['source_version']: raise SourceChanged('来源版本已变化，请重新选择')
                resolved.append((ref, source))
            self.db.execute('DELETE FROM notebook_sources WHERE notebook_id=? AND student_id=?', (key, student))
            for ref, source in resolved:
                self.db.execute('INSERT INTO notebook_sources VALUES (?,?,?,?,?,?,?,?)',
                    (key, student, COURSE, ref['source_type'], ref['source_id'], ref['source_version'], source['title'], now()))
            self.db.execute('UPDATE notebooks SET revision=revision+1,updated_at=? WHERE id=? AND student_id=?', (now(), key, student))
            return dict(id=key, revision=row['revision'] + 1)
        return self._write(student, key, body, 'sources', apply)

    def context(self, student, key, revision, refs):
        row = self.notebook(student, key, active=True)
        if row['revision'] != revision: raise SourceChanged('笔记本资料范围已变化，请刷新后重试')
        if not 1 <= len(refs) <= 55: raise ValueError('请明确选择1～55项笔记本内资料')
        members = {(r['source_type'], r['source_id']): r['source_version'] for r in self.store.sources(student, key)}
        selected = []
        for ref in refs:
            identity = (ref['source_type'], ref['source_id'])
            if ref['source_type'] == 'personal_question' or members.get(identity) != ref['source_version']:
                raise NoteConflict('所选资料不属于本轮笔记本范围，请重新选择')
            if identity in [(a, b) for a, b, _ in selected]: raise ValueError('不能重复选择来源')
            selected.append((*identity, ref['source_version']))
        return NotebookContext(student, key, COURSE, revision, tuple(selected))

    def guard(self, context):
        try: self.context(context.student_id, context.notebook_id, context.revision, context.refs())
        except (NoteConflict, NoteNotFound) as exc: raise SourceChanged('笔记本范围已变化') from exc

    def preview(self, student, key, body):
        with self.repository.transaction():
            ref = {k: body[k] for k in SOURCE_FIELDS}
            self.context(student, key, body['expected_revision'], [ref])
            return self.workbench.preview(student, ref, body.get('page'))

    def run(self, student, key, request_id):
        with self.repository.transaction():
            notebook = self.notebook(student, key)
            row = self.store.run(student, key, request_id)
            if row is None: raise NoteNotFound('当前笔记本下没有该问答记录')
            try: result = self.workbench.get(student, request_id)
            except NoteNotFound:
                body = json.loads(row['request_json'])
                result = dict(request_id=request_id, question=body['question'], status='uncertain', answer='', citations=[],
                              selected_sources=[], source_statuses=[], model_calls=0, reason='execution_unconfirmed',
                              created_at=row['created_at'], updated_at=row['created_at'], saved_note_id=None)
            stale = notebook['revision'] != row['notebook_revision'] or bool(notebook['archived'])
            return {**result, 'notebook_id': key, 'notebook_revision': row['notebook_revision'], 'notebook_context_stale': stale,
                    'status': 'stale' if stale and result['status'] != 'uncertain' else result['status']}

    def history(self, student, key):
        with self.repository.transaction():
            self.notebook(student, key)
            return [self.run(student, key, r['request_id']) for r in self.store.runs(student, key)]

    def ask(self, student, key, body):
        request_id = body['request_id']; uuid_text(request_id)
        checksum = sha256(encode(body).encode()).hexdigest()
        with self.repository.transaction():
            self.notebook(student, key)
            old = self.store.run(student, key, request_id)
            if old:
                if old['request_hash'] != checksum: raise NoteConflict('请求编号已用于其他问题或资料')
                return self.run(student, key, request_id)
            context = self.context(student, key, body['expected_revision'], body['sources'])
            # Fail invalid/stale source refs before claiming a paid request.
            self.workbench.knowledge._validate(student, context.refs(), COURSE)
            if self.db.execute('SELECT 1 FROM notebook_runs WHERE request_id=?', (request_id,)).fetchone() or self.db.execute('SELECT 1 FROM workbench_runs WHERE request_id=?', (request_id,)).fetchone():
                raise NoteConflict('请求编号不可用')
            self.db.execute('INSERT INTO notebook_runs VALUES (?,?,?,?,?,?,?,?,?)',
                (request_id, key, student, COURSE, context.revision, checksum, encode(body), encode(asdict(context)), now()))
        # Durable reservation precedes provider execution. Never retry a reservation
        # whose billable execution cannot be confirmed after timeout/restart.
        self.workbench.lesson_guard = lambda: self.guard(context)
        self.workbench.ask(student, {k: v for k, v in body.items() if k != 'expected_revision'})
        return self.run(student, key, request_id)

    def save_answer(self, student, key, request_id):
        with self.repository.transaction():
            self.notebook(student, key, active=True)
            self.run(student, key, request_id)  # Cannot adopt another notebook's receipt.
            result = self.workbench.save_note(student, request_id)
            if result.get('deleted'): return result
            ref = dict(source_type='personal_note', source_id=result['note_id'], source_version='')
            source = self._resolve(student, ref)
            found = self.db.execute('SELECT 1 FROM notebook_sources WHERE notebook_id=? AND source_type=? AND source_id=?', (key, 'personal_note', result['note_id'])).fetchone()
            if not found:
                self.db.execute('INSERT INTO notebook_sources VALUES (?,?,?,?,?,?,?,?)', (key, student, COURSE, 'personal_note', result['note_id'], source['source_version'], source['title'], now()))
                self.db.execute('UPDATE notebooks SET revision=revision+1,updated_at=? WHERE id=?', (now(), key))
        return result

    def questions(self, student, key):
        with self.repository.transaction():
            self.notebook(student, key)
            members = self.store.sources(student, key)
            originals, explicit = set(), set()
            for ref in members:
                try: current = self._resolve(student, ref)
                except (ValueError, NoteNotFound, ArchitectureError, IndexUnavailable): continue
                if current['source_version'] != ref['source_version']: continue
                if ref['source_type'] == 'personal_question': explicit.add(ref['source_id'])
                elif ref['source_type'] == 'uploaded_document': originals.add(('document', ref['source_id'], current['version_id']))
                elif ref['source_type'] == 'personal_note': originals.add(('personal_note', ref['source_id'], ref['source_version']))
            items = []
            for row in self.db.execute("SELECT * FROM personal_questions WHERE student_id=? AND course_id=? AND status!='archived' ORDER BY updated_at DESC,id", (student, COURSE)):
                source = json.loads(row['source_json'])
                if row['id'] in explicit or (source.get('original_source_type'), source.get('original_source_id'), source.get('source_version')) in originals:
                    items.append(self.bank.view(student, dict(row)))
            return dict(items=items)

    def start_practice(self, student, key, body):
        def apply():
            row = self.notebook(student, key, active=True)
            if row['revision'] != body['expected_revision']: raise SourceChanged('笔记本范围已变化，请刷新')
            allowed = {q['id'] for q in self.questions(student, key)['items'] if q['status'] == 'practice' and q['source_status'] in ('current', 'manual')}
            if body['question_id'] not in allowed: raise NoteConflict('该题不在当前笔记本的可练习范围内')
            if self.db.execute('SELECT 1 FROM personal_bank_operations WHERE student_id=? AND request_id=?', (student, body['request_id'])).fetchone():
                raise NoteConflict('请求编号不可用')
            result = self.bank.start(student, {k: body[k] for k in ('request_id', 'question_id')})
            self.db.execute('INSERT INTO notebook_practice VALUES (?,?,?,?,?)', (result['session_id'], key, student, COURSE, now()))
            return result
        return self._write(student, key, body, 'practice', apply)

    def question(self, student, key, question_id):
        uuid_text(question_id)
        result = next((q for q in self.questions(student, key)['items'] if q['id'] == question_id), None)
        if result is None: raise NoteNotFound('当前笔记本下没有该题目')
        return result

    def practice_session(self, student, key, session_id):
        with self.repository.transaction():
            self.notebook(student, key); uuid_text(session_id)
            if not self.db.execute('SELECT 1 FROM notebook_practice WHERE notebook_id=? AND student_id=? AND session_id=?', (key, student, session_id)).fetchone():
                raise NoteNotFound('当前笔记本下没有该练习记录')
            return self.bank.session(student, session_id)

    def practice_history(self, student, key):
        with self.repository.transaction():
            self.notebook(student, key)
            rows = self.db.execute('SELECT session_id FROM notebook_practice WHERE notebook_id=? AND student_id=? ORDER BY created_at DESC,session_id LIMIT 100', (key, student)).fetchall()
            return dict(items=[self.bank.session(student, r['session_id']) for r in rows])

    def submit_practice(self, student, key, session_id, body, *, draft=False):
        with self.repository.transaction():
            self.notebook(student, key, active=True)
            self.practice_session(student, key, session_id)
            return (self.bank.save_practice_draft if draft else self.bank.submit)(student, session_id, body)

    def practice_receipt(self, student, key, request_id):
        with self.repository.transaction():
            self.notebook(student, key)
            operation = self.store.operation(student, request_id)
            if operation:
                if operation['notebook_id'] != key: raise NoteNotFound('当前笔记本下没有该练习回执')
                result = json.loads(operation['result_json'])
            else: result = self.bank.receipt(student, request_id)
            if not result.get('session_id'): raise NoteNotFound('当前笔记本下没有该练习回执')
            self.practice_session(student, key, result['session_id'])
            return result
