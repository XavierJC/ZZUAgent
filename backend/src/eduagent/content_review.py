"""Offline checks and a reviewer packet; never changes a bank or review status."""

import argparse
from collections import Counter
import json
from pathlib import Path
import re

from eduagent.domain.catalog import Catalog


def _normalized(text: str) -> str:
    return re.sub(r"\s+", "", text).casefold()


def load_candidate(data_dir: Path, candidate_path: Path) -> tuple[Catalog, dict]:
    knowledge = json.loads((data_dir / "knowledge_points.json").read_text(encoding="utf-8"))
    candidate_data = json.loads(candidate_path.read_text(encoding="utf-8"))
    catalog = Catalog(knowledge, candidate_data)
    active = Catalog.load(data_dir)
    seen_stems: set[str] = set()
    for question in catalog.questions.values():
        stem = _normalized(question.stem)
        if stem in seen_stems:
            raise ValueError("候选题干存在完全重复（忽略空白与大小写）")
        seen_stems.add(stem)
        if len({_normalized(value) for value in question.options.values()}) != 4:
            raise ValueError(f"候选题 {question.id} 存在重复选项")
    # Preserve old evidence: edits to an existing question need a deliberate new
    # version/review, rather than being hidden in an additive candidate pack.
    for identifier, question in active.questions.items():
        if catalog.questions.get(identifier) != question:
            raise ValueError(f"候选包未原样保留当前题目 {identifier}")
    summary = {
        "candidate_version": catalog.bank_version,
        "candidate_fingerprint": catalog.fingerprint,
        "active_version": active.bank_version,
        "active_fingerprint": active.fingerprint,
        "question_count": len(catalog.questions),
        "added_count": len(set(catalog.questions) - set(active.questions)),
        "review_counts": dict(Counter(q.review_status for q in catalog.questions.values())),
        "coverage": {
            skill: dict(Counter(q.difficulty for q in catalog.questions.values() if q.knowledge_id == skill))
            for skill in catalog.ordered_knowledge
        },
        "human_review_performed": False,
        "active_bank_changed": False,
    }
    if any(not value for value in summary["coverage"].values()):
        raise ValueError("候选题库没有覆盖全部知识点")
    return catalog, summary


def render_review(catalog: Catalog, summary: dict) -> str:
    lines = [
        "# 候选题库逐题审阅单", "",
        "本文件由离线工具生成，包含标准答案，供负责人审阅。自动检查不代表人工校验。",
        "候选包尚未用于运行中的服务；请勿将本文件作为学生取题接口。", "",
        f"候选版本：`{catalog.bank_version}`；共 {len(catalog.questions)} 题。",
        f"候选内容指纹：`{summary['candidate_fingerprint']}`。",
        f"当前题库版本：`{summary['active_version']}`；新增 {summary['added_count']} 题。", "",
        "审阅方法：独立解题后检查唯一正确选项、解析、定义和难度；不合适的题目记录修改意见。",
        "勾选本单不会自动改变 JSON 状态。负责人完成审阅后，再单独登记 reviewer、reviewed_at 和 human_verified。",
        "题目或校验元数据变化会改变内容指纹，正式切换须使用新数据库，保留原学习记录。", "",
        "## 覆盖情况", "",
        "| 知识点 | easy | medium | hard |", "| --- | ---: | ---: | ---: |",
    ]
    for identifier, counts in summary["coverage"].items():
        lines.append(f"| {catalog.knowledge[identifier].name} | {counts.get('easy', 0)} | {counts.get('medium', 0)} | {counts.get('hard', 0)} |")
    for skill in catalog.ordered_knowledge:
        point = catalog.knowledge[skill]
        lines.extend(["", f"## {point.name}", "",
                      "先修约定：" + ("、".join(catalog.knowledge[p].name for p in point.prerequisites) or "无"),
                      "先修边属于教学配置，仍需单独审阅。"])
        for question in catalog.select(skill, count=len(catalog.questions)):
            lines.extend(["", f"### {question.id}（{question.difficulty}，{question.review_status}）", "", question.stem, ""])
            lines.extend(f"- {key}. {value}" for key, value in question.options.items())
            lines.extend(["", f"候选答案：**{question.answer}**", "", f"解析：{question.explanation}", "",
                          f"来源：{question.source}", "",
                          "- [ ] 已独立验算，正确选项唯一，解析成立。",
                          "- [ ] 定义清楚、选项无歧义、知识点与难度合适。", "",
                          "审阅人：____　日期：____　修改意见：____"])
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--candidate", type=Path, default=Path("data/candidates/questions-v2.json"))
    parser.add_argument("--output", type=Path, help="Create a new review packet; refuses to overwrite existing notes")
    args = parser.parse_args(argv)
    try:
        catalog, summary = load_candidate(args.data_dir, args.candidate)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(render_review(catalog, summary))
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps(summary, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
