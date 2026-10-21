"""Offline parser tests: formatting tolerance must not create source authority."""

import json

import pytest

from eduagent.agent.workbench_answers import AnswerValidationError, parse_answer


PASSAGES = {'gradient:1': {'citation_id': 'gradient:1', 'raw_md': '沿负梯度更新。'}}


@pytest.mark.parametrize('wrapper', ['{}', '```json\n{}\n```', '```JSON\r\n{}\r\n```', '\ufeff {} '])
def test_valid_json_and_complete_code_fence_preserve_markdown_and_math(wrapper):
    text = r'解释 $\frac{1}{2}$。[gradient:1]'
    result = parse_answer(wrapper.format(json.dumps({'answer': text, 'citation_ids': ['gradient:1']})), PASSAGES)
    assert result['answer'] == text and result['citations'] == list(PASSAGES.values())


def test_verified_list_can_supply_a_missing_reference_footer():
    result = parse_answer(json.dumps({'answer': '解释 $w$。', 'citation_ids': ['gradient:1']}), PASSAGES)
    assert result['answer'] == '解释 $w$。\n\n参考片段：[gradient:1]'
    assert result['citations'] == list(PASSAGES.values())


@pytest.mark.parametrize('content,passages,code', [
    ('plain Markdown', PASSAGES, 'invalid_json'),
    ('说明\n```json\n{}\n```', PASSAGES, 'invalid_json'),
    ('{"answer":"a","answer":"b","citation_ids":[]}', {}, 'duplicate_json_fields'),
    ('[]', PASSAGES, 'invalid_fields'),
    ('{"answer":"x","citation_ids":[],"update_bkt":1}', {}, 'invalid_fields'),
    ('{"answer":"","citation_ids":[]}', {}, 'invalid_answer'),
    ('{"answer":"x","citation_ids":"gradient:1"}', PASSAGES, 'invalid_citation_list'),
    ('{"answer":"x","citation_ids":["unselected:1"]}', PASSAGES, 'unknown_citation'),
    ('{"answer":"x [unselected:1]","citation_ids":["gradient:1"]}', PASSAGES, 'unknown_citation'),
    ('{"answer":"x [gradient:1]","citation_ids":[]}', PASSAGES, 'missing_citations'),
    ('{"answer":"x [1]","citation_ids":[]}', {}, 'unexpected_citations'),
    ('{"answer":"x [gradient:1]","citation_ids":[]}', {}, 'unknown_citation'),
])
def test_invalid_answers_have_specific_non_private_diagnostics(content, passages, code):
    with pytest.raises(AnswerValidationError) as caught:
        parse_answer(content, passages)
    assert caught.value.code == code and str(caught.value) == code


def test_conflicting_inline_list_is_not_repaired():
    passages = {**PASSAGES, 'gradient:2': {'citation_id': 'gradient:2'}}
    with pytest.raises(AnswerValidationError, match='citation_mismatch'):
        parse_answer('{"answer":"解释 [gradient:1]","citation_ids":["gradient:2"]}', passages)


def test_no_evidence_accepts_general_explanation_without_fabricated_citations():
    assert parse_answer('{"answer":"你好，本轮没有本地资料依据。","citation_ids":[]}', {})['citations'] == []


def test_guide_retains_strict_inline_and_action_link_constraints():
    with pytest.raises(AnswerValidationError, match='citation_mismatch'):
        parse_answer('{"answer":"解释","citation_ids":["gradient:1"]}', PASSAGES, guide=True)
    with pytest.raises(AnswerValidationError, match='disallowed_links'):
        parse_answer('{"answer":"[操作](https://example.com/) [gradient:1]","citation_ids":["gradient:1"]}', PASSAGES, guide=True)
