from dataclasses import asdict
import sqlite3

import pytest

from eduagent.agent.policy import RulePolicy
from eduagent.domain.bkt import BKTParameters
from eduagent.domain.catalog import Catalog
from eduagent.services.learning import LearningService, SubmissionConflict
from eduagent.storage.sqlite import SQLiteRepository


def answer_next(service, student="student-a", correct=True, event_id=None):
    decision = service.next_action(student)
    question = service.catalog.questions[decision.question["id"]]
    answer = question.answer if correct else next(a for a in question.options if a != question.answer)
    event_id = event_id or f"{student}-{decision.revision}"
    return service.submit(student, decision.decision_id, answer, event_id)


def test_prior_is_not_diagnosis_and_reads_do_not_update(service):
    states = service.status("student-a")
    assert all(s.attempts == 0 and s.probability == 0.2 for s in states.values())
    first = service.next_action("student-a")
    assert first.action == "diagnose"
    assert first.knowledge_id == "linear_regression_loss"
    assert service.next_action("student-a") == first
    assert service.status("student-a") == states


def test_wrong_answer_reviews_weak_prerequisite(service):
    feedback = answer_next(service, correct=False)
    assert feedback.next_mastery == pytest.approx(4 / 31)
    next_action = service.next_action("student-a")
    assert next_action.action == "review"
    assert next_action.knowledge_id == "linear_regression_loss"
    assert next_action.question["id"] == "lr_02"
    assert next_action.evidence["supports_goals"] == ["logistic_regression"]
    assert "复习" in next_action.reason


def test_success_advances_only_after_mastering_prerequisite(service):
    first = answer_next(service)
    assert first.next_mastery == pytest.approx(10 / 19)
    assert service.next_action("student-a").action == "practice"
    answer_next(service)
    decision = service.next_action("student-a")
    assert decision.action == "advance"
    assert decision.knowledge_id == "gradient_descent"
    assert decision.evidence["prerequisites"]["linear_regression_loss"] == pytest.approx(0.82)


def test_invalid_answer_writes_nothing_and_can_retry(service):
    decision = service.next_action("student-a")
    for answer in ("E", "AB", ""):
        with pytest.raises(ValueError):
            service.submit("student-a", decision.decision_id, answer, "event-1")
    assert service.repository.student("student-a")["revision"] == 0
    assert service.repository.attempt("event-1") is None
    answer_next(service, event_id="event-1")
    assert service.repository.student("student-a")["revision"] == 1


def test_identical_event_retry_returns_original_result_without_update(service):
    original = answer_next(service, event_id="event-1")
    states = service.status("student-a")
    replayed = service.submit("student-a", original.decision_id,
                              original.selected_answer.lower(), "event-1")
    assert replayed.replayed is True
    assert asdict(replayed) | {"replayed": False} == asdict(original)
    assert service.status("student-a") == states
    assert service.repository.student("student-a")["revision"] == 1


def test_conflicting_event_or_consumed_assignment_rejected(service):
    result = answer_next(service, event_id="event-1")
    wrong_answer = "A" if result.selected_answer != "A" else "B"
    with pytest.raises(SubmissionConflict, match="冲突"):
        service.submit("student-a", result.decision_id, wrong_answer, "event-1")
    with pytest.raises(SubmissionConflict, match="已经提交"):
        service.submit("student-a", result.decision_id, result.selected_answer, "new-event")
    next_decision = service.next_action("student-a")
    with pytest.raises(SubmissionConflict, match="冲突"):
        service.submit("student-a", next_decision.decision_id, "A", "event-1")
    assert service.repository.student("student-a")["revision"] == 1


def test_student_isolation_and_assignment_ownership(service):
    service.register("student-b", ("logistic_regression",))
    decision = service.next_action("student-a")
    with pytest.raises(SubmissionConflict, match="不属于"):
        service.submit("student-b", decision.decision_id, "B", "bad-owner")
    answer_next(service)
    assert service.status("student-b")["linear_regression_loss"].probability == 0.2
    assert service.next_action("student-b").question["id"] == "lr_01"


def test_save_close_reopen_restores_goals_state_and_pending_assignment(catalog, tmp_path):
    path = tmp_path / "restart.sqlite3"
    with SQLiteRepository(path) as repository:
        first = LearningService(catalog, repository)
        first.register("student-a", ("logistic_regression",))
        result = answer_next(first, event_id="persisted-event")
        state = first.status("student-a")
        pending = first.next_action("student-a")
    with SQLiteRepository(path) as repository:
        restored = LearningService(catalog, repository)
        restored.register("student-a")
        assert restored.status("student-a") == state
        assert restored.next_action("student-a") == pending
        replay = restored.submit("student-a", result.decision_id, result.selected_answer, "persisted-event")
        assert replay.replayed
        answer_next(restored)
        assert restored.next_action("student-a").knowledge_id == "gradient_descent"


def test_atomic_rollback_when_mastery_write_fails(service):
    connection = service.repository.connection
    connection.execute("""CREATE TRIGGER fail_mastery BEFORE INSERT ON mastery
                          BEGIN SELECT RAISE(ABORT, 'injected failure'); END""")
    decision = service.next_action("student-a")
    with pytest.raises(sqlite3.IntegrityError, match="injected failure"):
        answer_next(service, event_id="rollback-event")
    assert service.repository.attempt("rollback-event") is None
    assert service.repository.student("student-a")["revision"] == 0
    assert all(state.attempts == 0 for state in service.status("student-a").values())
    assert service.next_action("student-a") == decision
    connection.execute("DROP TRIGGER fail_mastery")
    answer_next(service, event_id="rollback-event")
    assert service.repository.student("student-a")["revision"] == 1


def test_question_exhaustion_stops_instead_of_repeating(service):
    answer_next(service, correct=False)
    answer_next(service, correct=False)
    stop = service.next_action("student-a")
    assert stop.action == "stopped" and stop.stop_reason == "insufficient_questions"
    assert stop.question is None
    with pytest.raises(SubmissionConflict, match="没有可提交"):
        service.submit("student-a", stop.decision_id, "A", "after-stop")


def test_round_limit_persists_across_restart(catalog, tmp_path):
    path = tmp_path / "limit.sqlite3"
    policy = RulePolicy(max_rounds=1)
    with SQLiteRepository(path) as repository:
        service = LearningService(catalog, repository, policy=policy)
        service.register("student-a")
        answer_next(service)
    with SQLiteRepository(path) as repository:
        service = LearningService(catalog, repository, policy=policy)
        stop = service.next_action("student-a")
        assert stop.stop_reason == "round_limit" and stop.question is None


def test_full_five_topic_synthetic_loop(catalog, tmp_path):
    with SQLiteRepository(tmp_path / "complete.sqlite3") as repository:
        service = LearningService(catalog, repository)
        service.register("student-a")
        selected = []
        for _ in range(10):
            result = answer_next(service)
            selected.append(result.question_id)
            assert result.bank_version == "ml-questions-p1-v1"
            assert result.parameters["guess"] == 0.25
            assert result.question_version == "1"
        assert len(set(selected)) == 10
        assert service.next_action("student-a").action == "finish"
        assert all(s.attempts == 2 and s.probability == pytest.approx(0.82)
                   for s in service.status("student-a").values())


@pytest.mark.parametrize("change", ["parameters", "policy", "catalog"])
def test_configuration_drift_rejected_even_with_same_version(catalog, raw_data, tmp_path, change):
    path = tmp_path / "bound.sqlite3"
    with SQLiteRepository(path) as repository:
        LearningService(catalog, repository)
    parameters = BKTParameters(initial=0.3) if change == "parameters" else None
    policy = RulePolicy(threshold=0.9) if change == "policy" else None
    if change == "catalog":
        raw_data[1]["questions"][0]["stem"] += " changed"
        catalog = Catalog(*raw_data)
    with SQLiteRepository(path) as repository:
        with pytest.raises(ValueError, match="不能静默混用"):
            LearningService(catalog, repository, parameters, policy)


def test_goal_validation_and_existing_goals_not_silently_replaced(service):
    with pytest.raises(ValueError, match="已有不同"):
        service.register("student-a", ("model_evaluation",))
    with pytest.raises(ValueError, match="未知知识点"):
        service.register("bad-student", ("unknown",))
    assert service.repository.student("bad-student") is None
    with pytest.raises(ValueError, match="不能为空"):
        service.register("empty-goals", ())


@pytest.mark.parametrize("kwargs", [{"max_rounds": 0}, {"max_rounds": True}, {"threshold": 0}, {"threshold": 1.1}])
def test_invalid_policy_configuration(kwargs):
    with pytest.raises(ValueError):
        RulePolicy(**kwargs)
