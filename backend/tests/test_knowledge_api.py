from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from eduagent.api.app import create_app
from eduagent.api.settings import APISettings
from eduagent.services.note_index import NoteIndexer
from eduagent.storage.personal import PersonalRepository
from eduagent.storage.sqlite import SQLiteRepository


@pytest.fixture
def configured(data_dir, tmp_path):
    return APISettings(data_dir=data_dir, db_path=tmp_path / 'no-model.sqlite3')


def create(client, text='星河定理 starunique 说明梯度下降的方向。'):
    response = client.post('/api/v1/students/a/notes', json={
        'id': str(uuid4()), 'title': '合成笔记', 'content_md': text, 'knowledge_point_ids': ['gradient_descent']})
    assert response.status_code == 201, response.text
    return response.json()


def source(client, identifier):
    items = client.get('/api/v1/students/a/knowledge/sources').json()['items']
    value = next(item for item in items if item['source_id'] == identifier)
    return {key: value[key] for key in ('source_type', 'source_id', 'source_version')}


def search(client, sources, query='starunique', student='a'):
    return client.post(f'/api/v1/students/{student}/knowledge/search', json={'query': query, 'sources': sources})


def test_without_model_key_lifecycle_source_selection_and_restart(configured, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Phase3A must never call a model')
    monkeypatch.setattr('eduagent.agent.deepseek.DeepSeekClient', forbidden)
    assert not configured.agent.api_key and not configured.agent.enabled
    with TestClient(create_app(configured)) as client:
        for student in ('a', 'b'):
            client.post('/api/v1/students', json={'student_id': student})
        assert client.get('/health').json()['retrieval_available'] is True
        assert client.post('/api/v1/materials/search', json={'query': '梯度下降'}).json()
        assert client.post('/api/v1/students/a/tutor', json={'question': '解释梯度下降'}).status_code == 503
        before = client.get('/api/v1/students/a/mastery').json()
        note = create(client)
        original = source(client, note['id'])
        result = search(client, [original]).json()
        citation = result['items'][0]
        assert result['model_calls'] == 0 and citation['raw_md'] == note['content_md']
        assert citation['source_revision'] == 1 and citation['start_line'] == 1
        assert search(client, [original], student='b').status_code == 404
        assert note['id'] not in client.get('/api/v1/students/b/knowledge/sources').text
        gradient = source(client, 'gradient')
        assert not search(client, [gradient]).json()['items']
        updated = client.patch(f"/api/v1/students/a/notes/{note['id']}", json={
            'expected_revision': 1, 'content_md': '月海理论 moonunique 采用新步长。'}).json()
        assert search(client, [original]).status_code == 409
        current = source(client, note['id'])
        assert not search(client, [current]).json()['items']
        assert search(client, [current], 'moonunique').json()['items'][0]['source_revision'] == 2
        assert client.get('/api/v1/students/a/mastery').json() == before
        assert not client.get('/api/v1/students/a/history').json()['items']
    # New application lifecycle / connections: no in-memory index is required.
    with TestClient(create_app(configured)) as reopened:
        assert search(reopened, [current], 'moonunique').json()['items']
        assert reopened.post(f"/api/v1/students/a/notes/{note['id']}/reindex", json={'expected_revision': 1}).status_code == 409
        assert reopened.post(f"/api/v1/students/a/notes/{note['id']}/reindex", json={'expected_revision': 2}).json()['status'] == 'ready'
        assert reopened.delete(f"/api/v1/students/a/notes/{note['id']}?expected_revision=2").status_code == 204
        assert search(reopened, [current], 'moonunique').status_code == 404
        assert not any(s['source_type'] == 'personal_note' for s in reopened.get('/api/v1/students/a/knowledge/sources').json()['items'])


@pytest.mark.parametrize('body', [
    {'query': '梯度', 'sources': []}, {'query': '梯度'},
    {'query': '梯度', 'sources': [{'source_type': 'other', 'source_id': 'gradient', 'source_version': 'x'}]},
    {'query': '梯度', 'sources': [], 'student_id': 'b'},
    {'query': '梯度', 'sources': [], 'top_k': True},
    {'query': '梯度', 'sources': [], 'course_id': 'other'},
])
def test_invalid_source_requests_do_not_expand_scope(configured, body):
    with TestClient(create_app(configured)) as client:
        client.post('/api/v1/students', json={'student_id': 'a'})
        assert client.post('/api/v1/students/a/knowledge/search', json=body).status_code == 422


def test_failed_index_and_incomplete_data_are_explicit_and_retryable(configured, monkeypatch):
    with TestClient(create_app(configured)) as client:
        client.post('/api/v1/students', json={'student_id': 'a'})
        # A failed parser does not undo the independent Markdown save.
        from eduagent.services import notes as notes_module
        original = notes_module.NoteIndexer
        def broken(repository):
            def fail(_):
                raise RuntimeError('sensitive data')
            return original(repository, fail)
        monkeypatch.setattr(notes_module, 'NoteIndexer', broken)
        note = create(client)
        assert note['index_status'] == 'failed'
        ref = source(client, note['id'])
        assert search(client, [ref]).status_code == 503
        assert client.get(f"/api/v1/students/a/notes/{note['id']}").json()['content_md'] == note['content_md']
        assert 'sensitive' not in client.get('/api/v1/students/a/knowledge/sources').text
        assert client.post(f"/api/v1/students/b/notes/{note['id']}/reindex", json={'expected_revision': 1}).status_code == 404
        assert client.post(f"/api/v1/students/a/notes/{note['id']}/reindex", json={'expected_revision': 1}).json()['status'] == 'ready'
        with SQLiteRepository(configured.db_path) as repository:
            repository.connection.execute('DELETE FROM note_chunks WHERE note_id=?', (note['id'],))
        assert search(client, [ref]).status_code == 503
        assert client.post(f"/api/v1/students/a/notes/{note['id']}/reindex", json={'expected_revision': 1}).json()['status'] == 'ready'
        assert search(client, [ref]).json()['items']


def test_retrieval_flag_is_independent_from_model_config(configured, monkeypatch):
    from dataclasses import replace
    monkeypatch.setattr('eduagent.api.settings.local_configuration', lambda: {'EDUAGENT_RETRIEVAL_ENABLED': 'true'})
    parsed = APISettings.from_environment()
    assert parsed.retrieval_enabled and not parsed.agent.enabled and not parsed.agent.api_key
    monkeypatch.setattr('eduagent.api.settings.local_configuration', lambda: {'EDUAGENT_RETRIEVAL_ENABLED': 'invalid'})
    with pytest.raises(ValueError):
        APISettings.from_environment()
    with TestClient(create_app(replace(configured, retrieval_enabled=False))) as client:
        client.post('/api/v1/students', json={'student_id': 'a'})
        note = create(client)
        assert client.post('/api/v1/materials/search', json={'query': '梯度'}).status_code == 503
        assert search(client, [source(client, note['id'])]).status_code == 503


def test_search_body_limit_and_source_versions_are_checked(configured):
    with TestClient(create_app(configured)) as client:
        client.post('/api/v1/students', json={'student_id': 'a'})
        course = source(client, 'gradient')
        assert search(client, [{**course, 'source_version': 'old'}], '梯度下降').status_code == 409
        assert search(client, [course, course], '梯度下降').status_code == 422
        assert search(client, [{**course, 'source_id': 'unknown'}], '梯度下降').status_code == 404
        assert client.post('/api/v1/students/a/knowledge/search', content=b'x' * 262145).status_code == 413
