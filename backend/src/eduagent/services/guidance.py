"""One transactional view of objective facts, reports and read-only advice."""

from hashlib import sha256

from eduagent.domain.guidance import RULE_VERSION, analyze
from eduagent.domain.notes import COURSE_ID, NoteConflict, course
from eduagent.storage.self_assessments import SelfAssessmentRepository
from eduagent.storage.sqlite import encode


class LearningContextChanged(NoteConflict):
    pass


class GuidanceService:
    def __init__(self, learning):
        self.learning, self.repository = learning, learning.repository
        self.reports = SelfAssessmentRepository(self.repository)

    def _snapshot(self, student, course_id=COURSE_ID):
        """Caller owns transaction; no next_action, nested snapshot or writes."""
        course(course_id)
        learner = self.learning._student(student)
        import json
        goals = json.loads(learner['goals_json'])
        catalog = self.learning.catalog
        ordered = list(catalog.expand_goals(goals))
        states = self.learning.status(student)
        latest = self.reports.latest(student, course_id)
        answered = self.repository.answered_questions(student)
        items = []
        for key, point in catalog.knowledge.items():
            state = states[key]
            recent = [dict(row, correct=bool(row['correct'])) for row in self.repository.connection.execute(
                '''SELECT a.event_id,a.question_id,a.correct,a.created_at,d.revision+1 AS learning_revision
                   FROM attempts a JOIN decisions d ON d.id=a.decision_id AND d.student_id=a.student_id
                   WHERE a.student_id=? AND a.knowledge_id=? ORDER BY d.revision DESC LIMIT 3''', (student, key))]
            items.append(dict(knowledge_id=key, name=point.name, prerequisites=list(point.prerequisites),
                in_goal_path=key in ordered, self_report=latest.get(key), recent_attempts=recent,
                objective=dict(has_evidence=state.attempts > 0, probability=state.probability if state.attempts else None,
                    prior_probability=self.learning.parameters.initial, attempts=state.attempts, last_correct=state.last_correct,
                    meets_progress_condition=state.attempts > 0 and state.probability >= self.learning.policy.threshold and state.last_correct is True),
                available_questions=len(catalog.select(key, exclude=answered)),
                round_limit_reached=learner['revision'] >= self.learning.policy.max_rounds))
        recommendations = analyze(items, ordered, goals)
        result = dict(course_id=course_id, learning_revision=learner['revision'], assessment_revision=self.reports.revision(student, course_id),
            rule_version=RULE_VERSION, threshold=self.learning.policy.threshold, goals=goals,
            goal_names=[catalog.knowledge[key].name for key in goals], items=items, recommendations=recommendations,
            versions=dict(bkt=self.learning.parameters.version, policy=self.learning.policy.version,
                knowledge=catalog.knowledge_version, catalog=catalog.fingerprint, bank=catalog.bank_version))
        result['snapshot_hash'] = sha256(encode(result).encode()).hexdigest()
        return result

    def snapshot(self, student, course_id=COURSE_ID):
        with self.repository.transaction():
            return self._snapshot(student, course_id)

    @staticmethod
    def external_summary(snapshot):
        # Explicit allowlist: no learner IDs, report IDs, event IDs, full quiz
        # history, answer keys, or unselected note contents reach the provider.
        return dict(goals=snapshot['goal_names'], rule_version=snapshot['rule_version'],
            recommendations=[dict(knowledge_id=p['knowledge_id'], name=p['name'], priority=p['priority'],
                objective=p['objective'], self_report=({k: p['self_report'][k] for k in ('level', 'confidence')} if p['self_report'] else None),
                reasons=p['reasons']) for p in snapshot['recommendations']])
