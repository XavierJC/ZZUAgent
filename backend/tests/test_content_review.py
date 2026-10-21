import json
import math
from statistics import fmean

import pytest

from eduagent.content_review import load_candidate, main, render_review
from eduagent.services.learning import LearningService
from eduagent.storage.sqlite import SQLiteRepository


@pytest.fixture
def candidate(data_dir):
    return load_candidate(data_dir, data_dir / "candidates/questions-v2.json")


def test_candidate_is_additive_pending_and_balanced(candidate, catalog):
    bank, summary = candidate
    assert summary["question_count"] == 40 and summary["added_count"] == 30
    assert summary["review_counts"] == {"pending": 40}
    assert summary["active_fingerprint"] == catalog.fingerprint != bank.fingerprint
    assert all(summary["coverage"][skill] == {"easy": 3, "medium": 3, "hard": 2}
               for skill in catalog.knowledge)
    assert all(bank.questions[key] == question for key, question in catalog.questions.items())
    assert not summary["human_review_performed"] and not summary["active_bank_changed"]


# Independently compute numeric answers; these checks cannot establish wording,
# teaching value, difficulty, or every conceptual answer's correctness.
@pytest.mark.parametrize("identifier,computed", [
    ("lr_03", lambda: f"{2 * 3 + 1:g}"),
    ("lr_04", lambda: f"{fmean([-1, 1]):g} 和 {fmean([(-1) ** 2, 1 ** 2]):g}"),
    ("lr_05", lambda: f"{(2 ** 2 + (-2) ** 2) / (2 * 2):g}"),
    ("lr_06", lambda: f"{fmean([1, 2, 6]):g}"),
    ("lr_07", lambda: f"{fmean([1 - 2, 3 - 1]):g}"),
    ("lr_08", lambda: "(" + ",".join(f"{(1 * 2 - 1 * 1 - 4) * x:g}" for x in [2, 1]) + ")"),
    ("gd_03", lambda: f"{1 - 0.25 * (-4):g}"),
    ("gd_05", lambda: f"{4 * (1 - 0.5) ** 2:g}"),
    ("gd_07", lambda: f"0<η<{2 / max([1, 4]):g}"),
    ("gd_08", lambda: f"{3 - 0.2 * fmean([2, -1, 5]):g}"),
    ("log_04", lambda: f"{1 / (1 + math.exp(math.log(3))):g}"),
    ("log_05", lambda: f"-ln({1 - 0.2:g})"),
    ("log_06", lambda: f"{math.exp(math.log(4)):g}"),
    ("log_07", lambda: f"{0.8 - 1:g}"),
    ("reg_05", lambda: f"{(0.2 / 2) * (3 ** 2 + 4 ** 2):g}"),
    ("reg_06", lambda: f"{2 - 0.1 * (3 + 0.5 * 2):g}"),
    ("reg_07", lambda: f"({4 / (1 + 1):g},{2 / (1 + 1):g})ᵀ"),
    ("eval_03", lambda: f"{90 / 100:.0%} 和 {0 / 10:g}"),
    ("eval_04", lambda: f"{6 / (6 + 4):g}"),
    ("eval_05", lambda: f"{2 * 0.75 * 0.5 / (0.75 + 0.5):g}"),
    ("eval_06", lambda: f"{(8 + 6) / (8 + 2 + 4 + 6):g}"),
])
def test_candidate_numeric_answers_from_independent_calculation(candidate, identifier, computed):
    bank, _ = candidate
    question = bank.questions[identifier]
    assert question.options[question.answer] == computed()


@pytest.mark.parametrize("change", ["duplicate_stem", "duplicate_options", "changed_active"])
def test_candidate_audit_rejects_ambiguous_or_silently_changed_content(data_dir, tmp_path, change):
    data = json.loads((data_dir / "candidates/questions-v2.json").read_text(encoding="utf-8"))
    if change == "duplicate_stem":
        data["questions"][-1]["stem"] = data["questions"][0]["stem"] + "  "
    elif change == "duplicate_options":
        options = data["questions"][-1]["options"]
        options["D"] = options["A"]
    else:
        data["questions"][0]["explanation"] += " altered"
    path = tmp_path / "candidate.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError):
        load_candidate(data_dir, path)


def test_review_packet_includes_all_questions_and_preserves_existing_notes(candidate, data_dir, tmp_path, capsys):
    bank, summary = candidate
    packet = render_review(bank, summary)
    assert packet.count("审阅人：____") == 40
    assert "自动检查不代表人工校验" in packet
    output = tmp_path / "review.md"
    args = ["--data-dir", str(data_dir), "--candidate", str(data_dir / "candidates/questions-v2.json"),
            "--output", str(output)]
    assert main(args) == 0
    assert json.loads(capsys.readouterr().out)["question_count"] == 40
    output.write_text("reviewer notes", encoding="utf-8")
    with pytest.raises(SystemExit) as error:
        main(args)
    assert error.value.code == 2 and output.read_text(encoding="utf-8") == "reviewer notes"


def test_candidate_allows_recovery_after_two_errors_without_repeating(candidate, tmp_path):
    bank, _ = candidate
    path = tmp_path / "candidate.sqlite3"
    seen = []
    with SQLiteRepository(path) as repository:
        service = LearningService(bank, repository)
        service.register("synthetic", ("gradient_descent",))
        for step in range(5):
            decision = service.next_action("synthetic")
            question = bank.questions[decision.question["id"]]
            seen.append(question.id)
            answer = next(a for a in question.options if a != question.answer) if step < 2 else question.answer
            service.submit("synthetic", decision.decision_id, answer, f"answer-{step}")
        pending = service.next_action("synthetic")
        assert pending.action == "advance" and pending.knowledge_id == "gradient_descent"
        assert service.status("synthetic")["linear_regression_loss"].probability > 0.8
    assert seen == ["lr_01", "lr_02", "lr_03", "lr_04", "lr_05"]
    with SQLiteRepository(path) as repository:
        restored = LearningService(bank, repository)
        assert restored.next_action("synthetic") == pending
        assert restored.snapshot("synthetic").revision == 5


def test_candidate_cannot_rebind_existing_active_database(candidate, catalog, tmp_path):
    bank, _ = candidate
    path = tmp_path / "active.sqlite3"
    with SQLiteRepository(path) as repository:
        service = LearningService(catalog, repository)
        service.register("existing", ("linear_regression_loss",))
        decision = service.next_action("existing")
        service.submit("existing", decision.decision_id, "B", "original-answer")
    with SQLiteRepository(path) as repository:
        with pytest.raises(ValueError, match="不能静默混用"):
            LearningService(bank, repository)
    with SQLiteRepository(path) as repository:
        original = LearningService(catalog, repository)
        assert original.snapshot("existing").revision == 1
        assert repository.attempt("original-answer").correct is True
