from fastapi.testclient import TestClient
import pytest

from eduagent.api.app import create_app
from eduagent.api.settings import APISettings
from eduagent.services.learning import LearningService
from eduagent.storage.sqlite import SQLiteRepository


@pytest.fixture
def web_settings(data_dir, tmp_path):
    return APISettings(data_dir=data_dir, db_path=tmp_path / "web.sqlite3", frontend_dir=tmp_path / "dist")


def test_answer_history_is_ordered_scoped_bounded_and_read_only(web_settings):
    with TestClient(create_app(web_settings)) as client:
        for student in ["a", "b"]:
            client.post("/api/v1/students", json={"student_id": student})
        assert client.get("/api/v1/students/a/history").json()["items"] == []
        receipts = []
        for answer in ["B", "A"]:
            decision = client.post("/api/v1/students/a/next").json()
            result = client.post("/api/v1/students/a/answers", json={
                "decision_id": decision["decision_id"], "event_id": f"event-{answer}", "answer": answer,
            })
            assert result.status_code == 200
            receipts.append(result.json())
        before = client.get("/api/v1/students/a/mastery").json()
        history = client.get("/api/v1/students/a/history").json()
        assert history == {"student_id": "a", "revision": 2, "items": list(reversed(receipts))}
        assert client.get("/api/v1/students/a/history?limit=1").json()["items"] == [receipts[-1]]
        assert client.get("/api/v1/students/b/history").json()["items"] == []
        assert client.get("/api/v1/students/missing/history").status_code == 404
        assert client.get("/api/v1/students/a/mastery").json() == before
    with TestClient(create_app(web_settings)) as restored:
        assert restored.get("/api/v1/students/a/history").json() == history


@pytest.mark.parametrize("path", ["history?limit=0", "history?limit=51", "tutor-runs?limit=0", "tutor-runs?limit=11"])
def test_history_limits_are_validated(web_settings, path):
    with TestClient(create_app(web_settings)) as client:
        assert client.get(f"/api/v1/students/a/{path}").status_code == 422


def test_saved_tutor_history_does_not_require_model_or_leak_other_student(web_settings, catalog):
    def record(identifier, student):
        return {"run_id": identifier, "student_id": student, "state_revision": 0,
                "mode": "offline_fallback", "model": None, "model_calls": 0, "usage": {},
                "answer": "Saved course feedback", "citations": [], "tools_used": [],
                "fallback_reason": "model_timeout", "next_exercise": None}
    with SQLiteRepository(web_settings.db_path) as repository:
        service = LearningService(catalog, repository)
        service.register("a"); service.register("b")
        for run_id, student, time in [("old", "a", "2026-10-19"), ("other", "b", "2026-10-21"), ("new", "a", "2026-10-20")]:
            repository.save_tutor_run(record(run_id, student), time)
    # Agent is disabled; a successful GET proves it only reads persisted rows.
    with TestClient(create_app(web_settings)) as client:
        response = client.get("/api/v1/students/a/tutor-runs")
        assert response.status_code == 200
        assert [item["run_id"] for item in response.json()] == ["new", "old"]
        assert len(client.get("/api/v1/students/a/tutor-runs?limit=1").json()) == 1
        assert [item["run_id"] for item in client.get("/api/v1/students/b/tutor-runs").json()] == ["other"]
        assert client.get("/api/v1/students/missing/tutor-runs").status_code == 404
        assert client.get("/api/v1/students/a/mastery").json()["revision"] == 0


def test_frontend_only_serves_compiled_index_and_asset_directory(web_settings):
    assets = web_settings.frontend_dir / "assets"
    assets.mkdir(parents=True)
    (web_settings.frontend_dir / "index.html").write_text("<html><body>EduAgent</body></html>", encoding="utf-8")
    (assets / "app.js").write_text("console.log('public asset')", encoding="utf-8")
    (web_settings.frontend_dir / ".env").write_text("PRIVATE=value", encoding="utf-8")
    with TestClient(create_app(web_settings)) as client:
        index = client.get("/")
        assert index.status_code == 200 and "text/html" in index.headers["content-type"]
        assert index.headers["cache-control"] == "no-store"
        assert client.get("/assets/app.js").status_code == 200
        for path in ["/.env", "/src/App.vue", "/data/questions.json", "/backend/pyproject.toml", "/assets/%2e%2e/.env"]:
            assert client.get(path).status_code == 404
        schema = client.get("/openapi.json").json()
    assert "/" not in schema["paths"] and len(schema["paths"]) == 88


def test_missing_frontend_build_keeps_api_available(web_settings):
    with TestClient(create_app(web_settings)) as client:
        assert client.get("/").json()["error"]["code"] == "frontend_not_built"
        assert client.get("/").status_code == 503
        assert client.get("/health").status_code == 200


@pytest.mark.parametrize("limit", [True, 0, 51])
def test_service_validates_history_limits(catalog, tmp_path, limit):
    with SQLiteRepository(tmp_path / "history.sqlite3") as repository:
        with pytest.raises(ValueError):
            LearningService(catalog, repository).history("a", limit)
