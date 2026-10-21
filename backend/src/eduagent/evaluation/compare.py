"""Compare next decisions on paired, synthetic states; no model or live DB."""

import argparse
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path

from eduagent.agent.policy import RulePolicy
from eduagent.domain.bkt import BKTParameters
from eduagent.domain.catalog import Catalog, required_text
from eduagent.domain.models import Mastery, Recommendation
from eduagent.evaluation.fixed import FixedSequencePolicy
from eduagent.services.learning import LearningService
from eduagent.storage.sqlite import SQLiteRepository


def fingerprint(value: object) -> str:
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)
    return sha256(canonical.encode("utf-8")).hexdigest()


def validate_dataset(dataset: dict, catalog: Catalog) -> None:
    if not isinstance(dataset, dict) or dataset.get("split") != "development":
        raise ValueError("策略情景集必须声明 development 用途")
    for field in ("version", "source", "notes"):
        required_text(dataset.get(field), field)
    if dataset.get("review_status") not in ("pending", "human_verified"):
        raise ValueError("情景集需要审阅状态")
    if dataset["review_status"] == "human_verified":
        required_text(dataset.get("reviewer"), "人工审阅人")
        required_text(dataset.get("reviewed_at"), "人工审阅日期")
    cases = dataset.get("cases")
    if not isinstance(cases, list) or not 1 <= len(cases) <= 100:
        raise ValueError("cases 必须包含 1～100 个情景")
    seen = set()
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("情景必须是对象")
        identifier = required_text(case.get("id"), "情景 ID")
        required_text(case.get("label"), "情景说明")
        if identifier in seen:
            raise ValueError("情景 ID 重复")
        seen.add(identifier)
        goals = case.get("goals")
        if (not isinstance(goals, list) or not goals
                or any(not isinstance(goal, str) for goal in goals) or len(set(goals)) != len(goals)):
            raise ValueError("goals 必须是非空且不重复的知识点列表")
        required = catalog.expand_goals(goals)
        history = case.get("history")
        if not isinstance(history, list) or len(history) > 20:
            raise ValueError("history 必须是最多 20 条的合成答题列表")
        questions = set()
        for item in history:
            if not isinstance(item, dict):
                raise ValueError("答题项必须是对象")
            question_id = item.get("question_id")
            if not isinstance(question_id, str) or question_id not in catalog.questions:
                raise ValueError("答题历史引用未知题目")
            question = catalog.questions[question_id]
            if question_id in questions or question.knowledge_id not in required:
                raise ValueError("答题历史重复或超出目标及先修范围")
            questions.add(question_id)
            question.grade(item.get("answer"))  # Reject invalid options; never trust a supplied score.


def load_dataset(path: Path, catalog: Catalog) -> dict:
    dataset = json.loads(path.read_text(encoding="utf-8"))
    validate_dataset(dataset, catalog)
    return dataset


def _replay(case: dict, catalog: Catalog, parameters: BKTParameters, policy: RulePolicy) -> tuple[dict, list]:
    """Use actual assignment, scoring, BKT and SQLite, isolated in memory.

    Each prefix must be reachable under the application policy. We then query
    both policies at the *same* state; we do not invent counterfactual answers
    to questions that one policy would never assign.
    """
    with SQLiteRepository(":memory:") as repository:
        service = LearningService(catalog, repository, parameters, policy)
        student_id = "synthetic-paired-state"
        service.register(student_id, tuple(case["goals"]))
        observations = []
        for position, item in enumerate(case["history"]):
            decision = service.next_action(student_id)
            if decision.question is None or decision.question["id"] != item["question_id"]:
                raise ValueError(f"情景 {case['id']} 第 {position + 1} 题不符合实际分配")
            result = service.submit(student_id, decision.decision_id, item["answer"], f"event-{position}")
            observations.append({key: getattr(result, key) for key in (
                "question_id", "knowledge_id", "selected_answer", "correct", "prior", "posterior", "next_mastery")})
        snapshot = service.snapshot(student_id)
        shared = {
            "student_id": snapshot.student_id, "revision": snapshot.revision, "goals": list(snapshot.goals),
            "states": {state.knowledge_id: asdict(state) for state in snapshot.mastery},
            "answered": sorted(repository.answered_questions(student_id)),
        }
    return shared, observations


def _decision_view(decision: Recommendation, states: dict[str, Mastery], catalog: Catalog, threshold: float) -> dict:
    # Diagnostic only: the reference criterion is the application's rule,
    # not a validated universal definition of pedagogical prerequisite mastery.
    prerequisites = catalog.expand_goals((decision.knowledge_id,))[:-1] if decision.question else ()
    weak = [key for key in prerequisites if not (
        states[key].attempts > 0 and states[key].probability >= threshold and states[key].last_correct is True)]
    return {"action": decision.action, "knowledge_id": decision.knowledge_id,
            "question_id": decision.question["id"] if decision.question else None,
            "stop_reason": decision.stop_reason, "reason": decision.reason, "evidence": decision.evidence,
            "weak_prerequisites": weak}


def evaluate(catalog: Catalog, dataset: dict) -> dict:
    validate_dataset(dataset, catalog)
    adaptive, fixed, parameters = RulePolicy(), FixedSequencePolicy(), BKTParameters()
    rows = []
    for case in dataset["cases"]:
        shared, observations = _replay(case, catalog, parameters, adaptive)
        original = fingerprint(shared)
        states = {key: Mastery(**value) for key, value in shared["states"].items()}
        inputs = dict(decision_id="evaluation-only", student_id=shared["student_id"], revision=shared["revision"],
                      goals=tuple(shared["goals"]), states=states, answered=set(shared["answered"]), catalog=catalog)
        decisions = {}
        input_fingerprints = {}
        for name, policy in (("adaptive", adaptive), ("fixed", fixed)):
            current = {**shared, "states": {key: asdict(value) for key, value in states.items()},
                       "answered": sorted(inputs["answered"])}
            input_fingerprints[name] = fingerprint(current)
            if input_fingerprints[name] != original:
                raise RuntimeError("策略更改了共享输入，比较无效")
            decisions[name] = _decision_view(policy.decide(**inputs), states, catalog, adaptive.threshold)
        after = {**shared, "states": {key: asdict(value) for key, value in states.items()},
                 "answered": sorted(inputs["answered"])}
        if fingerprint(after) != original:
            raise RuntimeError("策略更改了共享输入，比较无效")
        a, b = decisions["adaptive"], decisions["fixed"]
        selection_differs = (a["knowledge_id"], a["question_id"]) != (b["knowledge_id"], b["question_id"])
        behavior_differs = selection_differs or (a["action"], a["stop_reason"]) != (b["action"], b["stop_reason"])
        rows.append({"id": case["id"], "label": case["label"], "shared_input": shared,
                     "input_fingerprints": input_fingerprints, "input_unchanged": True,
                     "observations": observations, **decisions, "selection_differs": selection_differs,
                     "behavior_differs": behavior_differs})
    counts = {}
    for name in ("adaptive", "fixed"):
        decisions = [row[name] for row in rows]
        counts[name] = {
            "exercise_assignments": sum(d["question_id"] is not None for d in decisions),
            "stopped": sum(d["action"] == "stopped" for d in decisions),
            "finished": sum(d["action"] == "finish" for d in decisions),
            "assignments_with_weak_prerequisites": sum(bool(d["weak_prerequisites"]) for d in decisions),
        }
    return {
        "evaluation_version": "paired-next-decision-v1", "dataset_version": dataset["version"],
        "dataset_fingerprint": fingerprint(dataset), "split": dataset["split"],
        "review_status": dataset["review_status"], "source": dataset["source"], "notes": dataset["notes"],
        "catalog_fingerprint": catalog.fingerprint, "bank_version": catalog.bank_version,
        "question_count": len(catalog.questions),
        "pending_question_count": sum(q.review_status == "pending" for q in catalog.questions.values()),
        "bkt_parameters": asdict(parameters), "policies": {"adaptive": asdict(adaptive), "fixed": asdict(fixed)},
        "prerequisite_reference": "attempts > 0 AND probability >= 0.80 AND last_correct is True; all ancestors",
        "case_count": len(rows), "counts": counts,
        "selection_difference_cases": sum(row["selection_differs"] for row in rows),
        "action_only_difference_cases": sum(row["behavior_differs"] and not row["selection_differs"] for row in rows),
        "identical_behavior_cases": sum(not row["behavior_differs"] for row in rows),
        "model_requests": 0, "database": ":memory:", "live_database_written": False,
        "learning_effect_measured": False, "cases": rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--dataset", type=Path, default=Path("data/evaluation/policy-paired-v1.json"))
    parser.add_argument("--output", type=Path, help="Optional new JSON report; existing files are never overwritten")
    args = parser.parse_args(argv)
    try:
        catalog = Catalog.load(args.data_dir)
        report = evaluate(catalog, load_dataset(args.dataset, catalog))
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("x", encoding="utf-8", newline="\n") as stream:
                json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
                stream.write("\n")
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps({key: value for key, value in report.items() if key != "cases"}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
