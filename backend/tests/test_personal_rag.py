import json
from hashlib import sha256
from threading import Barrier
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest

from eduagent.domain.notes import NoteConflict, NoteNotFound, NoteTooLarge
from eduagent.retrieval.note_chunks import chunk_markdown, blocks, ChunkingError
from eduagent.retrieval.index import CourseIndex
from eduagent.services.notes import NotesService
from eduagent.services.note_index import NoteIndexer
from eduagent.services.knowledge import KnowledgeService, CourseSources, SourceChanged, IndexUnavailable, note_version
from eduagent.storage.personal import PersonalRepository
from eduagent.storage.sqlite import SQLiteRepository
from eduagent.storage.migrations import fact_snapshot


def make_note(**overrides):
    raw = '# 学习笔记\n\n橙光算法使用归一化梯度控制学习率。\n'
    return {**dict(id=str(uuid4()), title='独立自建笔记', content_md=raw, knowledge_point_ids=['gradient_descent']), **overrides}


def ref(note):
    return dict(source_type='personal_note', source_id=note['id'], source_version=note_version(note))


@pytest.fixture
def workspace(service, data_dir):
    courses = CourseSources(CourseIndex(data_dir / 'materials', set(service.catalog.knowledge)), data_dir / 'materials')
    return NotesService(service.catalog, service.repository), KnowledgeService(service.catalog, service.repository, courses)


def test_chunk_positions_math_code_headings_and_stable_ids():
    raw = '# 梯度\n\n' + ('说明文字' * 190) + '\n\n$$\n' + 'x+y=' * 220 + '\n$$\n\n```python\n# not a section\n' + 'value = 1\n' * 95 + '```\n\n## 收敛\n\n控制学习率。'
    note = dict(id=str(uuid4()), student_id='a', course_id='machine_learning', revision=3,
                content_hash=sha256(raw.encode()).hexdigest(), title='自建', content_md=raw)
    chunks = chunk_markdown(note)
    assert chunks == chunk_markdown(note)
    assert len(chunks) >= 3
    for chunk in chunks:
        assert chunk['raw_md'] == raw[chunk['start_offset']:chunk['end_offset']]
        assert chunk['start_line'] == raw.count('\n', 0, chunk['start_offset']) + 1
        assert chunk['chunk_hash'] == sha256(chunk['raw_md'].encode()).hexdigest()
    for block in blocks(raw):
        if block.protected:
            assert any(c['start_offset'] <= block.start and c['end_offset'] >= block.end for c in chunks)
    assert not any('not a section' in c['section'] for c in chunks)
    assert chunks[-1]['section'] == '梯度 / 收敛'


def test_empty_and_oversized_protected_blocks_are_explicit():
    note = dict(id=str(uuid4()), student_id='a', course_id='machine_learning', revision=1, content_hash='hash', title='标题', content_md='')
    assert chunk_markdown(note) == []
    with pytest.raises(ChunkingError, match='protected_block_too_large'):
        chunk_markdown({**note, 'content_md': '```\n' + 'x' * 9000 + '\n```'})


def test_create_search_update_delete_scope_and_no_learning_mutation(workspace, service):
    notes, knowledge = workspace
    before = fact_snapshot(service.repository.connection)
    note, _ = notes.create('student-a', **make_note())
    assert note['index_status'] == 'ready'
    original_ref = ref(note)
    result = knowledge.search('student-a', '橙光算法', [original_ref])
    assert result['model_calls'] == 0 and result['items'][0]['source_id'] == note['id']
    assert result['items'][0]['review_status'] == 'personal_unverified'
    changed = notes.update('student-a', note['id'], 1, {'content_md': '# 补充\n\n紫星算法采用独立步长。'})
    with pytest.raises(SourceChanged):
        knowledge.search('student-a', '橙光算法', [original_ref])
    # Shared words such as 算法 may still match new text: this is lexical search,
    # not semantic exclusion. The returned content/version must be current.
    assert all(item['source_revision'] == 2 and '橙光' not in item['raw_md']
               for item in knowledge.search('student-a', '橙光算法', [ref(changed)])['items'])
    assert knowledge.search('student-a', '紫星算法', [ref(changed)])['items']
    notes.delete('student-a', note['id'], 2)
    with pytest.raises(NoteNotFound):
        knowledge.search('student-a', '紫星算法', [ref(changed)])
    assert not service.repository.connection.execute('SELECT * FROM note_chunks').fetchall()
    assert fact_snapshot(service.repository.connection) == before


def test_source_selection_empty_duplicate_foreign_and_combined(workspace, service):
    notes, knowledge = workspace
    first, _ = notes.create('student-a', **make_note())
    second, _ = notes.create('student-a', **make_note(content_md='蓝河算法是唯一关键词。'))
    service.register('other')
    with pytest.raises(NoteNotFound):
        knowledge.search('other', '橙光算法', [ref(first)])
    assert not any(s['source_type'] == 'personal_note' for s in knowledge.sources('other')['items'])
    with pytest.raises(ValueError):
        knowledge.search('student-a', '梯度下降', [])
    with pytest.raises(ValueError):
        knowledge.search('student-a', '梯度下降', [ref(first), ref(first)])
    assert all(item['source_id'] == first['id'] and '蓝河' not in item['raw_md']
               for item in knowledge.search('student-a', '蓝河算法', [ref(first)])['items'])
    course = next(s for s in knowledge.sources('student-a')['items'] if s['source_id'] == 'gradient')
    course_ref = {key: course[key] for key in ('source_type', 'source_id', 'source_version')}
    result = knowledge.search('student-a', '梯度', [course_ref, ref(first)], top_k=5)
    assert all(item['source_id'] in ('gradient', first['id']) for item in result['items'])
    assert result['fusion'] == 'rrf-k60'
    assert not knowledge.search('student-a', '橙光算法', [ref(first)], knowledge_id='model_evaluation')['items']


def test_failed_index_keeps_raw_and_safe_retry(workspace, service):
    notes, knowledge = workspace
    def fail(_):
        raise RuntimeError('PRIVATE RAW TEXT MUST NOT LEAK')
    notes.indexer = NoteIndexer(service.repository, fail)
    note, _ = notes.create('student-a', **make_note())
    assert note['index_status'] == 'failed'
    assert notes.get('student-a', note['id'])['content_md'] == note['content_md']
    state = PersonalRepository(service.repository).state(note['id'])
    assert state['error_code'] == 'index_build_failed' and 'PRIVATE' not in json.dumps(state)
    with pytest.raises(IndexUnavailable):
        knowledge.search('student-a', '橙光算法', [ref(note)])
    recovered = NoteIndexer(service.repository).rebuild('student-a', note['id'], 1)
    assert recovered['status'] == 'ready'
    assert knowledge.search('student-a', '橙光算法', [ref(note)])['items']


def test_update_invalidates_before_build_and_old_build_cannot_publish(workspace, service):
    notes, knowledge = workspace
    note, _ = notes.create('student-a', **make_note())
    path = service.repository.connection.execute('PRAGMA database_list').fetchone()[2]
    barrier = Barrier(2)
    def delayed(snapshot):
        barrier.wait(); barrier.wait()
        return chunk_markdown(snapshot)
    def old_task():
        with SQLiteRepository(path) as repository:
            with pytest.raises(NoteConflict):
                NoteIndexer(repository, delayed).rebuild('student-a', note['id'], 1)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(old_task)
        barrier.wait()
        with pytest.raises(IndexUnavailable):
            knowledge.search('student-a', '橙光算法', [ref(note)])
        changed = notes.update('student-a', note['id'], 1, {'content_md': '青竹算法控制新的归一化梯度。'})
        barrier.wait(); future.result(timeout=5)
    assert PersonalRepository(service.repository).state(note['id'])['indexed_revision'] == 2
    assert knowledge.search('student-a', '青竹算法', [ref(changed)])['items']


def test_build_token_fences_same_revision_and_delete(workspace, service):
    notes, _ = workspace
    note, _ = notes.create('student-a', **make_note())
    storage = PersonalRepository(service.repository)
    old = storage.claim('student-a', note['id'], 1, 'old')
    latest = storage.claim('student-a', note['id'], 1, 'latest')
    with pytest.raises(NoteConflict):
        storage.publish(old, 'old', chunk_markdown(old))
    storage.fail(old, 'old', 'stale_failure')
    assert storage.state(note['id'])['status'] == 'building'
    storage.publish(latest, 'latest', chunk_markdown(latest))
    snapshot = storage.claim('student-a', note['id'], 1, 'delete-race')
    notes.delete('student-a', note['id'], 1)
    with pytest.raises(NoteConflict):
        storage.publish(snapshot, 'delete-race', chunk_markdown(snapshot))
    assert storage.state(note['id'])['status'] == 'disabled'


def test_final_validation_rejects_change_during_search(workspace, service, monkeypatch):
    notes, knowledge = workspace
    note, _ = notes.create('student-a', **make_note())
    import eduagent.services.knowledge as module
    original = module.search_personal
    def interleave(*args):
        result = original(*args)
        notes.update('student-a', note['id'], 1, {'title': '标题也改变版本'})
        return result
    monkeypatch.setattr(module, 'search_personal', interleave)
    with pytest.raises(SourceChanged):
        knowledge.search('student-a', '橙光算法', [ref(note)])


def test_reopen_and_recover_interrupted_build(workspace, service):
    notes, _ = workspace
    note, _ = notes.create('student-a', **make_note())
    path = service.repository.connection.execute('PRAGMA database_list').fetchone()[2]
    PersonalRepository(service.repository).claim('student-a', note['id'], 1, 'interrupted')
    with SQLiteRepository(path) as reopened:
        assert NoteIndexer(reopened).recover()['recovered'] == 1
        knowledge = KnowledgeService(service.catalog, reopened)
        assert knowledge.search('student-a', '橙光算法', [ref(note)])['items']
        assert NoteIndexer(reopened).recover()['recovered'] == 0


def test_course_selection_filters_before_top_k_and_original_baseline_unchanged(workspace):
    _, knowledge = workspace
    index = knowledge.courses.index
    for query in ['梯度下降', '模型评估', 'MSE', '机器学习课程QQ群号']:
        assert index.search(query) == index.search(query, source_ids=frozenset(knowledge.courses.documents))
    assert all(item['citation_id'].startswith('evaluation:') for item in index.search(
        '模型评估梯度下降', top_k=5, source_ids=frozenset({'evaluation'})))
    assert index.search('梯度下降', source_ids=frozenset()) == []


def test_sparse_index_limits_and_private_vocabulary_are_explicit():
    from eduagent.retrieval.personal import search_personal
    base = dict(title='自建', section='章节', content_text='独有词 unique', chunk_id='x')
    with pytest.raises(NoteTooLarge):
        search_personal([base] * 257, 'unique', 3)
    with pytest.raises(NoteTooLarge):
        search_personal([{**base, 'content_text': ' '.join('word' + str(i) for i in range(8193))}], 'unique', 3)
    assert not search_personal([base], 'otherlearnersecret', 3)


def test_tampered_derived_raw_is_never_returned(workspace, service):
    notes, knowledge = workspace
    note, _ = notes.create('student-a', **make_note())
    service.repository.connection.execute("UPDATE note_chunks SET raw_md='unexpected' WHERE note_id=?", (note['id'],))
    with pytest.raises(IndexUnavailable):
        knowledge.search('student-a', '橙光算法', [ref(note)])


def test_inline_math_is_not_split_at_window_boundary():
    formula = '$' + 'x+y' * 80 + '$'
    raw = '说明' * 390 + formula + ' 后续内容' * 80
    note = dict(id=str(uuid4()), student_id='a', course_id='machine_learning', revision=1,
                content_hash=sha256(raw.encode()).hexdigest(), title='数学', content_md=raw)
    chunks = chunk_markdown(note)
    assert any(formula in chunk['raw_md'] for chunk in chunks)
    begin, end = raw.index(formula), raw.index(formula) + len(formula)
    assert all(not begin < c['start_offset'] < end and not begin < c['end_offset'] < end for c in chunks)
