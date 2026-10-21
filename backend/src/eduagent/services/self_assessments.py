"""Idempotent append/CAS reports, independent of the learning revision."""

from hashlib import sha256
from uuid import uuid4

from eduagent.domain.notes import COURSE_ID, NoteConflict, NoteNotFound, course
from eduagent.domain.self_assessment import request_uuid, assessment_items
from eduagent.services.learning import now
from eduagent.storage.self_assessments import SelfAssessmentRepository
from eduagent.storage.sqlite import encode


class SelfAssessmentService:
    def __init__(self, learning):
        self.learning, self.repository = learning, learning.repository
        self.reports = SelfAssessmentRepository(self.repository)

    def _student(self, student, course_id):
        course(course_id)
        return self.learning._student(student)

    def _receipt(self, batch, replayed):
        return dict(request_id=batch['request_id'], committed_revision=batch['assessment_revision'],
            current_revision=self.reports.revision(batch['student_id'], batch['course_id']), course_id=batch['course_id'],
            learning_revision_at_save=batch['learning_revision_at_save'], created_at=batch['created_at'], replayed=replayed,
            items=self.reports.entries(batch['student_id'], batch['course_id'], batch=batch['request_id']))

    def save(self, student, *, request_id, expected_revision, items, course_id=COURSE_ID):
        request_uuid(request_id)
        if type(expected_revision) is not int or expected_revision < 0:
            raise ValueError('expected_revision必须为非负整数')
        values = assessment_items(items, self.learning.catalog)
        payload = encode(dict(request_id=request_id, course_id=course_id, expected_revision=expected_revision, items=values))
        digest = sha256(payload.encode()).hexdigest()
        with self.repository.transaction():
            learner = self._student(student, course_id)
            previous = self.reports.batch(request_id)
            if previous:
                if previous['student_id'] != student or previous['course_id'] != course_id:
                    raise NoteNotFound('当前学习标识下没有该自评回执')
                if previous['request_hash'] != digest:
                    raise NoteConflict('自评请求编号已用于不同内容，不能覆盖或重复使用')
                return self._receipt(previous, True)
            revision = self.reports.revision(student, course_id)
            if revision != expected_revision:
                raise NoteConflict('自评版本已变化，本机草稿应保留；请读取最新版本后确认')
            timestamp = now()
            self.reports.insert((request_id, student, course_id, revision + 1, expected_revision, digest, payload, learner['revision'], timestamp),
                [(str(uuid4()), request_id, student, course_id, item['knowledge_id'], item['level'], item['confidence']) for item in values])
            return self._receipt(self.reports.batch(request_id), False)

    def receipt(self, student, request_id, course_id=COURSE_ID):
        with self.repository.transaction():
            self._student(student, course_id)
            row = self.reports.batch(request_id)
            if row is None or row['student_id'] != student or row['course_id'] != course_id:
                raise NoteNotFound('当前学习标识下没有该自评回执')
            return self._receipt(row, True)

    def latest(self, student, course_id=COURSE_ID):
        with self.repository.transaction():
            self._student(student, course_id)
            latest = self.reports.latest(student, course_id)
            return dict(course_id=course_id, assessment_revision=self.reports.revision(student, course_id),
                items=[dict(knowledge_id=key, assessment=latest.get(key)) for key in self.learning.catalog.knowledge])

    def history(self, student, course_id=COURSE_ID, knowledge_id=None, limit=20, offset=0):
        if knowledge_id is not None and knowledge_id not in self.learning.catalog.knowledge:
            raise ValueError('知识点不存在')
        if type(limit) is not int or not 1 <= limit <= 50 or type(offset) is not int or offset < 0:
            raise ValueError('自评分页参数无效')
        with self.repository.transaction():
            self._student(student, course_id)
            return dict(course_id=course_id, assessment_revision=self.reports.revision(student, course_id),
                items=self.reports.entries(student, course_id, knowledge=knowledge_id, limit=limit, offset=offset), limit=limit, offset=offset)
