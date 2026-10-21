"""A deterministic policy that will share a contract with the future Agent."""

from dataclasses import dataclass

from eduagent.domain.bkt import probability
from eduagent.domain.catalog import Catalog
from eduagent.domain.models import Mastery, Recommendation


@dataclass(frozen=True)
class RulePolicy:
    threshold: float = 0.80
    max_rounds: int = 20
    version: str = "rules-v1"

    def __post_init__(self) -> None:
        probability(self.threshold, "threshold")
        if self.threshold == 0:
            raise ValueError("掌握阈值必须大于 0")
        if isinstance(self.max_rounds, bool) or not isinstance(self.max_rounds, int) or self.max_rounds < 1:
            raise ValueError("最大答题轮数必须是正整数")

    def decide(self, *, decision_id: str, student_id: str, revision: int,
               goals: tuple[str, ...], states: dict[str, Mastery], answered: set[str],
               catalog: Catalog) -> Recommendation:
        ordered = catalog.expand_goals(goals)
        evidence = {
            "mode": "offline_rules", "policy_version": self.version,
            "goals": list(goals), "required_knowledge": list(ordered),
            "threshold": self.threshold, "max_rounds": self.max_rounds,
            "state_revision": revision,
        }
        base = dict(decision_id=decision_id, student_id=student_id, revision=revision)

        def mastered(identifier: str) -> bool:
            state = states[identifier]
            return state.attempts > 0 and state.probability >= self.threshold and state.last_correct is True

        remaining = [identifier for identifier in ordered if not mastered(identifier)]
        if not remaining:
            return Recommendation(**base, action="finish", knowledge_id=None,
                                  reason="目标及先修知识点均满足演示掌握阈值；不代表真实能力已被验证。",
                                  evidence=evidence)
        if revision >= self.max_rounds:
            return Recommendation(**base, action="stopped", knowledge_id=None,
                                  reason="已达到该演示学生的累计答题上限。", evidence=evidence,
                                  stop_reason="round_limit")
        # Topological order guarantees that a weak prerequisite comes first.
        target = remaining[0]
        point = catalog.knowledge[target]
        state = states[target]
        evidence.update({
            "mastery": state.probability, "attempts": state.attempts,
            "last_correct": state.last_correct,
            "prerequisites": {p: states[p].probability for p in point.prerequisites},
            "supports_goals": [goal for goal in goals if target in catalog.expand_goals((goal,))],
        })
        questions = catalog.select(target, exclude=answered)
        if not questions:
            return Recommendation(**base, action="stopped", knowledge_id=target,
                                  reason=f"{point.name}尚未满足条件，但可用新题已耗尽；需要补充题库。",
                                  evidence=evidence, stop_reason="insufficient_questions")
        if state.attempts == 0:
            action = "advance" if point.prerequisites else "diagnose"
            reason = f"{point.name}尚无答题证据，先用一道题诊断。"
            if point.prerequisites:
                reason = "先修知识点已满足演示阈值。" + reason
        elif state.last_correct is False:
            action = "review"
            reason = f"{point.name}最近一次答错，先复习再完成下一道练习。{point.review_tip}"
        else:
            action = "practice"
            reason = f"{point.name}当前掌握度 {state.probability:.1%} 低于阈值，继续练习。"
        return Recommendation(**base, action=action, knowledge_id=target, reason=reason,
                              evidence=evidence, question=questions[0].public_view())
