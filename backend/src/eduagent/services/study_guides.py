"""Rule-owned guide generation with optional bounded evidence explanation."""

from dataclasses import dataclass, asdict
from hashlib import sha256
import json

from eduagent.domain.guidance import render_rules
from eduagent.domain.notes import COURSE_ID, NoteConflict, NoteNotFound
from eduagent.domain.self_assessment import request_uuid
from eduagent.services.guidance import GuidanceService, LearningContextChanged
from eduagent.services.knowledge import SourceChanged, IndexUnavailable
from eduagent.services.learning import now
from eduagent.services.workbench import WorkbenchService, RequestContext
from eduagent.storage.study_guides import StudyGuideRepository
from eduagent.storage.sqlite import encode


@dataclass(frozen=True)
class GuideRequestContext(RequestContext):
    assessment_revision: int
    snapshot_hash: str
    guide_rule_version: str


class StudyGuideService:
    def __init__(self, learning, courses=None, enabled=True, settings=None, client_factory=None):
        self.learning, self.repository = learning, learning.repository
        self.guidance = GuidanceService(learning)
        self.receipts = StudyGuideRepository(self.repository)
        self.workbench = WorkbenchService(learning, courses, enabled)
        self.knowledge = self.workbench.knowledge
        self.settings, self.client_factory = settings, client_factory

    def _owned(self, student, request_id):
        self.learning._student(student)
        row = self.receipts.find(request_id)
        if row is None or row['student_id'] != student:
            raise NoteNotFound('当前学习标识下没有该学习指南')
        return row

    def _view(self, row, current=None):
        snapshot = json.loads(row['snapshot_json'])
        current = current or self.guidance._snapshot(row['student_id'], row['course_id'])
        sources = json.loads(row['context_json'])['sources']
        statuses = self.workbench._source_status(row['student_id'], sources)
        stale = []
        if current['learning_revision'] != row['learning_revision']: stale.append('learning_state_changed')
        if current['assessment_revision'] != row['assessment_revision']: stale.append('self_assessment_changed')
        if current['versions'] != snapshot['versions'] or current['rule_version'] != snapshot['rule_version']:
            stale.append('configuration_changed')
        if any(s['current_status'] != 'current' for s in statuses): stale.append('sources_changed')
        status, output = row['status'], json.loads(row['result_json'])
        if status == 'running':
            status, output = 'uncertain', {**output, 'reason': 'execution_unconfirmed'}
        elif stale and status in ('complete', 'local'):
            status = 'stale'
        return dict(request_id=row['request_id'], course_id=row['course_id'], status=status,
            snapshot=snapshot, sources=sources, source_statuses=statuses, stale_reasons=stale,
            model_calls=row['model_calls'], created_at=row['created_at'], updated_at=row['updated_at'], **output)

    def get(self, student, request_id):
        with self.repository.transaction():
            return self._view(self._owned(student, request_id))

    def history(self, student, limit=20):
        if type(limit) is not int or not 1 <= limit <= 50:
            raise ValueError('指南数量必须为1～50')
        with self.repository.transaction():
            snapshot = self.guidance._snapshot(student)
            return [self._view(row, snapshot) for row in self.receipts.recent(student, COURSE_ID, limit)]

    def _validate_locked(self, context):
        current = self.guidance._snapshot(context.student_id, context.course_id)
        if current['snapshot_hash'] != context.snapshot_hash:
            raise LearningContextChanged('答题、自评或规则版本已变化，请刷新学情后发起新请求')
        if context.sources:
            _, courses = self.knowledge._validate(context.student_id, context.refs(), context.course_id)
            if not self.knowledge.enabled:
                raise IndexUnavailable('本地检索已关闭')
            if courses: self.knowledge.courses.verify()

    def validate_context(self, context):
        with self.repository.transaction():
            self._validate_locked(context)

    def before_model(self, context):
        with self.repository.transaction():
            self._validate_locked(context)
            if not self.receipts.attempted(context.student_id, context.request_id, now()):
                raise LearningContextChanged('原指南请求已经结束，不能重新调用模型')

    def _replay(self, row, student, digest):
        if row['student_id'] != student:
            raise NoteNotFound('当前学习标识下没有该学习指南')
        if row['request_hash'] != digest:
            raise NoteConflict('指南请求编号已用于不同内容，不能重复生成或复用授权')
        return self._view(row)

    def generate(self, student, body):
        request_id = request_uuid(body['request_id'])
        if body['mode'] not in ('rules', 'model') or type(body['allow_personal_external']) is not bool:
            raise ValueError('指南模式或授权无效')
        if any(type(body[key]) is not int or body[key] < 0 for key in ('expected_learning_revision', 'expected_assessment_revision')):
            raise ValueError('学情版本必须为非负整数')
        if not isinstance(body['sources'], list) or len(body['sources']) > 55 or body['mode'] == 'model' and not body['sources']:
            raise ValueError('模型模式必须明确选择1～55个来源')
        digest = sha256(encode(body).encode()).hexdigest()
        with self.repository.transaction():
            self.learning._student(student)
            existing = self.receipts.find(request_id)
            if existing: return self._replay(existing, student, digest)
            snapshot = self.guidance._snapshot(student, body['course_id'])
            if snapshot['learning_revision'] != body['expected_learning_revision'] or snapshot['assessment_revision'] != body['expected_assessment_revision']:
                raise LearningContextChanged('保存的学情已变化，请先刷新；自评草稿不参与生成')
        context = GuideRequestContext(student, body['course_id'], request_id,
            tuple((s['source_type'], s['source_id'], s['source_version']) for s in body['sources']), body['allow_personal_external'],
            snapshot['learning_revision'], snapshot['assessment_revision'], snapshot['snapshot_hash'], snapshot['rule_version'])
        # Empty rules scope never calls retrieval, not even with a default query.
        branches = []
        if context.sources:
            self.validate_context(context)
            for point in snapshot['recommendations']:
                self.validate_context(context)
                branches.append(self.knowledge.search(student, point['name'], context.refs(), context.course_id, top_k=3)['items'])
        evidence, seen = [], set()
        for rank in range(3):
            for branch in branches:
                if rank < len(branch) and branch[rank]['citation_id'] not in seen:
                    evidence.append(branch[rank]); seen.add(branch[rank]['citation_id'])
        evidence = evidence[:5]
        result = dict(rules_md=render_rules(snapshot), explanation_md='', citations=evidence, reason=None, model=None,
                      tools_used=[], usage=dict(prompt_tokens=0, completion_tokens=0))
        with self.repository.transaction():
            existing = self.receipts.find(request_id)
            if existing: return self._replay(existing, student, digest)
            self._validate_locked(context)
            context_json = {**asdict(context), 'sources': context.refs()}
            self.receipts.claim(student, request_id, digest, body, context_json, snapshot, result, now())
        reason = ('rules_requested' if body['mode'] == 'rules' else
                  'teacher_consent_required' if any(ref[0]=='teaching_material' for ref in context.sources) else
                  'personal_consent_required' if any(ref[0] == 'personal_note' for ref in context.sources) and not context.allow_personal_external else
                  'model_disabled' if not self.settings or not self.settings.enabled else
                  'insufficient_evidence' if not evidence else None)
        status = 'local'
        if reason is None:
            try:
                from eduagent.agent.workbench import WorkbenchAgent
                summary = self.guidance.external_summary(snapshot)
                output = WorkbenchAgent(self, context, self.client_factory(), self.settings, summary).run(
                    '请仅辅助解释本轮程序已确定的学习重点，不能修改重点、排序、事实、评分或先修。', evidence, guide_context=summary)
                reason = output.get('reason')
                status = 'complete' if not reason else ('uncertain' if reason in (
                    'model_timeout', 'network_error', 'upstream_error', 'invalid_model_response') else 'local')
                result.update(model=output.get('model'), usage=output['usage'], tools_used=output['tools_used'])
                if not reason:
                    result.update(explanation_md=output['answer'], citations=output['citations'])
            except (SourceChanged, NoteNotFound, IndexUnavailable, LearningContextChanged):
                status, reason = 'stale', 'context_changed'
            except Exception:
                status, reason = 'uncertain', 'execution_unconfirmed'
        with self.repository.transaction():
            try:
                self._validate_locked(context)
            except (SourceChanged, NoteNotFound, IndexUnavailable, LearningContextChanged):
                # Expired evidence and unknown upstream execution are separate
                # facts. Preserve the no-retry state if both happen together.
                if status != 'uncertain':
                    status, reason = 'stale', 'context_changed'
            self.receipts.finish(request_id, status, {**result, 'reason': reason}, now())
        return self.get(student, request_id)
