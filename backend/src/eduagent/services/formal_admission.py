"""Explicit, additive assessment admission. No model calls or automatic writes.

The immutable admission lives in local SQLite metadata, not in a public file.
It binds the old configuration and frozen question versions. Old executables
reject the new configuration instead of silently scoring an incompatible bank.
"""
from copy import copy
from dataclasses import asdict, replace
from hashlib import sha256
import json

from eduagent.domain.catalog import Catalog, Question
from eduagent.storage.sqlite import encode

KEY = 'formal_assessment_admission_v1'
VERSION = 'ai-admission-v1'


def checksum(value):
    return sha256(encode(value).encode()).hexdigest()


class FormalAdmission:
    def __init__(self, base, repository, configuration):
        self.base, self.repo = base, repository
        row = repository.connection.execute('SELECT value FROM metadata WHERE key=?', (KEY,)).fetchone()
        self.record = json.loads(row[0]) if row else None
        self.catalog = base
        self.configuration = configuration
        if not self.record:
            return
        record = self.record
        if record['version'] != VERSION or record['previous_configuration'] != configuration:
            raise ValueError('正式题准入记录与原知识点、评分或BKT配置不一致')
        knowledge = dict(version=base.knowledge_version,
                         knowledge_points=[dict(asdict(p), prerequisites=list(p.prerequisites)) for p in base.knowledge.values()])
        shared = Catalog(knowledge, dict(version=record['bank_version'], questions=record['shared_questions']))
        for key, old in base.questions.items():
            if key not in shared.questions or asdict(old) != asdict(shared.questions[key]):
                raise ValueError('正式扩题只能追加，不能改写原题或历史评分依据')
        self.catalog = copy(shared)
        self.catalog.questions = {key: replace(q, review_status='ai_checked') for key, q in shared.questions.items()}
        self.configuration = dict(configuration, formal_admission=dict(version=VERSION, digest=checksum(record)))
        seen = set(shared.questions)
        for entry in record['personal_questions']:
            q = entry['question']
            if q['id'] in seen or q['knowledge_id'] not in base.knowledge:
                raise ValueError('个人正式题ID重复或超出原知识点范围')
            seen.add(q['id'])
            if not entry['student_id'] or q['review_status'] != 'ai_checked':
                raise ValueError('个人正式题缺少作用域或AI检查记录')
            if set(q['options']) != {'A', 'B'} or q['answer'] not in q['options'] or not q['stem'].strip() or not q['explanation'].strip():
                raise ValueError('个人正式判断题缺少完整评分依据')
            if entry.get('answer_origin') != 'source_extracted_by_ai':
                raise ValueError('本次个人题准入仅接受原文已有答案')
            Question(**q)

    def source_current(self, student, entry):
        """Check the owner, exact revision, original version, deletion and readiness."""
        db = self.repo.connection
        row = db.execute('SELECT * FROM personal_questions WHERE id=? AND student_id=? AND course_id=?',
                         (entry['personal_id'], student, 'machine_learning')).fetchone()
        if not row or row['status'] == 'archived' or row['revision'] != entry['revision']:
            return False
        if checksum(json.loads(row['payload_json'])) != entry['payload_hash'] or checksum(json.loads(row['source_json'])) != entry['source_hash']:
            return False
        source = entry['source']
        if source.get('original_source_type') != 'document':
            return False
        document = db.execute('SELECT * FROM course_documents WHERE id=? AND student_id=? AND course_id=?',
                              (source['original_source_id'], student, 'machine_learning')).fetchone()
        if not document or document['deleted_at'] or document['current_version_id'] != source['source_version']:
            return False
        run = db.execute('SELECT * FROM document_parse_runs WHERE id=? AND document_id=? AND student_id=? AND version_id=?',
                         (source.get('run_id'), document['id'], student, source['source_version'])).fetchone()
        return bool(run and run['status'] in ('ready', 'partial', 'empty') and
                    (source.get('origin_mode') != 'local' or document['current_parse_id'] == run['id']))

    def for_student(self, student):
        if not self.record:
            return self.base
        result = copy(self.catalog)
        result.questions = dict(self.catalog.questions)
        for entry in self.record['personal_questions']:
            if entry['student_id'] == student and self.source_current(student, entry):
                q = Question(**entry['question'])
                result.questions[q.id] = q
        result.fingerprint = checksum([self.catalog.fingerprint, [asdict(q) for q in result.questions.values()]])
        return result

    def compatible_release(self, value, current):
        if value == current:
            return True
        if not self.record:
            return False
        previous = self.record['previous_configuration']
        return value == dict(previous, scoring='exact-option-key-v1')

    def question(self, student, key):
        return self.for_student(student).questions.get(key)

    def assessment_info(self, student):
        catalog = self.for_student(student)
        return dict(question_count=len(catalog.questions), shared_count=len(self.catalog.questions),
                    personal_count=len(catalog.questions)-len(self.catalog.questions),
                    ai_checked_count=sum(q.review_status == 'ai_checked' for q in catalog.questions.values()),
                    bank_version=catalog.bank_version, bkt_calibrated=False)
