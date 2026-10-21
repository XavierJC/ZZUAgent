"""Phase-one CLI; --demo uses answer keys as explicitly synthetic input."""

import argparse
from pathlib import Path
import sqlite3
from uuid import uuid4

from eduagent.agent.policy import RulePolicy
from eduagent.domain.catalog import Catalog
from eduagent.services.learning import LearningService
from eduagent.storage.sqlite import SQLiteRepository


def show_status(service: LearningService, student_id: str) -> None:
    print("\n学习状态（BKT 演示参数，未经真实数据校准）：")
    for key, state in service.status(student_id).items():
        evidence = f"已答 {state.attempts} 题" if state.attempts else "尚无答题证据，显示先验"
        print(f"  {service.catalog.knowledge[key].name}: {state.probability:.2%}，{evidence}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="EduAgent 第一阶段：离线规则学习闭环")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--db", type=Path, default=Path("data/local/eduagent.sqlite3"))
    parser.add_argument("--student", default="demo")
    parser.add_argument("--goal", action="append", help="知识点 ID，可重复指定；恢复时省略")
    parser.add_argument("--max-rounds", type=int, default=20, help="每名演示学生累计答题上限，重启不清零")
    parser.add_argument("--demo", action="store_true", help="自动提交标准答案，使用合成数据验证流程")
    parser.add_argument("--status", action="store_true", help="仅查看保存的学习状态")
    args = parser.parse_args(argv)
    try:
        catalog = Catalog.load(args.data_dir)
        with SQLiteRepository(args.db) as repository:
            service = LearningService(catalog, repository, policy=RulePolicy(max_rounds=args.max_rounds))
            service.register(args.student, tuple(args.goal) if args.goal else None)
            print("EduAgent | offline_rules | 离线规则模式，无真实模型调用")
            print(f"学生标识: {args.student} | 数据库: {args.db.resolve()}")
            if args.demo:
                print("合成演示：自动使用题库标准答案，仅验证工程流程，不代表学习效果。")
            pending = sum(q.review_status == "pending" for q in catalog.questions.values())
            print(f"题库 {len(catalog.questions)} 题，其中 {pending} 题待人工校验。")
            if args.status:
                show_status(service, args.student)
                return 0
            while True:
                decision = service.next_action(args.student)
                print(f"\n[{decision.action}] {decision.reason}")
                if decision.question is None:
                    if decision.stop_reason:
                        print(f"停止原因: {decision.stop_reason}")
                    break
                question = decision.question
                print(f"{question['id']} ({question['difficulty']}): {question['stem']}")
                for option, text in question["options"].items():
                    print(f"  {option}. {text}")
                if args.demo:
                    answer = catalog.questions[question["id"]].answer
                    print(f"合成提交: {answer}")
                else:
                    try:
                        answer = input("答案 A/B/C/D（q 保存并退出）: ")
                    except EOFError:
                        break
                    if answer.strip().lower() == "q":
                        break
                try:
                    result = service.submit(args.student, decision.decision_id, answer, str(uuid4()))
                except ValueError as exc:
                    print(f"提交未计入记录: {exc}")
                    continue
                print(f"{'答对' if result.correct else '答错'}，正确选项 {result.correct_answer}。{result.explanation}")
                print(f"BKT: 观测前 {result.prior:.6f} → 后验 {result.posterior:.6f}"
                      f" → 学习转移后 {result.next_mastery:.6f}")
            show_status(service, args.student)
        return 0
    except (ValueError, OSError, sqlite3.Error) as exc:
        print(f"无法运行: {exc}")
        return 2
    except KeyboardInterrupt:
        print("\n已退出；已提交记录保存在数据库中。")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
