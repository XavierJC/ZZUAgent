"""Evaluate local lexical retrieval on a declared development set, with no LLM."""

import argparse
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path

from eduagent.domain.catalog import Catalog
from eduagent.retrieval.index import CourseIndex


def load_dataset(path: Path, index: CourseIndex) -> dict:
    dataset = json.loads(path.read_text(encoding="utf-8"))
    if (not isinstance(dataset, dict) or not isinstance(dataset.get("version"), str)
            or not dataset["version"].strip() or dataset.get("split") != "development"
            or dataset.get("review_status") not in ("pending", "human_verified")):
        raise ValueError("评估集需声明版本、development 用途和审阅状态")
    cases = dataset.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("评估集 cases 必须是非空列表")
    passages = {p.citation_id: p for p in index.passages}
    skills = {p.knowledge_id for p in index.passages}
    seen = set()
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("评估案例必须是对象")
        identifier, query = case.get("id"), case.get("query")
        if not isinstance(identifier, str) or not identifier.strip() or identifier in seen:
            raise ValueError("评估案例 ID 为空或重复")
        seen.add(identifier)
        if not isinstance(query, str) or not query.strip() or len(query) > 1000:
            raise ValueError("评估问题必须为 1～1000 字符")
        skill = case.get("knowledge_id")
        if skill is not None and (not isinstance(skill, str) or skill not in skills):
            raise ValueError("评估案例知识点无效")
        expected = case.get("expected_citation_ids")
        if (not isinstance(expected, list) or any(not isinstance(x, str) or x not in passages for x in expected)
                or len(set(expected)) != len(expected)):
            raise ValueError("预期章节 ID 无效或重复")
        if skill is not None and any(passages[x].knowledge_id != skill for x in expected):
            raise ValueError("预期章节与限定知识点不符")
    return dataset


def evaluate(index: CourseIndex, dataset: dict) -> dict:
    rows = []
    positives = top1 = top3 = negatives = rejected = 0
    reciprocal_sum = 0.0
    for case in dataset["cases"]:
        matches = index.search(case["query"], case.get("knowledge_id"), top_k=3)
        retrieved = [match["citation_id"] for match in matches]
        expected = case["expected_citation_ids"]
        rank = next((position for position, identifier in enumerate(retrieved, 1) if identifier in expected), None)
        if expected:
            positives += 1
            top1 += rank == 1
            top3 += rank is not None
            reciprocal_sum += 1 / rank if rank else 0
        else:
            negatives += 1
            rejected += not retrieved
        rows.append({
            **case, "retrieved_citation_ids": retrieved,
            "scores": [match["score"] for match in matches],
            "first_relevant_rank": rank,
            "passed": rank is not None if expected else not retrieved,
        })
    def rate(numerator: float, denominator: int) -> float | None:
        return numerator / denominator if denominator else None
    return {
        "dataset_version": dataset["version"], "split": dataset["split"],
        "review_status": dataset["review_status"], "positive_cases": positives,
        "negative_cases": negatives,
        "metrics": {"hit_at_1": rate(top1, positives), "hit_at_3": rate(top3, positives),
                    "mrr_at_3": rate(reciprocal_sum, positives),
                    "negative_empty_rate": rate(rejected, negatives)},
        "model_requests": 0, "cases": rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--dataset", type=Path, default=Path("data/evaluation/retrieval-dev-v1.json"))
    parser.add_argument("--policy", choices=("baseline", "phrase"), default="phrase",
                        help="Keep the original baseline reproducible; default uses the phrase guard")
    parser.add_argument("--output", type=Path, help="Optional new JSON report; existing reports are never overwritten")
    args = parser.parse_args(argv)
    try:
        catalog = Catalog.load(args.data_dir)
        index = CourseIndex(args.data_dir / "materials", set(catalog.knowledge), phrase_gate=args.policy == "phrase")
        report = evaluate(index, load_dataset(args.dataset, index))
        raw_corpus = json.dumps([asdict(p) for p in index.passages], ensure_ascii=False, sort_keys=True)
        report.update(corpus_fingerprint=sha256(raw_corpus.encode("utf-8")).hexdigest(),
                      dataset_fingerprint=sha256(args.dataset.read_bytes()).hexdigest(),
                      passage_count=len(index.passages), top_k=3,
                      algorithm="FAISS + normalized TF-IDF; minimum cosine score 0.12",
                      retrieval_policy=index.configuration)
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
