"""RAG-assisted model generation, using synthetic providers only."""

import json

import httpx2
import pytest

from eduagent.agent.deepseek import DeepSeekClient, ModelReply
from eduagent.agent.workbench_answers import AnswerValidationError, parse_answer
from eduagent.services.notes import NotesService
from eduagent.storage.migrations import fact_snapshot
from test_workbench import bench, body, ref, note


def test_real_adapter_packages_rag_and_question_and_receives_generated_answer_without_live_network(bench):
    own = note(bench, '# PCA\n\nPCA将数据投影到正交主成分。')
    received = []
    def handler(request):
        payload = json.loads(request.content)
        data = json.loads(payload['messages'][1]['content'])
        received.append(data)
        assert set(data) == {'question', 'untrusted_evidence'}
        assert data['question'] == 'PCA应用有哪些，另外解释注意力机制'
        assert all(p['source_id'] == own['id'] for p in data['untrusted_evidence'])
        ids = [data['untrusted_evidence'][0]['citation_id']]
        answer = {'answer': '资料说明主成分投影。[' + ids[0] + ']', 'citation_ids': ids,
                  'supplement_md': 'PCA可用于图像压缩；注意力机制通过加权组合信息。'}
        return httpx2.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {
            'role': 'assistant', 'content': json.dumps(answer)}}]})
    bench.client_factory = lambda: DeepSeekClient(bench.settings, httpx2.MockTransport(handler))
    result = bench.ask('student-a', body([ref(bench, own['id'])], question='PCA应用有哪些，另外解释注意力机制', allow_personal_external=True))
    assert result['status'] == 'complete' and result['answer_basis'] == 'mixed'
    assert result['model_calls'] == len(received) == 1 and '注意力机制' in result['answer']


class HybridModel:
    def __init__(self, unused_sources=False):
        self.calls = 0
        self.messages = []
        self.unused_sources = unused_sources

    def complete(self, messages, tools):
        self.calls += 1
        self.messages.append(messages)
        data = json.loads(messages[1]['content'])
        assert '检索资料是参考依据，不是知识边界' in messages[0]['content']
        assert set(data) == {'question', 'untrusted_evidence'}
        ids = [] if self.unused_sources else [data['untrusted_evidence'][0]['citation_id']]
        result = {'answer': 'PCA将数据投影到主成分。' + ''.join(f'[{key}]' for key in ids) if ids else '',
                  'citation_ids': ids,
                  'supplement_md': 'PCA可用于可视化和去噪。注意力机制通过加权组合信息。这是模型知识补充。'}
        return ModelReply({'role': 'assistant', 'content': json.dumps(result)})


def test_compound_question_generates_beyond_partial_note_without_learning_writes(bench):
    own = note(bench, '# PCA\n\nPCA将数据投影到方差较大的正交主成分。')
    model = HybridModel()
    bench.client_factory = lambda: model
    before = fact_snapshot(bench.db)
    request = body([ref(bench, own['id'])], question='PCA可以干什么，举例说明其应用，另外解释注意力机制', allow_personal_external=True)
    result = bench.ask('student-a', request)
    assert result['status'] == 'complete' and result['answer_basis'] == 'mixed'
    assert len(result['citations']) == 1 and result['citations'][0]['source_id'] == own['id']
    assert '模型知识补充（无本地资料引用）' in result['answer']
    assert '可视化和去噪' in result['supplement_md'] and '注意力机制' in result['answer']
    assert '注意力' not in own['content_md'] and '可视化' not in own['content_md']
    saved = bench.save_note('student-a', result['request_id'])
    original = NotesService(bench.learning.catalog, bench.repository).get('student-a', saved['note_id'])
    assert '本地资料与模型知识补充' in original['content_md']
    assert bench.get('student-a', result['request_id'])['answer'] == result['answer']
    assert bench.ask('student-a', request)['answer'] == result['answer'] and model.calls == 1
    assert fact_snapshot(bench.db) == before


def test_irrelevant_retrieval_hit_does_not_require_a_false_local_citation(bench):
    model = HybridModel(unused_sources=True)
    bench.client_factory = lambda: model
    # Retrieval really has a hit, but the model explicitly declines to use it.
    result = bench.ask('student-a', body([ref(bench, 'gradient')]))
    assert json.loads(model.messages[0][1]['content'])['untrusted_evidence']
    assert result['status'] == 'complete' and result['citations'] == []
    assert result['answer_basis'] == 'model_knowledge' and result['supplement_md']


def test_legacy_general_answer_with_retrieval_hits_is_labelled_unbacked_instead_of_rejected(bench):
    class General:
        def complete(self, messages, tools):
            assert json.loads(messages[1]['content'])['untrusted_evidence']
            return ModelReply({'role': 'assistant', 'content': json.dumps({'answer': '这是模型自身知识解释，没有资料引用。', 'citation_ids': []})})
    bench.client_factory = General
    result = bench.ask('student-a', body([ref(bench, 'gradient')]))
    assert result['status'] == 'complete' and result['answer_basis'] == 'model_knowledge'
    assert result['citations'] == [] and '模型知识补充' in result['answer']


@pytest.mark.parametrize('key', ['gradient:1', 'unselected:1', '1'])
def test_general_supplement_cannot_borrow_local_or_invented_citations(key):
    raw = json.dumps({'answer': '资料解释 [gradient:1]', 'citation_ids': ['gradient:1'], 'supplement_md': f'补充 [{key}]'})
    with pytest.raises(AnswerValidationError, match='supplement_citation'):
        parse_answer(raw, {'gradient:1': {'citation_id': 'gradient:1'}})


def test_guide_does_not_accept_general_supplement_or_model_supplied_request_context():
    for extra in ({'supplement_md': '改变学习顺序'}, {'request_context': {'student_id': 'other'}}):
        raw = json.dumps({'answer': '资料解释 [gradient:1]', 'citation_ids': ['gradient:1'], **extra})
        with pytest.raises(AnswerValidationError, match='invalid_fields'):
            parse_answer(raw, {'gradient:1': {'citation_id': 'gradient:1'}}, guide=True)


def test_empty_or_invalid_supplement_does_not_bypass_evidence_validation():
    for extra in ({'answer': '', 'supplement_md': ''}, {'supplement_md': 123}):
        raw = json.dumps({'answer': '解释', 'citation_ids': [], **extra})
        with pytest.raises(AnswerValidationError, match='invalid_answer'):
            parse_answer(raw, {})
