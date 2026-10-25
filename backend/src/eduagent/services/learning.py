"""The application controls grading, BKT and one atomic state transition.

Future API/Agent adapters should call this service rather than write mastery
or scores themselves. Planning reads persisted state; it cannot invent it.
"""

from dataclasses import asdict, replace
from datetime import datetime, timezone
import json
from uuid import uuid4

from eduagent.agent.policy import RulePolicy
from eduagent.domain.bkt import BKTParameters, update_bkt
from eduagent.domain.catalog import Catalog, normalize_answer, required_text
from eduagent.domain.models import LearningSnapshot, Mastery, Recommendation, SubmissionResult
from eduagent.storage.sqlite import SQLiteRepository


class SubmissionConflict(ValueError):
    """An event ID conflicts, or an assigned question is already consumed."""


class StudentNotFound(ValueError):
    """The requested learner does not exist."""


class GoalConflict(ValueError):
    """An existing learner has a different persisted goal."""


def identifier(value: str, name: str) -> str:
    required_text(value, name)
    if value != value.strip() or len(value) > 128:
        raise ValueError(f"{name} 不能带首尾空格，且不得超过 128 字符")
    return value


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class LearningService:
    def __init__(self, catalog: Catalog, repository: SQLiteRepository,
                 parameters: BKTParameters | None = None, policy: RulePolicy | None = None):
        self.catalog = catalog
        self.repository = repository
        self.parameters = parameters or BKTParameters()
        self.policy = policy or RulePolicy()
        configuration = {
            "catalog_fingerprint": catalog.fingerprint,
            "knowledge_version": catalog.knowledge_version, "bank_version": catalog.bank_version,
            "parameters": asdict(self.parameters), "policy": asdict(self.policy),
        }
        from eduagent.services.formal_admission import FormalAdmission
        self.formal_admission = FormalAdmission(catalog, repository, configuration)
        self.catalog = self.formal_admission.catalog
        repository.bind_configuration(self.formal_admission.configuration)

    def catalog_for(self, student_id):
        return self.formal_admission.for_student(student_id)

    def register(self, student_id: str, goals: tuple[str, ...] | None = None) -> None:
        identifier(student_id, "学生标识")
        if goals is not None:
            if isinstance(goals, str):
                raise ValueError("目标必须是知识点 ID 序列")
            goals = tuple(dict.fromkeys(goals))
            self.catalog.expand_goals(goals)
        with self.repository.transaction():
            existing = self.repository.student(student_id)
            if existing:
                if goals is not None and tuple(json.loads(existing["goals_json"])) != goals:
                    raise GoalConflict("该演示学生已有不同学习目标，请使用新的学生标识")
            else:
                resolved = goals if goals is not None else tuple(self.catalog.knowledge)
                self.repository.add_student(student_id, resolved, now())

    def _student(self, student_id: str):
        identifier(student_id, "学生标识")
        student = self.repository.student(student_id)
        if student is None:
            raise StudentNotFound("学生标识不存在，请先创建学习记录")
        return student

    def status(self, student_id: str) -> dict[str, Mastery]:
        self._student(student_id)
        persisted = self.repository.states(student_id)
        return {key: persisted.get(key, Mastery(key, self.parameters.initial))
                for key in self.catalog.knowledge}

    def next_action(self, student_id: str) -> Recommendation:
        with self.repository.transaction():
            student = self._student(student_id)
            existing = self.repository.decision_at(student_id, student["revision"])
            if existing and not (existing.stop_reason == 'insufficient_questions' and self.formal_admission.record
                                 and self.catalog_for(student_id).select(existing.knowledge_id, exclude=self.repository.answered_questions(student_id))):
                return existing
            decision = self.policy.decide(
                decision_id=str(uuid4()), student_id=student_id, revision=student["revision"],
                goals=tuple(json.loads(student["goals_json"])), states=self.status(student_id),
                answered=self.repository.answered_questions(student_id), catalog=self.catalog_for(student_id),
            )
            if self.formal_admission.record:
                decision = replace(decision, evidence=dict(decision.evidence, bank_version=self.catalog.bank_version,
                    admission_version='ai-admission-v1'))
            if existing:
                # Only an explicit next command resumes a previously exhausted
                # bank. Preserve the old terminal snapshot before replacing the
                # ungraded decision at this revision. Reads never do this.
                self.repository.connection.execute('INSERT INTO metadata VALUES (?,?)',
                    ('formal-resumed:'+existing.decision_id, json.dumps(asdict(existing), ensure_ascii=False)))
                # Keep any teaching-session link to the original terminal ID.
                decision = replace(decision, decision_id=existing.decision_id)
                self.repository.connection.execute('UPDATE decisions SET payload_json=? WHERE id=?',
                    (json.dumps(asdict(decision), ensure_ascii=False), existing.decision_id))
                self.repository.connection.execute('UPDATE teaching_decisions SET question_json=? WHERE decision_id=?',
                    (json.dumps(decision.question, ensure_ascii=False), existing.decision_id))
                return decision
            self.repository.save_decision(decision, now())
            return decision

    def snapshot(self, student_id: str) -> LearningSnapshot:
        """Read revision, goals and mastery from one consistent DB transaction."""
        with self.repository.transaction():
            student = self._student(student_id)
            return LearningSnapshot(
                student_id=student_id, goals=tuple(json.loads(student["goals_json"])),
                revision=student["revision"], mastery=tuple(self.status(student_id).values()),
            )

    def submit(self, student_id: str, decision_id: str, answer: str, event_id: str) -> SubmissionResult:
        identifier(student_id, "学生标识")
        identifier(decision_id, "决策标识")
        identifier(event_id, "事件标识")
        selected = normalize_answer(answer)
        with self.repository.transaction():
            previous = self.repository.attempt(event_id)
            if previous:
                if (previous.student_id, previous.decision_id, previous.selected_answer) != (
                    student_id, decision_id, selected
                ):
                    raise SubmissionConflict("事件 ID 已存在且提交内容冲突")
                return replace(previous, replayed=True)
            student = self._student(student_id)
            decision = self.repository.decision(decision_id)
            if decision is None or decision.student_id != student_id:
                raise SubmissionConflict("题目分配不存在或不属于当前学生")
            if decision.revision != student["revision"]:
                raise SubmissionConflict("题目分配已过期或已经提交，不能再次更新")
            if decision.question is None:
                raise SubmissionConflict("该决策没有可提交的题目")
            question = self.catalog_for(student_id).questions.get(decision.question["id"])
            if question is None:
                raise SubmissionConflict('题目来源或版本已变化，不能按当前题库评分')
            if any(decision.question.get(k) != question.public_view().get(k) for k in ('id','version','knowledge_id','stem','options')):
                raise SubmissionConflict('题目版本与原分配不一致')
            correct = question.grade(selected)
            state = self.status(student_id)[question.knowledge_id]
            update = update_bkt(state.probability, correct, self.parameters)
            result = SubmissionResult(
                event_id=event_id, student_id=student_id, decision_id=decision_id,
                question_id=question.id, question_version=question.version,
                knowledge_id=question.knowledge_id, selected_answer=selected,
                correct_answer=question.answer, correct=correct, explanation=question.explanation,
                prior=update.prior, posterior=update.posterior, next_mastery=update.next_mastery,
                bank_version=decision.evidence.get('bank_version', self.formal_admission.base.bank_version), parameter_version=self.parameters.version,
                parameters=asdict(self.parameters), created_at=now(),
            )
            self.repository.record_attempt(result, state.attempts)
            return result

    def history(self, student_id: str, limit: int = 50) -> dict:
        """Return this learner's graded receipts, without allocating a new task."""
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 50:
            raise ValueError("历史查询数量必须为 1～50")
        with self.repository.transaction():
            student = self._student(student_id)
            return {"student_id": student_id, "revision": student["revision"],
                    "items": self.repository.recent_attempts(student_id, limit)}
