"""Four-parameter Bayesian Knowledge Tracing, without forgetting.

Observe an answer to compute q = P(learned | observation), then apply the
learning transition: p_next = q + (1-q) * learn. Browsing a lesson alone does
not invoke this function. Defaults are demonstration assumptions, not fitted
student parameters. See docs/PROJECT_CONTEXT.md for the formulas/reference.
"""

from dataclasses import dataclass
from math import isfinite


def probability(value: float, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} 必须是数值概率")
    if not isfinite(value) or not 0 <= value <= 1:
        raise ValueError(f"{name} 必须在 [0, 1] 内且有限")


@dataclass(frozen=True)
class BKTParameters:
    initial: float = 0.20
    learn: float = 0.10
    slip: float = 0.10
    guess: float = 0.25
    version: str = "bkt-demo-v1"

    def __post_init__(self) -> None:
        for name in ("initial", "learn", "slip", "guess"):
            probability(getattr(self, name), name)
        if not isinstance(self.version, str) or not self.version.strip():
            raise ValueError("BKT 参数版本不能为空")


@dataclass(frozen=True)
class BKTUpdate:
    prior: float
    posterior: float
    next_mastery: float


def update_bkt(prior: float, correct: bool, params: BKTParameters) -> BKTUpdate:
    probability(prior, "prior")
    if not isinstance(correct, bool):
        raise ValueError("correct 必须是布尔值")
    learned_likelihood = 1 - params.slip if correct else params.slip
    unlearned_likelihood = params.guess if correct else 1 - params.guess
    numerator = prior * learned_likelihood
    evidence = numerator + (1 - prior) * unlearned_likelihood
    if evidence == 0:
        raise ValueError("该参数下观测概率为零，无法执行贝叶斯更新")
    posterior = numerator / evidence
    next_mastery = posterior + (1 - posterior) * params.learn
    return BKTUpdate(prior, posterior, next_mastery)
