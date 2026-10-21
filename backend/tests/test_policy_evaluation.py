from copy import deepcopy
from dataclasses import replace
import json

import pytest

from eduagent.domain.models import Mastery
from eduagent.evaluation.compare import evaluate, fingerprint, load_dataset, main
from eduagent.evaluation.fixed import FixedSequencePolicy


def decide(catalog, *, policy=None, answered=(), states=None, revision=None):
    return (policy or FixedSequencePolicy()).decide(
        decision_id="test", student_id="synthetic", revision=len(answered) if revision is None else revision,
        goals=("logistic_regression",), answered=set(answered), catalog=catalog,
        states=states or {key: Mastery(key, 0.2) for key in catalog.knowledge})


@pytest.fixture
def dataset(data_dir, catalog):
    return load_dataset(data_dir / "evaluation/policy-paired-v1.json", catalog)


def test_fixed_baseline_uses_exercise_quota_instead_of_bkt(catalog):
    prior = {key: Mastery(key, 0.2) for key in catalog.knowledge}
    high = {key: replace(state, probability=0.99, attempts=8, last_correct=True) for key, state in prior.items()}
    # High mastery alone does not skip the fixed exercise quota.
    assert decide(catalog, states=high).question["id"] == "lr_01"
    wrong = {**prior, "linear_regression_loss": Mastery("linear_regression_loss", 0.129, 1, False)}
    assert decide(catalog, answered=("lr_01",), states=wrong).action == "practice"
    next_topic = decide(catalog, answered=("lr_01", "lr_02"))
    assert next_topic.action == "advance" and next_topic.question["id"] == "gd_01"
    assert "answer" not in next_topic.question and "explanation" not in next_topic.question


def test_fixed_baseline_stops_when_quota_cannot_be_met(catalog):
    stopped = decide(catalog, policy=FixedSequencePolicy(questions_per_skill=3), answered=("lr_01", "lr_02"))
    assert stopped.action == "stopped" and stopped.stop_reason == "insufficient_questions"
    assert stopped.knowledge_id == "linear_regression_loss" and stopped.question is None


def test_fixed_completion_means_quota_only_and_ignores_unrelated_topics(catalog):
    finished = decide(catalog, answered=("lr_01", "lr_02", "gd_01", "gd_02", "log_01", "log_02"))
    assert finished.action == "finish" and finished.question is None
    assert finished.evidence["completion_basis"] == "exercise_quota_only"
    assert "不判定" in finished.reason
    assert "model_evaluation" not in finished.evidence["required_knowledge"]


def test_fixed_round_limit_returns_no_question(catalog):
    stopped = decide(catalog, policy=FixedSequencePolicy(max_rounds=1), answered=("lr_01",))
    assert stopped.stop_reason == "round_limit" and stopped.question is None


@pytest.mark.parametrize("kwargs", [
    {"questions_per_skill": True}, {"questions_per_skill": 0}, {"questions_per_skill": 1.5},
    {"max_rounds": False}, {"max_rounds": -1},
])
def test_fixed_baseline_rejects_invalid_limits(kwargs):
    with pytest.raises(ValueError):
        FixedSequencePolicy(**kwargs)


def test_paired_states_replay_real_grading_and_preserve_identical_inputs(catalog, dataset):
    report = evaluate(catalog, dataset)
    rows = {row["id"]: row for row in report["cases"]}
    assert report["case_count"] == 8 and report["pending_question_count"] == 10
    assert report["counts"] == {
        "adaptive": {"exercise_assignments": 4, "stopped": 3, "finished": 1,
                     "assignments_with_weak_prerequisites": 0},
        "fixed": {"exercise_assignments": 7, "stopped": 0, "finished": 1,
                  "assignments_with_weak_prerequisites": 3},
    }
    assert (report["selection_difference_cases"], report["action_only_difference_cases"],
            report["identical_behavior_cases"]) == (3, 2, 3)
    for row in rows.values():
        assert row["input_unchanged"]
        assert row["input_fingerprints"]["adaptive"] == row["input_fingerprints"]["fixed"] == fingerprint(row["shared_input"])
        assert len(row["observations"]) == row["shared_input"]["revision"]
    mixed = rows["lr-mixed"]
    assert mixed["shared_input"]["states"]["linear_regression_loss"]["probability"] == pytest.approx(19 / 46)
    assert [item["correct"] for item in mixed["observations"]] == [False, True]
    assert mixed["adaptive"]["stop_reason"] == "insufficient_questions"
    assert mixed["fixed"]["question_id"] == "gd_01"
    assert mixed["fixed"]["weak_prerequisites"] == ["linear_regression_loss"]
    assert rows["lr-wrong"]["adaptive"]["action"] == "review"
    assert rows["lr-wrong"]["fixed"]["action"] == "practice"
    for row in (rows["lr-wrong"], rows["gd-wrong"]):
        assert not row["selection_differs"]  # A review label is not a different exercise.
    assert rows["goal-done"]["adaptive"]["action"] == rows["goal-done"]["fixed"]["action"] == "finish"
    assert report["model_requests"] == 0 and report["database"] == ":memory:"
    assert not report["learning_effect_measured"] and not report["live_database_written"]


def test_comparison_is_reproducible_and_does_not_edit_catalog_or_dataset(catalog, dataset):
    original = deepcopy(dataset)
    questions = deepcopy(catalog.questions)
    first = evaluate(catalog, dataset)
    assert first == evaluate(catalog, dataset)  # No UUIDs or wall-clock timestamps in the report.
    assert dataset == original and catalog.questions == questions


@pytest.mark.parametrize("change", [
    "duplicate_id", "unknown_question", "repeat_question", "invalid_answer", "unknown_goal",
    "outside_goal", "wrong_split", "empty_history_type", "unverified_human_claim",
])
def test_invalid_paired_scenarios_are_rejected(catalog, dataset, change):
    value = deepcopy(dataset)
    if change == "duplicate_id":
        value["cases"][1]["id"] = value["cases"][0]["id"]
    elif change == "unknown_question":
        value["cases"][1]["history"][0]["question_id"] = "missing"
    elif change == "repeat_question":
        value["cases"][1]["history"] *= 2
    elif change == "invalid_answer":
        value["cases"][1]["history"][0]["answer"] = "E"
    elif change == "unknown_goal":
        value["cases"][0]["goals"] = ["unknown"]
    elif change == "outside_goal":
        value["cases"][1]["history"][0]["question_id"] = "eval_01"
    elif change == "wrong_split":
        value["split"] = "held_out"
    elif change == "empty_history_type":
        value["cases"][0]["history"] = None
    else:
        value["review_status"] = "human_verified"
    with pytest.raises(ValueError):
        evaluate(catalog, value)


@pytest.mark.parametrize("index,question_id", [(1, "lr_02"), (2, "gd_01")])
def test_unreachable_history_is_rejected_instead_of_inventing_assignment(catalog, dataset, index, question_id):
    value = deepcopy(dataset)
    if index == 1:
        value["cases"][index]["history"][0]["question_id"] = question_id
    else:
        value["cases"][index]["history"].append({"question_id": question_id, "answer": "C"})
    with pytest.raises(ValueError, match="不符合实际分配"):
        evaluate(catalog, value)


def test_command_saves_stable_report_and_refuses_overwrite(catalog, data_dir, tmp_path, capsys):
    path = tmp_path / "paired.json"
    args = ["--data-dir", str(data_dir), "--dataset", str(data_dir / "evaluation/policy-paired-v1.json"),
            "--output", str(path)]
    assert main(args) == 0
    summary = json.loads(capsys.readouterr().out)
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert summary["catalog_fingerprint"] == catalog.fingerprint and len(saved["cases"]) == 8
    assert summary["dataset_fingerprint"] == fingerprint(load_dataset(data_dir / "evaluation/policy-paired-v1.json", catalog))
    original = path.read_bytes()
    with pytest.raises(SystemExit) as error:
        main(args)
    assert error.value.code == 2 and path.read_bytes() == original
