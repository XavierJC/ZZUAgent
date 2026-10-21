"""Durable, student-scoped workbench receipts. No grading or planning writes.

A committed claim precedes every possible provider call. An interrupted claim
is deliberately not taken over: its billable execution cannot be inferred from
an HTTP timeout. Notes and immutable historical excerpts stay local unless the
specific request authorizes the selected note excerpts.
"""

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from uuid import UUID, uuid4

from eduagent.domain.notes import NoteConflict, NoteNotFound
from eduagent.services.knowledge import KnowledgeService, SourceChanged, IndexUnavailable, note_version
from eduagent.services.learning import now
from eduagent.services.notes import NotesService


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


@dataclass(frozen=True)
class RequestContext:
    student_id: str
    course_id: str
    request_id: str
    sources: tuple[tuple[str, str, str], ...]
    allow_personal_external: bool
    state_revision: int

    def refs(self):
        return [dict(zip(('source_type', 'source_id', 'source_version'), ref)) for ref in self.sources]


class WorkbenchService:
    def __init__(self, learning, courses=None, enabled=True, settings=None, client_factory=None):
        self.learning, self.repository = learning, learning.repository
        self.db = self.repository.connection
        self.knowledge = KnowledgeService(learning.catalog, self.repository, courses, enabled)
        self.settings, self.client_factory = settings, client_factory

    def _row(self, student, request_id):
        self.knowledge.student(student, 'machine_learning')
        row = self.db.execute('SELECT * FROM workbench_runs WHERE student_id=? AND request_id=?', (student, request_id)).fetchone()
        if row is None:
            raise NoteNotFound('当前学习标识下没有该工作台记录')
        return row

    def _source_status(self, student, refs):
        statuses = []
        for ref in refs:
            status = 'current'
            if ref['source_type'] == 'personal_note':
                row = self.db.execute('SELECT * FROM notes WHERE student_id=? AND course_id=? AND id=?',
                                      (student, 'machine_learning', ref['source_id'])).fetchone()
                status = ('deleted' if row is None or row['deleted_at'] else
                          'modified' if note_version(row) != ref['source_version'] else 'current')
            else:
                courses = self.knowledge.courses
                document = courses.documents.get(ref['source_id']) if courses else None
                status = 'unavailable' if document is None else 'current'
                if document and document['source_version'] != ref['source_version']:
                    status = 'modified'
                if status == 'current':
                    try:
                        courses.verify()
                    except SourceChanged:
                        status = 'modified'
            statuses.append({**ref, 'current_status': status})
        return statuses

    def _view(self, row):
        result = json.loads(row['result_json'])
        # Older immutable receipts predate this optional response metadata.
        result.setdefault('answer_basis', 'selected_sources' if row['status'] == 'complete' and result.get('citations')
                          else 'local_excerpts' if result.get('citations') else 'none')
        result.setdefault('validation_error', None)
        result.setdefault('validation_summary', None)
        result.setdefault('supplement_md', '')
        result.setdefault('finish_reason', None)
        result.setdefault('max_output_tokens', None)
        result.update(request_id=row['request_id'], course_id=row['course_id'], status=row['status'],
                      model_calls=row['model_calls'], created_at=row['created_at'], updated_at=row['updated_at'])
        context = json.loads(row['context_json'])
        result['context'] = context
        result['source_statuses'] = self._source_status(row['student_id'], context['sources'])
        if row['status'] == 'running':
            result.update(status='uncertain', reason='execution_unconfirmed')
        origin = self.db.execute('SELECT note_id FROM workbench_note_origins WHERE request_id=?', (row['request_id'],)).fetchone()
        result['saved_note_id'] = origin['note_id'] if origin else None
        return result

    def get(self, student, request_id):
        with self.repository.transaction():
            return self._view(self._row(student, request_id))

    def history(self, student, limit=20):
        if type(limit) is not int or not 1 <= limit <= 50:
            raise ValueError('记录数量必须为1～50')
        with self.repository.transaction():
            self.knowledge.student(student, 'machine_learning')
            rows = self.db.execute('SELECT * FROM workbench_runs WHERE student_id=? ORDER BY created_at DESC,request_id DESC LIMIT ?',
                                   (student, limit)).fetchall()
            return [self._view(row) for row in rows]

    def preview(self, student, ref):
        with self.repository.transaction():
            self.knowledge.student(student, 'machine_learning')
            if ref['source_type'] == 'personal_note':
                note = self.knowledge.personal.note(student, ref['source_id'], 'machine_learning')
                if note_version(note) != ref['source_version']:
                    raise SourceChanged('来源版本已变化，请刷新来源列表')
                return {**ref, 'title': note['title'], 'raw_md': note['content_md']}
            if ref['source_type'] == 'course_material' and self.knowledge.courses:
                self.knowledge.courses.verify()
                doc = self.knowledge.courses.documents.get(ref['source_id'])
                if not doc:
                    raise NoteNotFound('所选来源不存在')
                if doc['source_version'] != ref['source_version']:
                    raise SourceChanged('来源版本已变化，请刷新来源列表')
                return {**ref, 'title': doc['title'], 'raw_md': doc['text']}
            raise IndexUnavailable('课程来源不可用')

    def validate_context(self, context):
        with self.repository.transaction():
            _, courses = self.knowledge._validate(context.student_id, context.refs(), context.course_id)
            if courses:
                self.knowledge.courses.verify()
            if self.repository.student(context.student_id)['revision'] != context.state_revision:
                raise SourceChanged('学习状态已变化，请重新发起一轮问答')

    def ask(self, student, body):
        request_id = str(UUID(body['request_id']))
        if request_id != body['request_id']:
            raise ValueError('request_id 必须使用标准小写 UUID')
        if not body['question'].strip() or len(body['question']) > 1000:
            raise ValueError('问题必须为1～1000字符')
        if type(body['allow_personal_external']) is not bool or body['mode'] not in ('local', 'model'):
            raise ValueError('问答模式或授权无效')
        digest = sha256(encode(body).encode()).hexdigest()
        with self.repository.transaction():
            self.knowledge.student(student, body['course_id'])
            existing = self.db.execute('SELECT * FROM workbench_runs WHERE request_id=?', (request_id,)).fetchone()
            if existing:
                if existing['student_id'] != student:
                    raise NoteNotFound('当前学习标识下没有该工作台记录')
                if existing['request_hash'] != digest:
                    raise NoteConflict('请求编号已用于其他内容；不能重新生成或复用授权')
                return self._view(existing)
        # Validating before claiming prevents invalid source sets from becoming
        # records, while a second check at claim time closes the intervening race.
        evidence = self.knowledge.search(student, body['question'], body['sources'], body['course_id'], top_k=5)['items']
        snapshot = self.learning.snapshot(student)
        context = RequestContext(student, body['course_id'], request_id,
            tuple((s['source_type'], s['source_id'], s['source_version']) for s in body['sources']),
            body['allow_personal_external'], snapshot.revision)
        learning_state = {'goals': list(snapshot.goals), 'revision': snapshot.revision,
                          'mastery': [asdict(item) for item in snapshot.mastery]}
        # Capture titles only for the already selected sources; never enumerate
        # other personal notes for a course-only request.
        with self.repository.transaction():
            selected_notes, selected_courses = self.knowledge._validate(student, context.refs(), context.course_id)
            if selected_courses:
                self.knowledge.courses.verify()
            if self.repository.student(student)['revision'] != context.state_revision:
                raise SourceChanged('学习状态已变化，请重试')
            titles = {('personal_note', n['id']): n['title'] for n, _ in selected_notes}
            titles.update({('course_material', key): self.knowledge.courses.documents[key]['title'] for key in selected_courses})
            initial = {'question': body['question'], 'answer': '', 'citations': [], 'reason': None,
                       'model': None, 'provider': 'DeepSeek' if body['mode'] == 'model' else None,
                       'finish_reason': None, 'max_output_tokens': self.settings.max_tokens if self.settings else None,
                       'tools_used': [], 'usage': {'prompt_tokens': 0, 'completion_tokens': 0},
                       'selected_sources': [{**s, 'title': titles[(s['source_type'], s['source_id'])]} for s in context.refs()]}
            timestamp = now()
            # A concurrent identical request may have claimed while retrieval ran.
            existing = self.db.execute('SELECT * FROM workbench_runs WHERE request_id=?', (request_id,)).fetchone()
            if existing:
                if existing['student_id'] != student:
                    raise NoteNotFound('当前学习标识下没有该工作台记录')
                if existing['request_hash'] != digest:
                    raise NoteConflict('请求编号冲突')
                return self._view(existing)
            context_json = {**asdict(context), 'sources': context.refs()}
            self.db.execute('INSERT INTO workbench_runs VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                (request_id, student, context.course_id, digest, encode(body), encode(context_json), encode(initial), 'running', 0, timestamp, timestamp))
        reason = ('local_requested' if body['mode'] == 'local' else
                  'personal_consent_required' if selected_notes and not context.allow_personal_external else
                  'model_disabled' if not self.settings or not self.settings.enabled else None)
        status, output = 'local', {}
        if reason is None:
            from eduagent.agent.workbench import WorkbenchAgent
            try:
                client = self.client_factory() if self.client_factory else None
                output = WorkbenchAgent(self, context, client, self.settings, learning_state).run(body['question'], evidence)
                reason = output.get('reason')
                status = 'complete' if not reason else ('uncertain' if reason in (
                    'model_timeout', 'network_error', 'upstream_error', 'invalid_model_response') else 'local')
                if output.get('answer') or output.get('supplement_md'):
                    supplemental = output.get('supplement_md', '')
                    has_sources = bool(output.get('citations'))
                    output['answer_basis'] = 'mixed' if has_sources and supplemental else 'selected_sources' if has_sources else 'model_knowledge'
                    if supplemental:
                        output['answer'] = ((output['answer'] + '\n\n') if output.get('answer') else '') + '### 模型知识补充（无本地资料引用）\n\n' + supplemental
            except (SourceChanged, NoteNotFound, IndexUnavailable):
                reason, status = 'context_changed', 'stale'
            except Exception:
                # A provider may already have received the request. No upstream
                # payload, credentials or exception text is persisted or exposed.
                reason, status = 'execution_unconfirmed', 'uncertain'
        if not output.get('answer'):
            # Keep the local excerpt answer small enough to save through the
            # unchanged 64 KiB note contract, including its provenance footer.
            local_evidence, size = [], 0
            for item in evidence:
                item_size = len(item['raw_md'].encode('utf-8'))
                if size + item_size <= 48000:
                    local_evidence.append(item)
                    size += item_size
            output.update(answer=('以下为本地检索片段，并非模型生成的解释。\n\n' + '\n\n'.join(
                f"{item['raw_md']} [{item['citation_id']}]" for item in local_evidence)) if local_evidence else '所选资料中未找到足够依据，请调整问题或选择资料。',
                citations=local_evidence, answer_basis='local_excerpts' if local_evidence else 'none')
        with self.repository.transaction():
            try:
                _, courses = self.knowledge._validate(student, context.refs(), context.course_id)
                if courses:
                    self.knowledge.courses.verify()
                if self.repository.student(student)['revision'] != context.state_revision:
                    raise SourceChanged('状态变化')
            except (SourceChanged, NoteNotFound, IndexUnavailable):
                status, reason = 'stale', 'context_changed'
            result = {**initial, **output, 'reason': reason}
            self.db.execute('UPDATE workbench_runs SET status=?,result_json=?,updated_at=? WHERE request_id=? AND status=?',
                            (status, encode(result), now(), request_id, 'running'))
        return self.get(student, request_id)

    def before_model(self, context):
        self.validate_context(context)
        with self.repository.transaction():
            self.db.execute('UPDATE workbench_runs SET model_calls=model_calls+1,updated_at=? WHERE request_id=? AND student_id=? AND status=?',
                            (now(), context.request_id, context.student_id, 'running'))

    def save_note(self, student, request_id):
        run = self.get(student, request_id)
        if run['status'] not in ('complete', 'local', 'stale') or not run['answer']:
            raise NoteConflict('该请求状态尚不能另存笔记，请先核对记录')
        existing = self.db.execute('SELECT note_id FROM workbench_note_origins WHERE request_id=?', (request_id,)).fetchone()
        if not existing:
            note_id = str(uuid4())
            # Serialize competing saves with the same note service transaction;
            # an existing origin raises a local conflict, then returns its ID.
            def attach(key, content_hash, timestamp):
                if self.db.execute('SELECT 1 FROM workbench_note_origins WHERE request_id=?', (request_id,)).fetchone():
                    raise NoteConflict('该回答已保存')
                self.db.execute('INSERT INTO workbench_note_origins VALUES (?,?,?,?,?,?,?)',
                    (request_id, key, 1, content_hash, run['updated_at'], timestamp, encode(run['citations'])))
            body = (run['answer'] + '\n\n---\n来源：EduAgent 工作台回答\n'
                    + f"生成时间：{run['updated_at']}\n请求编号：{request_id}\n"
                    + ('回答依据：模型自身知识，本轮未使用本地片段作为回答依据，无本地资料引用。\n' if run['answer_basis'] == 'model_knowledge' else '')
                    + ('回答依据：本地资料与模型知识补充；补充部分不是资料原文。\n' if run['answer_basis'] == 'mixed' else '')
                    + '\n'.join(f"- [{c['citation_id']}] {c['title']}（{c['source_type']}，版本 {c['source_version']}，行 {c['start_line']}–{c['end_line']}）" for c in run['citations'])
                    + '\n\n此笔记可编辑；编辑后的内容不代表原始回答。引用快照保留在工作台历史中。')
            links = sorted({key for c in run['citations'] for key in c['knowledge_point_ids']})
            try:
                NotesService(self.learning.catalog, self.repository).create(student, id=note_id,
                    title=('助教回答：' + run['question'])[:120], content_md=body, knowledge_point_ids=links, _on_create=attach)
            except NoteConflict:
                if not self.db.execute('SELECT 1 FROM workbench_note_origins WHERE request_id=?', (request_id,)).fetchone():
                    raise
        origin = dict(self.db.execute('SELECT * FROM workbench_note_origins WHERE request_id=?', (request_id,)).fetchone())
        note = self.db.execute('SELECT revision,deleted_at,content_hash FROM notes WHERE id=? AND student_id=?', (origin['note_id'], student)).fetchone()
        return {'note_id': origin['note_id'], 'revision': note['revision'], 'deleted': bool(note['deleted_at']),
                'edited': note['revision'] != 1 or note['content_hash'] != origin['original_hash'],
                'request_id': request_id, 'generated_at': origin['generated_at']}
