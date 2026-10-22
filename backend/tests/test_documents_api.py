"""Actual local parse subprocesses through isolated API storage."""

import json
import time
from uuid import uuid4
from fastapi.testclient import TestClient
import pytest

from eduagent.api.app import create_app
from eduagent.api.settings import APISettings
from document_fixtures import pdf_bytes, pptx_bytes


@pytest.fixture
def document_client(tmp_path, data_dir):
    settings = APISettings(data_dir=data_dir, db_path=tmp_path / 'api.sqlite3')
    with TestClient(create_app(settings)) as client:
        for student in ('doc-a', 'doc-b'): assert client.post('/api/v1/students', json={'student_id': student}).status_code == 200
        yield client, settings


def upload(client, raw, name, **changes):
    meta = dict(request_id=str(uuid4()), title='合成课件', local_rights_confirmed=True)
    meta.update(changes)
    return client.post('/api/v1/students/doc-a/documents', files={'file': (name, raw)}, data={'metadata': json.dumps(meta)})


def wait(client, key):
    path = '/api/v1/students/doc-a/documents/' + key
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        response = client.get(path); assert response.status_code == 200
        if response.json()['parse']['status'] not in ('pending', 'processing'): return response.json()
        time.sleep(.05)
    pytest.fail('isolated local parser did not finish')


@pytest.mark.parametrize('name,raw,expected', [('course.md', '# 笔记\n\n$w$ 学习率'.encode(), '学习率'),
    ('course.txt', '模型评估'.encode(), '模型评估'), ('course.pdf', pdf_bytes(('主成分分析',)), '主成分分析'),
    ('course.pptx', pptx_bytes(), '主要变化方向')], ids=['markdown','text','pdf','pptx'])
def test_upload_parse_units_download_and_scope(document_client, name, raw, expected):
    client, settings = document_client
    before = client.get('/api/v1/students/doc-a/mastery').json()
    response = upload(client, raw, name)
    assert response.status_code == 202, response.text
    doc = wait(client, response.json()['id']); base = '/api/v1/students/doc-a/documents/' + doc['id']
    assert doc['parse']['status'] in ('ready', 'partial'), doc['parse']
    values = client.get(base + '/units').json()
    assert expected in ' '.join(u['text'] for u in values['items'])
    downloaded = client.get(base + '/original')
    assert downloaded.content == raw and downloaded.headers['x-content-type-options'] == 'nosniff'
    assert 'attachment' in downloaded.headers['content-disposition']
    for suffix in ('', '/units', '/versions', '/original', '/parse-runs'):
        denied = client.get(base.replace('/doc-a/', '/doc-b/') + suffix)
        assert denied.status_code == 404 and expected not in denied.text
    assert client.get('/api/v1/students/doc-a/mastery').json() == before
    assert not any('storage_key' in value for value in client.get(base + '/versions').json())


@pytest.mark.parametrize('name,raw,status', [('bad.exe', b'x', 415), ('fake.pdf', b'not pdf', 422),
    ('bad.txt', b'\xff', 422), ('../bad.md', b'text', 422), ('big.md', b'x' * (2*1024*1024+1), 413)],
    ids=['extension', 'signature', 'encoding', 'filename', 'text_size'])
def test_upload_rejects_bad_format_names_encoding_and_size(document_client, name, raw, status):
    client, _ = document_client
    assert upload(client, raw, name).status_code == status
    assert client.get('/api/v1/students/doc-a/documents').json()['items'] == []


def test_rights_fields_streaming_limits_and_disabled_vision(document_client):
    client, settings = document_client
    for rights in (False, 1, 'true'):
        response = client.post('/api/v1/students/doc-a/documents', files={'file': ('x.md', b'text')},
            data={'metadata': json.dumps(dict(request_id=str(uuid4()), title='test', local_rights_confirmed=rights))})
        assert response.status_code == 422
    too_big = client.post('/api/v1/students/doc-a/documents', content=b'x', headers={'content-length': str(21*1024*1024)})
    assert too_big.status_code == 413
    doc = wait(client, upload(client, pdf_bytes(), 'test.pdf').json()['id'])
    body = dict(request_id=str(uuid4()), expected_revision=doc['revision'], version_id=doc['version']['id'], pages=[1], consent_external=True)
    assert client.post(f"/api/v1/students/doc-a/documents/{doc['id']}/vision", json=body).status_code == 503
    assert client.get('/api/v1/students/doc-a/documents/capabilities').json()['vision_enabled'] is False


def test_stream_without_content_length_is_bounded_and_extra_fields_are_rejected(document_client):
    client, settings = document_client
    def chunks():
        yield b'--boundary\r\nContent-Disposition: form-data; name="file"; filename="x.pdf"\r\n\r\n'
        for _ in range(22): yield b'x' * (1024 * 1024)
        yield b'\r\n--boundary--\r\n'
    response = client.post('/api/v1/students/doc-a/documents', content=chunks(),
                           headers={'content-type': 'multipart/form-data; boundary=boundary'})
    assert response.status_code == 413
    response = client.post('/api/v1/students/doc-a/documents', files={'file': ('x.md', b'text')},
                          data={'metadata': '{}', 'unexpected': 'no'})
    assert response.status_code == 400
    assert not list(settings.document_dir.glob('staging/*'))
