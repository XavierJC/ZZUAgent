"""Load versioned JSON knowledge points/questions and reject invalid content."""

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Iterable


def required_text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} 必须是非空字符串")
    return value


def normalize_answer(answer: str) -> str:
    return required_text(answer, "答案").strip().upper()


@dataclass(frozen=True)
class KnowledgePoint:
    id: str
    name: str
    prerequisites: tuple[str, ...]
    review_tip: str


@dataclass(frozen=True)
class Question:
    id: str
    version: str
    knowledge_id: str
    difficulty: str
    stem: str
    options: dict[str, str]
    answer: str
    explanation: str
    source: str
    review_status: str

    def public_view(self) -> dict[str, Any]:
        """Do not expose the answer or explanation before submission."""
        fields = asdict(self)
        del fields["answer"]
        del fields["explanation"]
        return fields

    def grade(self, answer: str) -> bool:
        selected = normalize_answer(answer)
        if selected not in self.options:
            raise ValueError("只能提交题目提供的选项 A/B/C/D")
        return selected == self.answer


class Catalog:
    def __init__(self, knowledge_data: dict, question_data: dict):
        if not isinstance(knowledge_data, dict) or not isinstance(question_data, dict):
            raise ValueError("知识点与题库 JSON 顶层必须是对象")
        self.knowledge_version = required_text(knowledge_data.get("version"), "知识点版本")
        self.bank_version = required_text(question_data.get("version"), "题库版本")
        self.knowledge: dict[str, KnowledgePoint] = {}
        self.questions: dict[str, Question] = {}
        for item in self._items(knowledge_data, "knowledge_points"):
            identifier = required_text(item.get("id"), "知识点 ID")
            if identifier in self.knowledge:
                raise ValueError(f"重复知识点 ID: {identifier}")
            deps = item.get("prerequisites")
            if not isinstance(deps, list) or any(not isinstance(x, str) or not x for x in deps):
                raise ValueError("prerequisites 必须是知识点 ID 列表")
            if len(set(deps)) != len(deps):
                raise ValueError("先修知识点不能重复")
            self.knowledge[identifier] = KnowledgePoint(
                identifier, required_text(item.get("name"), "知识点名称"), tuple(deps),
                required_text(item.get("review_tip"), "复习提示"),
            )
        self.ordered_knowledge = self.expand_goals(tuple(self.knowledge))
        for item in self._items(question_data, "questions"):
            identifier = required_text(item.get("id"), "题目 ID")
            if identifier in self.questions:
                raise ValueError(f"重复题目 ID: {identifier}")
            knowledge_id = required_text(item.get("knowledge_id"), "题目知识点")
            if knowledge_id not in self.knowledge:
                raise ValueError(f"题目引用未知知识点: {knowledge_id}")
            difficulty = item.get("difficulty")
            if difficulty not in ("easy", "medium", "hard"):
                raise ValueError("difficulty 必须为 easy/medium/hard")
            options = item.get("options")
            if not isinstance(options, dict) or set(options) != set("ABCD"):
                raise ValueError("四选一题目必须包含且仅包含 A/B/C/D")
            for value in options.values():
                required_text(value, "选项内容")
            answer = item.get("answer")
            if not isinstance(answer, str) or answer not in options:
                raise ValueError("题目正确答案必须是一个有效选项")
            status = item.get("review_status")
            if status not in ("pending", "human_verified"):
                raise ValueError("review_status 必须为 pending/human_verified")
            if status == "human_verified":
                required_text(item.get("reviewer"), "人工校验人")
                required_text(item.get("reviewed_at"), "人工校验日期")
            self.questions[identifier] = Question(
                identifier, required_text(item.get("version"), "题目版本"), knowledge_id,
                difficulty, required_text(item.get("stem"), "题干"), dict(options), answer,
                required_text(item.get("explanation"), "解析"),
                required_text(item.get("source"), "来源"), status,
            )
        raw = json.dumps([knowledge_data, question_data], sort_keys=True, ensure_ascii=False)
        self.fingerprint = sha256(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _items(data: dict, key: str) -> list[dict]:
        items = data.get(key)
        if not isinstance(items, list) or not items or any(not isinstance(i, dict) for i in items):
            raise ValueError(f"{key} 必须是非空对象列表")
        return items

    @classmethod
    def load(cls, data_dir: Path) -> "Catalog":
        return cls(
            json.loads((data_dir / "knowledge_points.json").read_text(encoding="utf-8")),
            json.loads((data_dir / "questions.json").read_text(encoding="utf-8")),
        )

    def expand_goals(self, goals: Iterable[str]) -> tuple[str, ...]:
        """Stable topological order, including transitive prerequisites."""
        ordered: list[str] = []
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(identifier: str) -> None:
            if identifier not in self.knowledge:
                raise ValueError(f"未知知识点: {identifier}")
            if identifier in visiting:
                raise ValueError("先修关系存在环")
            if identifier in visited:
                return
            visiting.add(identifier)
            for parent in self.knowledge[identifier].prerequisites:
                visit(parent)
            visiting.remove(identifier)
            visited.add(identifier)
            ordered.append(identifier)

        for goal in goals:
            visit(goal)
        if not ordered:
            raise ValueError("学习目标不能为空")
        return tuple(ordered)

    def select(self, knowledge_id: str, exclude: Iterable[str] = (),
               difficulty: str | None = None, count: int = 1) -> list[Question]:
        if knowledge_id not in self.knowledge:
            raise ValueError(f"未知知识点: {knowledge_id}")
        if difficulty is not None and difficulty not in ("easy", "medium", "hard"):
            raise ValueError("无效难度")
        if isinstance(count, bool) or not isinstance(count, int) or count < 1:
            raise ValueError("选题数量必须为正整数")
        excluded = set(exclude)
        # JSON order is the reproducible selection order, not random sampling.
        return [q for q in self.questions.values() if q.knowledge_id == knowledge_id
                and q.id not in excluded and (difficulty is None or q.difficulty == difficulty)][:count]
