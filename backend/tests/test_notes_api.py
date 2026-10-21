import base64
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from eduagent.api.app import create_app
from eduagent.api.settings import APISettings


@pytest.fixture
def client(data_dir, tmp_path):
    with TestClient(create_app(APISettings(data_dir=data_dir, db_path=tmp_path / "notes.sqlite3"))) as result:
        for student in ("a", "b"):
            assert result.post("/api/v1/students", json={"student_id": student}).status_code == 200
        yield result


def body(**changes):
    return {"id": str(uuid4()), "title": "学习笔记", "content_md": "# MSE\n\n$L=x^2$",
            "knowledge_point_ids": ["gradient_descent", "linear_regression_loss"], **changes}


def test_real_http_note_lifecycle_is_scoped_versioned_and_does_not_touch_learning(client):
    prefix = "/api/v1/students/a/notes"
    before = client.get("/api/v1/students/a/mastery").json()
    data = body(content_md='<script>alert(1)</script>\n$L=x^2$')
    response = client.post(prefix, json=data)
    assert response.status_code == 201
    note = response.json()
    assert note["content_md"] == data["content_md"] and note["index_status"] == "ready"
    assert client.post(prefix, json=data).status_code == 200
    assert client.get(prefix).json()["total"] == 1
    assert "content_md" not in client.get(prefix).json()["items"][0]
    path = f"{prefix}/{note['id']}"
    other = f"/api/v1/students/b/notes/{note['id']}"
    assert client.get(other).status_code == 404
    assert client.patch(other, json={"expected_revision": 1, "title": "steal"}).status_code == 404
    assert client.delete(other + "?expected_revision=1").status_code == 404
    assert client.patch(path, json={"expected_revision": 1, "content_md": "**更新**"}).json()["revision"] == 2
    assert client.patch(path, json={"expected_revision": 1, "title": "stale"}).status_code == 409
    assert client.delete(path + "?expected_revision=1").status_code == 409
    assert client.delete(path + "?expected_revision=2").status_code == 204
    assert client.get(path).status_code == 404 and client.get(prefix).json()["total"] == 0
    assert client.post(prefix, json=data).status_code == 409
    assert client.get("/api/v1/students/a/mastery").json() == before
    assert client.get("/api/v1/students/a/history").json()["items"] == []


@pytest.mark.parametrize("changes", [{"content_html": "<b>x</b>"}, {"probability": 1}, {"revision": 9},
    {"knowledge_point_ids": ["unknown"]}, {"course_id": "other"}, {"title": " "}, {"id": "missing"}])
def test_invalid_fields_and_untrusted_values_are_rejected(client, changes):
    response = client.post("/api/v1/students/a/notes", json=body(**changes))
    assert response.status_code == 422 and client.get("/api/v1/students/a/notes").json()["total"] == 0


@pytest.mark.parametrize("change", [{"expected_revision": True, "title": "x"},
    {"expected_revision": 1}, {"expected_revision": 1, "content_md": None},
    {"expected_revision": 1, "content_hash": "fake"}])
def test_invalid_updates_are_not_applied(client, change):
    note = client.post("/api/v1/students/a/notes", json=body()).json()
    path = f"/api/v1/students/a/notes/{note['id']}"
    assert client.patch(path, json=change).status_code == 422
    assert client.get(path).json() == note


def test_size_limit_applies_before_json_and_without_content_length(client):
    prefix = "/api/v1/students/a/notes"
    assert client.post(prefix, json=body(content_md="x" * 65537)).status_code == 413
    assert client.post(prefix, json=body(content_md="中" * 22000)).status_code == 413
    def chunks():
        yield b'{"title":"'
        yield b'x' * 262144
        yield b'"}'
    assert client.post(prefix, content=chunks(), headers={"Content-Type": "application/json"}).status_code == 413
    assert client.get(prefix).json()["total"] == 0


def test_import_endpoint_and_missing_resources(client):
    data = {"id": str(uuid4()), "file_name": "复习.txt", "content_base64": base64.b64encode("复习 $w$".encode()).decode()}
    response = client.post("/api/v1/students/a/notes/import", json=data)
    assert response.status_code == 201 and response.json()["content_md"] == "复习 $w$"
    assert client.post("/api/v1/students/a/notes/import", json=data).status_code == 200
    assert client.post("/api/v1/students/a/notes/import", json={**data, "content_base64": "!?"}).status_code == 422
    assert client.post("/api/v1/students/missing/notes", json=body()).status_code == 404
    assert client.get(f"/api/v1/students/a/notes/{uuid4()}").status_code == 404
    assert client.get("/api/v1/students/a/notes?limit=51").status_code == 422
    assert client.get("/api/v1/students/a/notes?course_id=other").status_code == 422
