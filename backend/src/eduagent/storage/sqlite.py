"""Small SQLite repository; the learning service owns transaction boundaries."""

from contextlib import contextmanager
from dataclasses import asdict
import json
from pathlib import Path
import sqlite3
from typing import Iterator

from eduagent.domain.models import Mastery, Recommendation, SubmissionResult
from eduagent.storage.migrations import migrate


def encode(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


class SQLiteRepository:
    def __init__(self, path: str | Path):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(str(path), isolation_level=None, timeout=10)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        try:
            self.migration_report = migrate(self.connection, path)
        except BaseException:
            self.close()
            raise

    @contextmanager
    def transaction(self) -> Iterator[None]:
        # Serialize read/modify/write, including concurrent retries from another connection.
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.connection.execute("COMMIT")
        except BaseException:
            self.connection.execute("ROLLBACK")
            raise

    def bind_configuration(self, configuration: dict) -> None:
        value = encode(configuration)
        with self.transaction():
            row = self.connection.execute("SELECT value FROM metadata WHERE key='configuration'").fetchone()
            if row is None:
                self.connection.execute("INSERT INTO metadata VALUES ('configuration', ?)", (value,))
            elif row["value"] != value:
                raise ValueError("数据库配置与当前题库、BKT 或策略不一致；请使用新数据库，不能静默混用历史")

    def student(self, student_id: str) -> sqlite3.Row | None:
        return self.connection.execute("SELECT * FROM students WHERE id=?", (student_id,)).fetchone()

    def add_student(self, student_id: str, goals: tuple[str, ...], created_at: str) -> None:
        self.connection.execute(
            "INSERT INTO students (id, goals_json, created_at) VALUES (?, ?, ?)",
            (student_id, encode(goals), created_at),
        )

    def states(self, student_id: str) -> dict[str, Mastery]:
        rows = self.connection.execute("SELECT * FROM mastery WHERE student_id=?", (student_id,))
        return {row["knowledge_id"]: Mastery(row["knowledge_id"], row["probability"],
                row["attempts"], bool(row["last_correct"])) for row in rows}

    def answered_questions(self, student_id: str) -> set[str]:
        rows = self.connection.execute("SELECT question_id FROM attempts WHERE student_id=?", (student_id,))
        return {row[0] for row in rows}

    def decision_at(self, student_id: str, revision: int) -> Recommendation | None:
        row = self.connection.execute(
            "SELECT payload_json FROM decisions WHERE student_id=? AND revision=?", (student_id, revision),
        ).fetchone()
        return Recommendation(**json.loads(row[0])) if row else None

    def decision(self, decision_id: str) -> Recommendation | None:
        row = self.connection.execute("SELECT payload_json FROM decisions WHERE id=?", (decision_id,)).fetchone()
        return Recommendation(**json.loads(row[0])) if row else None

    def save_decision(self, decision: Recommendation, created_at: str) -> None:
        self.connection.execute(
            "INSERT INTO decisions VALUES (?, ?, ?, ?, ?)",
            (decision.decision_id, decision.student_id, decision.revision, encode(asdict(decision)), created_at),
        )

    def attempt(self, event_id: str) -> SubmissionResult | None:
        row = self.connection.execute("SELECT result_json FROM attempts WHERE event_id=?", (event_id,)).fetchone()
        return SubmissionResult(**json.loads(row[0])) if row else None

    def record_attempt(self, result: SubmissionResult, previous_attempts: int) -> None:
        self.connection.execute(
            """INSERT INTO attempts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (result.event_id, result.student_id, result.decision_id, result.question_id,
             result.knowledge_id, result.selected_answer, int(result.correct), result.prior,
             result.posterior, result.next_mastery, encode(asdict(result)), result.created_at),
        )
        self.connection.execute(
            """INSERT INTO mastery VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(student_id, knowledge_id) DO UPDATE SET
               probability=excluded.probability, attempts=excluded.attempts,
               last_correct=excluded.last_correct""",
            (result.student_id, result.knowledge_id, result.next_mastery,
             previous_attempts + 1, int(result.correct)),
        )
        self.connection.execute("UPDATE students SET revision=revision+1 WHERE id=?", (result.student_id,))

    def close(self) -> None:
        self.connection.close()

    def save_tutor_run(self, result: dict, created_at: str) -> None:
        self.connection.execute(
            "INSERT INTO tutor_runs VALUES (?, ?, ?, ?, ?, ?)",
            (result["run_id"], result["student_id"], result["state_revision"], result["mode"],
             encode(result), created_at),
        )

    def tutor_run(self, student_id: str, run_id: str) -> dict | None:
        row = self.connection.execute(
            "SELECT payload_json FROM tutor_runs WHERE id=? AND student_id=?", (run_id, student_id),
        ).fetchone()
        return json.loads(row[0]) if row else None

    def recent_attempts(self, student_id: str, limit: int) -> list[dict]:
        rows = self.connection.execute(
            """SELECT a.result_json FROM attempts a JOIN decisions d ON d.id=a.decision_id
               WHERE a.student_id=? ORDER BY d.revision DESC LIMIT ?""", (student_id, limit),
        )
        return [json.loads(row[0]) for row in rows]

    def recent_tutor_runs(self, student_id: str, limit: int) -> list[dict]:
        rows = self.connection.execute(
            """SELECT payload_json FROM tutor_runs WHERE student_id=?
               ORDER BY created_at DESC, id DESC LIMIT ?""", (student_id, limit),
        )
        return [json.loads(row[0]) for row in rows]

    def __enter__(self) -> "SQLiteRepository":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
