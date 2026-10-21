"""Typed state shared between the planner, flow service and storage."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Mastery:
    knowledge_id: str
    probability: float
    attempts: int = 0
    last_correct: bool | None = None


@dataclass(frozen=True)
class LearningSnapshot:
    student_id: str
    goals: tuple[str, ...]
    revision: int
    mastery: tuple[Mastery, ...]


@dataclass(frozen=True)
class Recommendation:
    decision_id: str
    student_id: str
    revision: int
    action: str
    knowledge_id: str | None
    reason: str
    evidence: dict[str, Any]
    question: dict[str, Any] | None = None
    stop_reason: str | None = None


@dataclass(frozen=True)
class SubmissionResult:
    event_id: str
    student_id: str
    decision_id: str
    question_id: str
    question_version: str
    knowledge_id: str
    selected_answer: str
    correct_answer: str
    correct: bool
    explanation: str
    prior: float
    posterior: float
    next_mastery: float
    bank_version: str
    parameter_version: str
    parameters: dict[str, Any]
    created_at: str
    replayed: bool = False
