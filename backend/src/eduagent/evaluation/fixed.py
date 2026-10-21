"""A fixed exercise quota baseline used only by the offline comparison.

Both policies follow the same prerequisite order and avoid repeated questions.
This baseline advances after a fixed number of exercises, regardless of scores.
Quota completion does not assert mastery or a learning effect.
"""

from dataclasses import dataclass

from eduagent.domain.catalog import Catalog
from eduagent.domain.models import Mastery, Recommendation


@dataclass(frozen=True)
class FixedSequencePolicy:
    questions_per_skill: int = 2
    max_rounds: int = 20
    version: str = "fixed-quota-v1"

    def __post_init__(self) -> None:
        for value in (self.questions_per_skill, self.max_rounds):
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError("固定题额与答题上限必须是正整数")

    def decide(self, *, decision_id: str, student_id: str, revision: int,
               goals: tuple[str, ...], states: dict[str, Mastery], answered: set[str],
               catalog: Catalog) -> Recommendation:
        ordered = catalog.expand_goals(goals)
        counts = {key: sum(q.id in answered for q in catalog.questions.values()
                           if q.knowledge_id == key) for key in ordered}
        evidence = {
            "mode": "offline_fixed_baseline", "policy_version": self.version,
            "goals": list(goals), "required_knowledge": list(ordered),
            "questions_per_skill": self.questions_per_skill, "completed_counts": counts,
            "max_rounds": self.max_rounds, "state_revision": revision,
            "completion_basis": "exercise_quota_only",
        }
        base = dict(decision_id=decision_id, student_id=student_id, revision=revision)
        remaining = [key for key in ordered if counts[key] < self.questions_per_skill]
        if not remaining:
            return Recommendation(**base, action="finish", knowledge_id=None,
                                  reason="固定练习额度已完成；不判定知识掌握或真实能力。", evidence=evidence)
        if revision >= self.max_rounds:
            return Recommendation(**base, action="stopped", knowledge_id=None,
                                  reason="已达到累计答题上限。", evidence=evidence, stop_reason="round_limit")
        target = remaining[0]
        questions = catalog.select(target, exclude=answered)
        if not questions:
            return Recommendation(**base, action="stopped", knowledge_id=target,
                                  reason="固定题额尚未完成，但可用新题已耗尽。", evidence=evidence,
                                  stop_reason="insufficient_questions")
        # Deliberately reads exercise counts, not BKT probability or correctness.
        action = "practice" if counts[target] else (
            "advance" if catalog.knowledge[target].prerequisites else "diagnose")
        return Recommendation(**base, action=action, knowledge_id=target,
                              reason="按先修顺序完成固定题额，不依据答题正误调整安排。",
                              evidence=evidence, question=questions[0].public_view())
