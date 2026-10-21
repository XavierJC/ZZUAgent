"""Explicit paid live check; never run as part of automatic unit tests."""

import argparse
import json
from pathlib import Path
from uuid import uuid4

from eduagent.agent.deepseek import DeepSeekClient
from eduagent.agent.settings import AgentSettings
from eduagent.agent.tutor import Tutor
from eduagent.config import local_configuration
from eduagent.domain.catalog import Catalog
from eduagent.retrieval.index import CourseIndex
from eduagent.services.learning import LearningService
from eduagent.storage.sqlite import SQLiteRepository


def main() -> int:
    parser = argparse.ArgumentParser(description="DeepSeek 真实小规模验证，会产生模型 API 请求")
    parser.add_argument("--db", type=Path, default=Path("data/local/live-agent-smoke.sqlite3"))
    args = parser.parse_args()
    values = local_configuration()
    settings = AgentSettings.from_mapping(values)
    if not settings.enabled:
        print("Agent 未启用，请检查本地配置，不要在命令行传入密钥。")
        return 2
    data_dir = Path(values.get("EDUAGENT_DATA_DIR", "data"))
    catalog = Catalog.load(data_dir)
    index = CourseIndex(data_dir / "materials", set(catalog.knowledge))
    with SQLiteRepository(args.db) as repository:
        service = LearningService(catalog, repository)
        student_id = "live-demo-" + uuid4().hex[:8]
        service.register(student_id, ("gradient_descent",))
        result = Tutor(service, index, DeepSeekClient(settings), settings).run(
            student_id, "请先读取我的学习状态，检索资料解释梯度下降为什么沿负梯度方向更新，并给出下一道合适的练习。",
        )
        print(json.dumps({
            "run_id": result["run_id"], "mode": result["mode"], "model": result["model"],
            "model_calls": result["model_calls"], "usage": result["usage"],
            "tools_used": result["tools_used"],
            "citation_ids": [item["citation_id"] for item in result["citations"]],
            "fallback_reason": result["fallback_reason"],
            "next_action": (result["next_exercise"] or {}).get("action"),
            "answer_preview": result["answer"][:250],
        }, ensure_ascii=True))
        return 0 if result["mode"] == "deepseek" else 2


if __name__ == "__main__":
    raise SystemExit(main())
