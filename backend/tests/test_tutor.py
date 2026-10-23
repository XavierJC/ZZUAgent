import json
import sqlite3

from fastapi.testclient import TestClient
import pytest

from eduagent.agent.deepseek import ModelError, ModelReply
from eduagent.agent.settings import AgentSettings
from eduagent.agent.tutor import Tutor
from eduagent.api.app import create_app
from eduagent.api.settings import APISettings
from eduagent.retrieval.index import CourseIndex
from eduagent.storage.sqlite import SQLiteRepository


@pytest.fixture
def course_index(data_dir, catalog):
    return CourseIndex(data_dir / "materials", set(catalog.knowledge))


def tool_reply(calls=None):
    calls = calls if calls is not None else [
        ("get_learning_state", {}),
        ("retrieve_course_material", {"query": "梯度下降参数更新负梯度", "knowledge_id": "gradient_descent"}),
        ("get_next_exercise", {}),
    ]
    return ModelReply({"role": "assistant", "content": None, "tool_calls": [
        {"id": f"call-{i}", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}
        for i, (name, args) in enumerate(calls)
    ]}, 10, 5)


class FakeModel:
    def __init__(self, *, error=None, invalid_citation=False, loop=False, mutate=None):
        self.calls = 0
        self.error, self.invalid_citation, self.loop, self.mutate = error, invalid_citation, loop, mutate
        self.received = []

    def complete(self, messages, tools, required=False):
        self.calls += 1
        self.received.append(messages)
        if self.error:
            raise ModelError(self.error)
        if self.calls == 1 or self.loop:
            return tool_reply()
        if self.mutate:
            self.mutate()
        citation_id = "gradient:1" if not self.invalid_citation else "invented:99"
        return ModelReply({"role": "assistant", "content": json.dumps({
            "answer": f"自建草稿指出，参数沿负梯度方向更新 [{citation_id}]。",
            "citation_ids": [citation_id],
        }, ensure_ascii=False)}, 20, 10)


def tutor(service, course_index, model, **kwargs):
    return Tutor(service, course_index, model, AgentSettings(enabled=True, api_key="test-only-secret", **kwargs))


def test_graph_executes_tools_and_returns_traceable_answer_without_grading(service, course_index):
    model = FakeModel()
    before = service.status("student-a")
    result = tutor(service, course_index, model).run("student-a", "请解释梯度下降")
    assert result["mode"] == "deepseek" and result["model_calls"] == 2
    assert result["citations"][0]["citation_id"] == "gradient:1"
    assert [t["name"] for t in result["tools_used"]] == [
        "get_learning_state", "retrieve_course_material", "get_next_exercise",
    ]
    assert result["next_exercise"]["knowledge_id"] == "linear_regression_loss"
    assert "answer" not in result["next_exercise"]["question"]
    assert service.status("student-a") == before
    assert service.repository.tutor_run("student-a", result["run_id"]) == result
    assert "test-only-secret" not in json.dumps(model.received)
    assert "student-a" not in json.dumps(model.received)
    assert "两条样本的真实值" not in json.dumps(model.received, ensure_ascii=False)
    assert "test-only-secret" not in json.dumps(result)


@pytest.mark.parametrize("code", ["authentication_failed", "model_timeout", "insufficient_balance", "network_error"])
def test_upstream_errors_fall_back_explicitly_without_learning_update(service, course_index, code):
    result = tutor(service, course_index, FakeModel(error=code)).run("student-a", "梯度下降更新方向")
    assert result["mode"] == "offline_fallback" and result["fallback_reason"] == code
    assert result["model_calls"] == 1
    assert all(s.attempts == 0 for s in service.status("student-a").values())
    assert result["citations"]


def test_invented_citation_cannot_pass_as_verified_model_answer(service, course_index):
    result = tutor(service, course_index, FakeModel(invalid_citation=True)).run("student-a", "梯度下降")
    assert result["mode"] == "offline_fallback"
    assert result["fallback_reason"] == "unverified_model_answer"
    assert "invented:99" not in result["answer"]


def test_model_loop_has_call_budget(service, course_index):
    model = FakeModel(loop=True)
    result = tutor(service, course_index, model, max_calls=2).run("student-a", "梯度下降")
    assert model.calls == 2
    assert result["fallback_reason"] == "model_call_limit"


def test_state_change_during_generation_discards_stale_advice(service, course_index):
    def mutate():
        decision = service.next_action("student-a")
        service.submit("student-a", decision.decision_id, "B", "during-generation")
    result = tutor(service, course_index, FakeModel(mutate=mutate)).run("student-a", "梯度下降")
    assert result["fallback_reason"] == "learning_state_changed"
    assert result["state_revision"] == 1 and result["next_exercise"]["revision"] == 1


def test_extra_tool_identity_arguments_are_rejected(service, course_index):
    class InvalidTools(FakeModel):
        def complete(self, messages, tools, required=False):
            self.calls += 1
            return tool_reply([("get_learning_state", {"student_id": "another-student"})])
    result = tutor(service, course_index, InvalidTools(), max_calls=2).run("student-a", "梯度下降")
    assert result["tools_used"][0]["status"] == "invalid"
    assert all(s.attempts == 0 for s in service.status("student-a").values())


def test_no_evidence_produces_clear_local_response(service, course_index):
    result = tutor(service, course_index, FakeModel(error="network_error")).run("student-a", "qzzxxyyunknown")
    assert result["citations"] == []
    assert "没有找到足够依据" in result["answer"]


def test_tutor_reads_updated_bkt_after_an_answer_and_assigns_review(service, course_index):
    decision = service.next_action("student-a")
    service.submit("student-a", decision.decision_id, "A", "before-tutoring")
    model = FakeModel()
    result = tutor(service, course_index, model).run("student-a", "请结合我的学情解释梯度下降")
    assert result["mode"] == "deepseek" and result["state_revision"] == 1
    assert result["next_exercise"]["action"] == "review"
    assert result["next_exercise"]["question"]["id"] == "lr_02"
    tool_outputs = [json.loads(m["content"]) for m in model.received[-1] if m["role"] == "tool"]
    observed = next(item for item in tool_outputs if "mastery" in item)
    linear = next(item for item in observed["mastery"] if item["knowledge_id"] == "linear_regression_loss")
    assert linear["probability"] == pytest.approx(4 / 31)
    assert linear["attempts"] == 1 and linear["last_correct"] is False


def test_new_table_migrates_v1_without_losing_history(catalog, tmp_path):
    from eduagent.services.learning import LearningService

    path = tmp_path / "migration.sqlite3"
    with SQLiteRepository(path) as repository:
        service = LearningService(catalog, repository)
        service.register("existing-student", ("logistic_regression",))
        decision = service.next_action("existing-student")
        receipt = service.submit("existing-student", decision.decision_id, "B", "historical-answer")
        expected = service.snapshot("existing-student")
        # Strip later extensions from this temporary fixture to reproduce v1.
        from eduagent.storage.migrations import DOCUMENT_TABLES, ARCHITECTURE_TABLES, BANK_TABLES, EXTRACTION_TABLES, RELEASE_TABLES
        for table in reversed(DOCUMENT_TABLES + ARCHITECTURE_TABLES + BANK_TABLES + EXTRACTION_TABLES + RELEASE_TABLES):
            repository.connection.execute(f'DROP TABLE {table}')
        for table in ("study_guide_runs", "self_assessment_entries", "self_assessment_batches", "workbench_note_origins", "workbench_runs", "note_chunks", "note_index_state", "note_knowledge_points", "notes"):
            repository.connection.execute(f"DROP TABLE {table}")
        repository.connection.execute("DROP TABLE tutor_runs")
        repository.connection.execute("PRAGMA user_version=1")
    with SQLiteRepository(path) as repository:
        assert repository.connection.execute("PRAGMA user_version").fetchone()[0] == 11
        restored = LearningService(catalog, repository)
        assert restored.snapshot("existing-student") == expected
        assert repository.attempt("historical-answer") == receipt


def test_agent_api_uses_bound_student_and_persists_only_their_run(data_dir, tmp_path, monkeypatch):
    model = FakeModel()
    monkeypatch.setattr("eduagent.agent.deepseek.DeepSeekClient", lambda settings: model)
    settings = APISettings(data_dir, tmp_path / "agent-api.sqlite3",
                           AgentSettings(enabled=True, api_key="test-only-secret"))
    with TestClient(create_app(settings)) as client:
        assert client.get("/health").json()["agent_enabled"] is True
        for student in ("alice", "bob"):
            assert client.post("/api/v1/students", json={"student_id": student}).status_code == 200
        search = client.post("/api/v1/materials/search", json={"query": "梯度下降"})
        assert search.status_code == 200 and search.json()
        response = client.post("/api/v1/students/alice/tutor", json={"question": "请解释梯度下降"})
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["mode"] == "deepseek"
        assert client.get(f"/api/v1/students/alice/tutor-runs/{result['run_id']}").json() == result
        assert client.get(f"/api/v1/students/bob/tutor-runs/{result['run_id']}").status_code == 404
        assert "test-only-secret" not in response.text


def test_agent_disabled_api_remains_usable(data_dir, tmp_path):
    settings = APISettings(data_dir, tmp_path / "disabled.sqlite3")
    with TestClient(create_app(settings)) as client:
        assert client.get("/health").status_code == 200
        assert client.post("/api/v1/students/alice/tutor", json={"question": "梯度下降"}).status_code == 503
