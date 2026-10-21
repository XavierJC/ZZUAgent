from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sqlite3

from fastapi.testclient import TestClient
import pytest

from eduagent.api.app import create_app
from eduagent.api.settings import APISettings
from eduagent.domain.bkt import BKTParameters
from eduagent.services.learning import LearningService
from eduagent.storage.sqlite import SQLiteRepository


@pytest.fixture
def api_settings(data_dir, tmp_path):
    return APISettings(data_dir=data_dir, db_path=tmp_path / "api.sqlite3")


@pytest.fixture
def client(api_settings):
    with TestClient(create_app(api_settings)) as result:
        yield result


def start(client, student="api-student", goals=None):
    payload = {"student_id": student}
    if goals is not None:
        payload["goals"] = goals
    response = client.post("/api/v1/students", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def next_question(client, student="api-student"):
    response = client.post(f"/api/v1/students/{student}/next")
    assert response.status_code == 200, response.text
    return response.json()


def submit(client, decision, answer="B", event_id="event-1", student="api-student"):
    return client.post(f"/api/v1/students/{student}/answers", json={
        "decision_id": decision["decision_id"], "event_id": event_id, "answer": answer,
    })


def test_health_and_course_metadata_do_not_publish_answer_bank(client):
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok", "version": "0.4.1", "mode": "offline_rules",
                             "question_count": 10, "pending_review_count": 10,
                             "agent_enabled": False, "retrieval_available": True}
    points = client.get("/api/v1/knowledge-points")
    assert points.status_code == 200 and len(points.json()) == 5
    assert all(set(point) == {"id", "name", "prerequisites", "review_tip"} for point in points.json())
    assert client.get("/api/v1/questions").status_code == 404


def test_openapi_documents_http_learning_contract(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert "/api/v1/students/{student_id}/answers" in schema["paths"]
    public_fields = schema["components"]["schemas"]["PublicQuestion"]["properties"]
    assert "answer" not in public_fields and "explanation" not in public_fields
    assert client.get("/docs").status_code == 200


def test_create_restore_and_mastery_snapshot(client):
    original = start(client, goals=["logistic_regression"])
    assert original["goals"] == ["logistic_regression"]
    assert original["revision"] == 0 and original["mode"] == "offline_rules"
    assert all(item["attempts"] == 0 and not item["has_evidence"] for item in original["mastery"])
    assert start(client) == original
    assert client.get("/api/v1/students/api-student/mastery").json() == original


@pytest.mark.parametrize("goals,status", [([], 422), (["unknown"], 422), (["model_evaluation"], 409)])
def test_invalid_or_conflicting_goals_rejected(client, goals, status):
    start(client, goals=["logistic_regression"])
    response = client.post("/api/v1/students", json={"student_id": "api-student", "goals": goals})
    assert response.status_code == status
    if status == 409:
        assert response.json()["error"]["code"] == "goal_conflict"
    assert client.get("/api/v1/students/api-student/mastery").json()["goals"] == ["logistic_regression"]


@pytest.mark.parametrize("payload", [
    {"student_id": 1}, {"student_id": " "}, {"student_id": " valid"},
    {"student_id": "x", "mastery": 1}, {"student_id": "x", "goals": "logistic_regression"},
])
def test_strict_request_validation(client, payload):
    response = client.post("/api/v1/students", json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert all("input" not in item for item in response.json()["error"]["details"])


@pytest.mark.parametrize("method,path,body", [
    ("get", "/mastery", None), ("post", "/next", None),
    ("post", "/answers", {"decision_id": "none", "event_id": "none", "answer": "A"}),
])
def test_missing_student_has_404(client, method, path, body):
    kwargs = {"json": body} if body is not None else {}
    response = client.request(method, "/api/v1/students/missing" + path, **kwargs)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "student_not_found"


def test_answer_only_available_after_graded_submission(client):
    start(client, goals=["logistic_regression"])
    decision = next_question(client)
    assert decision["question"]["id"] == "lr_01"
    assert "answer" not in decision["question"] and "explanation" not in decision["question"]
    assert next_question(client) == decision
    graded = submit(client, decision, " b ")
    assert graded.status_code == 200
    result = graded.json()
    assert result["correct"] and result["correct_answer"] == "B" and result["explanation"]
    assert result["prior"] == 0.2
    assert result["posterior"] == pytest.approx(9 / 19)
    assert result["next_mastery"] == pytest.approx(10 / 19)
    snapshot = client.get("/api/v1/students/api-student/mastery").json()
    assert snapshot["revision"] == 1
    linear = next(item for item in snapshot["mastery"] if item["knowledge_id"] == "linear_regression_loss")
    assert linear["has_evidence"] and linear["attempts"] == 1


@pytest.mark.parametrize("changes", [{"answer": "E"}, {"answer": True}, {"correct": True}, {"next_mastery": 1.0}])
def test_invalid_or_forged_answer_does_not_change_state(client, changes):
    start(client)
    decision = next_question(client)
    body = {"decision_id": decision["decision_id"], "event_id": "bad-event", "answer": "B", **changes}
    response = client.post("/api/v1/students/api-student/answers", json=body)
    assert response.status_code == 422
    assert client.get("/api/v1/students/api-student/mastery").json()["revision"] == 0
    assert submit(client, decision, event_id="bad-event").status_code == 200


def test_http_idempotency_and_conflicting_retry(client):
    start(client)
    decision = next_question(client)
    original = submit(client, decision).json()
    retry = submit(client, decision).json()
    assert retry["replayed"] is True
    assert retry | {"replayed": False} == original
    assert submit(client, decision, answer="A").status_code == 409
    assert submit(client, decision, event_id="different-event").status_code == 409
    assert client.get("/api/v1/students/api-student/mastery").json()["revision"] == 1


def test_concurrent_next_and_submit_are_idempotent(client):
    start(client)
    with ThreadPoolExecutor(max_workers=4) as pool:
        decisions = list(pool.map(lambda _: next_question(client), range(4)))
    assert len({item["decision_id"] for item in decisions}) == 1
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: submit(client, decisions[0]), range(2)))
    assert [response.status_code for response in responses] == [200, 200]
    assert sorted(response.json()["replayed"] for response in responses) == [False, True]
    assert client.get("/api/v1/students/api-student/mastery").json()["revision"] == 1


def test_cross_student_submission_cannot_return_other_students_answer(client):
    start(client, "alice")
    start(client, "bob")
    decision = next_question(client, "alice")
    response = submit(client, decision, student="bob")
    assert response.status_code == 409
    assert "correct_answer" not in response.json()
    assert client.get("/api/v1/students/bob/mastery").json()["revision"] == 0


def test_wrong_answers_review_then_stop_without_reusing_questions(client):
    start(client, goals=["logistic_regression"])
    first = next_question(client)
    assert submit(client, first, answer="A").status_code == 200
    second = next_question(client)
    assert second["action"] == "review" and second["knowledge_id"] == "linear_regression_loss"
    assert submit(client, second, answer="C", event_id="event-2").status_code == 200
    stopped = next_question(client)
    assert stopped["stop_reason"] == "insufficient_questions" and stopped["question"] is None


def test_full_http_five_topic_loop(client, catalog):
    start(client)
    for index in range(10):
        decision = next_question(client)
        answer = catalog.questions[decision["question"]["id"]].answer
        assert submit(client, decision, answer=answer, event_id=f"event-{index}").status_code == 200
    assert next_question(client)["action"] == "finish"
    snapshot = client.get("/api/v1/students/api-student/mastery").json()
    assert snapshot["revision"] == 10
    assert all(item["probability"] == pytest.approx(0.82) and item["attempts"] == 2
               for item in snapshot["mastery"])


def test_api_restart_restores_state_and_question_assignment(api_settings):
    with TestClient(create_app(api_settings)) as client:
        start(client, goals=["logistic_regression"])
        assert submit(client, next_question(client)).status_code == 200
        snapshot = client.get("/api/v1/students/api-student/mastery").json()
        pending = next_question(client)
    with TestClient(create_app(api_settings)) as client:
        assert start(client) == snapshot
        assert next_question(client) == pending


def test_database_failure_returns_503_and_rolls_back(client, api_settings):
    start(client)
    decision = next_question(client)
    with sqlite3.connect(api_settings.db_path) as connection:
        connection.execute("""CREATE TRIGGER fail_mastery BEFORE INSERT ON mastery
                              BEGIN SELECT RAISE(ABORT, 'injected-db-error'); END""")
    response = submit(client, decision)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "storage_unavailable"
    assert "injected-db-error" not in response.text
    with sqlite3.connect(api_settings.db_path) as connection:
        assert connection.execute("SELECT count(*) FROM attempts").fetchone()[0] == 0
        connection.execute("DROP TRIGGER fail_mastery")
    assert submit(client, decision).status_code == 200


def test_bad_historical_configuration_fails_at_startup(api_settings, catalog):
    with SQLiteRepository(api_settings.db_path) as repository:
        LearningService(catalog, repository, parameters=BKTParameters(initial=0.3))
    with pytest.raises(ValueError, match="不能静默混用"):
        with TestClient(create_app(api_settings)):
            pytest.fail("不一致配置不能启动")


def test_api_settings_from_environment(monkeypatch, data_dir, tmp_path):
    monkeypatch.setenv("EDUAGENT_DATA_DIR", str(data_dir))
    monkeypatch.setenv("EDUAGENT_DB_PATH", str(tmp_path / "env.sqlite3"))
    monkeypatch.setenv("EDUAGENT_AGENT_ENABLED", "false")
    settings = APISettings.from_environment()
    assert settings.data_dir == data_dir.resolve()
    with TestClient(create_app()) as client:
        assert client.get("/health").status_code == 200
    monkeypatch.setenv("EDUAGENT_DB_PATH", "")
    with pytest.raises(ValueError, match="不能为空"):
        APISettings.from_environment()


def test_api_cannot_use_separate_in_memory_connections():
    with pytest.raises(ValueError, match="文件数据库"):
        APISettings(db_path=Path(":memory:"))
