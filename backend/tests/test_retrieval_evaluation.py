from copy import deepcopy
import json

import pytest

from eduagent.retrieval.evaluate import evaluate, load_dataset, main
from eduagent.retrieval.index import CourseIndex


@pytest.fixture
def index(data_dir, catalog):
    return CourseIndex(data_dir / "materials", set(catalog.knowledge))


def test_development_dataset_is_explicit_and_references_real_sections(index, data_dir):
    dataset = load_dataset(data_dir / "evaluation/retrieval-dev-v1.json", index)
    assert dataset["split"] == "development" and dataset["review_status"] == "pending"
    assert len(dataset["cases"]) == 30
    assert sum(bool(case["expected_citation_ids"]) for case in dataset["cases"]) == 25
    assert {identifier for case in dataset["cases"] for identifier in case["expected_citation_ids"]} == {
        p.citation_id for p in index.passages}


def test_metrics_use_first_relevant_rank_and_separate_negative_denominator():
    class FixedIndex:
        def search(self, query, knowledge_id, top_k):
            assert top_k == 3
            results = {"p1": ["noise", "r1"], "p2": ["r2"], "p3": [], "n1": [], "n2": ["noise"]}
            return [{"citation_id": identifier, "score": 0.5} for identifier in results[query]]
    dataset = {"version": "fixed", "split": "development", "review_status": "pending", "cases": [
        {"id": name, "query": name, "expected_citation_ids": ["r" + name[1:]] if name.startswith("p") else []}
        for name in ["p1", "p2", "p3", "n1", "n2"]]}
    report = evaluate(FixedIndex(), dataset)
    assert report["metrics"] == pytest.approx({"hit_at_1": 1 / 3, "hit_at_3": 2 / 3,
                                              "mrr_at_3": 0.5, "negative_empty_rate": 0.5})
    assert report["positive_cases"] == 3 and report["negative_cases"] == 2
    assert report["cases"][0]["first_relevant_rank"] == 2
    assert report["cases"][-1]["passed"] is False
    assert report["model_requests"] == 0
    negative_only = deepcopy(dataset)
    negative_only["cases"] = negative_only["cases"][-2:]
    assert evaluate(FixedIndex(), negative_only)["metrics"]["hit_at_1"] is None


@pytest.mark.parametrize("change", ["duplicate_id", "unknown_section", "wrong_scope", "unknown_skill", "blank_query", "wrong_split"])
def test_invalid_evaluation_labels_are_rejected(index, data_dir, tmp_path, change):
    dataset = json.loads((data_dir / "evaluation/retrieval-dev-v1.json").read_text(encoding="utf-8"))
    if change == "duplicate_id":
        dataset["cases"][1]["id"] = dataset["cases"][0]["id"]
    elif change == "unknown_section":
        dataset["cases"][0]["expected_citation_ids"] = ["fiction:99"]
    elif change == "wrong_scope":
        dataset["cases"][0]["knowledge_id"] = "gradient_descent"
    elif change == "unknown_skill":
        dataset["cases"][0]["knowledge_id"] = "unknown"
    elif change == "blank_query":
        dataset["cases"][0]["query"] = " "
    else:
        dataset["split"] = "held_out"
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(dataset), encoding="utf-8")
    with pytest.raises(ValueError):
        load_dataset(path, index)


def test_evaluation_command_saves_cases_and_does_not_overwrite_report(data_dir, tmp_path, capsys):
    path = tmp_path / "report.json"
    args = ["--data-dir", str(data_dir), "--dataset", str(data_dir / "evaluation/retrieval-dev-v1.json"),
            "--output", str(path)]
    assert main(args) == 0
    summary = json.loads(capsys.readouterr().out)
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert summary["passage_count"] == 15 and len(saved["cases"]) == 30
    assert len(summary["corpus_fingerprint"]) == 64
    assert len(summary["dataset_fingerprint"]) == 64
    original = path.read_bytes()
    with pytest.raises(SystemExit) as error:
        main(args)
    assert error.value.code == 2 and path.read_bytes() == original
