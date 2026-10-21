"""Display-format compatibility must not become a source/identity capability."""

import json

import pytest

from eduagent.agent.deepseek import ModelReply
from eduagent.agent.workbench_answers import AnswerValidationError, parse_answer
from eduagent.storage.migrations import fact_snapshot
from test_workbench import bench, body, ref


PASSAGES = {'gradient:1': {'citation_id': 'gradient:1', 'source_id': 'gradient', 'raw_md': '服务端保存原文'}}


@pytest.mark.parametrize('field', ['answer_md', 'answer_markdown', 'response', 'response_md', 'content', 'explanation'])
def test_known_answer_alias_and_unrelated_metadata_are_display_compatible(field):
    raw = {field: '解释 $w$ [gradient:1]', 'citations': ['gradient:1'], 'title': '回答标题', 'status': 'success'}
    result = parse_answer(json.dumps(raw), PASSAGES)
    assert result['answer'] == raw[field] and result['citations'] == list(PASSAGES.values())
    assert 'title' not in result and 'status' not in result


def test_extra_model_metadata_never_overrides_server_sources_or_usage():
    raw = {'answer': '解释 [gradient:1]', 'citation_ids': ['gradient:1'],
           'sources': [{'student_id': 'other', 'raw_md': '伪造原文'}], 'usage': {'completion_tokens': 99999}}
    result = parse_answer(json.dumps(raw), PASSAGES)
    assert result['citations'][0] is PASSAGES['gradient:1']
    assert 'sources' not in result and 'usage' not in result and '伪造原文' not in json.dumps(result, ensure_ascii=False)


@pytest.mark.parametrize('wrapper', ['data', 'result', 'response'])
def test_single_explicit_envelope_is_unwrapped(wrapper):
    raw = {wrapper: {'answer': '解释 [gradient:1]', 'citation_ids': ['gradient:1']}, 'status': 'ok'}
    assert parse_answer(json.dumps(raw), PASSAGES)['citations'] == list(PASSAGES.values())


def test_single_element_list_remains_unambiguous_but_multiple_answers_reject():
    answer = {'answer': '解释 [gradient:1]', 'citation_ids': ['gradient:1']}
    assert parse_answer(json.dumps([answer]), PASSAGES)['answer'] == answer['answer']
    with pytest.raises(AnswerValidationError, match='invalid_fields'):
        parse_answer(json.dumps([answer, answer]), PASSAGES)


def test_missing_reference_array_can_use_actual_inline_ids_only():
    result = parse_answer('{"answer":"解释 [gradient:1]"}', PASSAGES)
    assert result['citations'] == list(PASSAGES.values())
    with pytest.raises(AnswerValidationError, match='unknown_citation'):
        parse_answer('{"answer":"解释 [unselected:1]"}', PASSAGES)


@pytest.mark.parametrize('key', ['citation_id', 'id'])
def test_citation_objects_cannot_override_original_metadata(key):
    result = parse_answer(json.dumps({'answer': '解释 [gradient:1]', 'references': [
        {key: 'gradient:1', 'raw_md': '伪造原文', 'source_version': 'forged'}]}), PASSAGES)
    assert result['citations'] == list(PASSAGES.values())
    with pytest.raises(AnswerValidationError, match='unknown_citation'):
        parse_answer(json.dumps({'answer': '解释 [unselected:1]', 'citations': [{key: 'unselected:1'}]}), PASSAGES)


@pytest.mark.parametrize('field', ['student_id', 'source_ids', 'tool_calls', 'update_bkt', 'execute_sql'])
def test_control_fields_still_reject_including_inside_an_envelope(field):
    for wrap in (False, True):
        raw = {'answer': '解释 [gradient:1]', 'citation_ids': ['gradient:1'], field: 'untrusted control'}
        with pytest.raises(AnswerValidationError, match='forbidden_output_fields'):
            parse_answer(json.dumps({'result': raw} if wrap else raw), PASSAGES)


def test_conflicting_aliases_and_conflicting_envelopes_are_not_guessed():
    for raw in ({'answer': 'A', 'response': 'B'}, {'data': {'answer': 'A'}, 'result': {'answer': 'B'}}):
        with pytest.raises(AnswerValidationError, match='ambiguous_fields'):
            parse_answer(json.dumps(raw), {})


def test_missing_body_diagnostic_records_no_unknown_property_names_or_values():
    with pytest.raises(AnswerValidationError, match='missing_answer') as caught:
        parse_answer('{"private note title":"private body"}', PASSAGES)
    assert caught.value.summary == {'root_type': 'object', 'recognized_fields': [], 'unknown_field_count': 1}
    assert 'private' not in json.dumps(caught.value.summary)


def test_supplement_only_answer_and_omitted_references_are_accepted_as_unbacked():
    result = parse_answer('{"general_knowledge":"资料以外的解释","title":"附加标题"}', PASSAGES)
    assert result['answer'] == '' and result['citations'] == [] and result['supplement_md'] == '资料以外的解释'


@pytest.mark.parametrize('raw', [
    {'answer': '解释 [gradient:1]', 'citation_ids': ['gradient:1'], 'title': '额外字段'},
    {'response': '解释 [gradient:1]', 'citations': ['gradient:1']},
])
def test_guide_contract_is_not_relaxed(raw):
    with pytest.raises(AnswerValidationError, match='invalid_fields'):
        parse_answer(json.dumps(raw), PASSAGES, guide=True)


def test_compatible_model_reply_is_saved_and_replayed_without_overwriting_facts(bench):
    class Compatible:
        calls = 0
        def complete(self, messages, tools):
            self.calls += 1
            key = json.loads(messages[1]['content'])['untrusted_evidence'][0]['citation_id']
            return ModelReply({'role': 'assistant', 'content': json.dumps({
                'response': '解释 ['+key+']', 'citations': [{'citation_id': key, 'raw_md': '伪造原文'}],
                'supplement': '模型知识补充。', 'title': '额外标题', 'usage': {'completion_tokens': 99999}})}, 9, 7)
    model = Compatible()
    bench.client_factory = lambda: model
    before = fact_snapshot(bench.db)
    request = body([ref(bench, 'gradient')])
    result = bench.ask('student-a', request)
    assert result['status'] == 'complete' and result['answer_basis'] == 'mixed'
    assert result['usage'] == {'prompt_tokens': 9, 'completion_tokens': 7}
    assert '伪造原文' not in json.dumps(result, ensure_ascii=False) and result['validation_error'] is None
    assert bench.ask('student-a', request)['answer'] == result['answer'] and model.calls == 1
    assert fact_snapshot(bench.db) == before
