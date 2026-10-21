"""Parse provider output without trusting model-supplied citations or actions."""

import json
import re


class AnswerValidationError(ValueError):
    """Only a fixed diagnostic code is persisted, never rejected private text."""

    def __init__(self, code, summary=None):
        self.code = code
        self.summary = summary
        super().__init__(code)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise AnswerValidationError('duplicate_json_fields')
        result[key] = value
    return result


# Model text is display data, never a capability or database write. Discard
# unrelated presentation metadata, but reject explicit control-plane fields.
CONTROL_FIELDS = frozenset({'student_id', 'course_id', 'request_id', 'source_ids', 'source_versions',
    'context', 'request_context', 'tool_calls', 'tools', 'actions', 'action', 'sql', 'execute_sql',
    'update_bkt', 'update_mastery', 'score', 'scores', 'mastery', 'bkt', 'recommendations', 'decision_id'})
ALIASES = {
    'answer': ('answer', 'answer_md', 'answer_markdown', 'response', 'response_md', 'content', 'explanation'),
    'citation_ids': ('citation_ids', 'citations', 'references'),
    'supplement_md': ('supplement_md', 'supplement', 'supplemental_md', 'model_knowledge',
                      'additional_knowledge', 'general_knowledge', 'general_answer', 'extension_md'),
}


def _reject_controls(value):
    if any(key.lower().replace('-', '_') in CONTROL_FIELDS for key in value):
        raise AnswerValidationError('forbidden_output_fields')


def _chat_fields(value):
    """Normalize only known answer aliases; never consume model source metadata."""
    if isinstance(value, list) and len(value) == 1:
        value = value[0]
    if not isinstance(value, dict):
        raise AnswerValidationError('invalid_fields')
    _reject_controls(value)
    # One explicit envelope is unambiguous; multiple alternatives are not.
    envelopes = [value[key] for key in ('data', 'result', 'response') if isinstance(value.get(key), dict)]
    if envelopes:
        if len(envelopes) != 1 or any(key in value for key in ('answer', 'answer_md', 'content', 'explanation')):
            raise AnswerValidationError('ambiguous_fields')
        value = envelopes[0]
        _reject_controls(value)
    normalized = {}
    for target, aliases in ALIASES.items():
        found = [value[key] for key in aliases if key in value]
        if found:
            if any(item != found[0] for item in found[1:]):
                raise AnswerValidationError('ambiguous_fields')
            normalized[target] = found[0]
    if 'answer' not in normalized:
        if isinstance(normalized.get('supplement_md'), str) and normalized['supplement_md'].strip():
            normalized['answer'] = ''
        else:
            raise AnswerValidationError('missing_answer')
    if 'citation_ids' not in normalized:
        text = normalized['answer']
        normalized['citation_ids'] = list(dict.fromkeys(re.findall(r'\[([a-zA-Z0-9_-]+:\d+)\]', text))) if isinstance(text, str) else []
    elif isinstance(normalized['citation_ids'], list):
        # A citation object can carry invented titles/content. Extract only its
        # identifier; the validator below resolves everything from the server.
        ids = []
        for item in normalized['citation_ids']:
            if isinstance(item, dict):
                if 'citation_id' in item and 'id' in item and item['citation_id'] != item['id']:
                    raise AnswerValidationError('ambiguous_fields')
                item = item.get('citation_id', item.get('id'))
            ids.append(item)
        normalized['citation_ids'] = ids
    return normalized


def parse_answer(content, passages, *, guide=False):
    """Accept a complete JSON object, optionally inside one JSON code fence.

    Do not extract arbitrary braces or repair JSON/LaTeX escapes: those changes
    could alter the original answer. A valid source list can supply a missing
    global reference footer; conflicting or invented citations are rejected.
    """
    if not isinstance(content, str):
        raise AnswerValidationError('invalid_json')
    raw = content.strip().lstrip('\ufeff').strip()
    fence = re.fullmatch(r'```(?:json)?[ \t]*\r?\n(.*?)\r?\n[ \t]*```', raw, re.I | re.S)
    if fence:
        raw = fence.group(1).strip()
    try:
        answer = json.loads(raw, object_pairs_hook=_unique_object)
    except json.JSONDecodeError:
        raise AnswerValidationError('invalid_json') from None
    required = {'answer', 'citation_ids'}
    # Keep only known schema names and counts for diagnosis, never values or
    # arbitrary model-generated property names that might include private text.
    known = {key for aliases in ALIASES.values() for key in aliases}
    summary = {'root_type': 'object' if isinstance(answer, dict) else 'array' if isinstance(answer, list) else 'other',
               'recognized_fields': sorted(set(answer) & known) if isinstance(answer, dict) else [],
               'unknown_field_count': len(set(answer) - known) if isinstance(answer, dict) else 0}
    try:
        if guide:
            if not isinstance(answer, dict) or set(answer) != required:
                raise AnswerValidationError('invalid_fields')
        else:
            answer = _chat_fields(answer)
    except AnswerValidationError as error:
        error.summary = summary
        raise
    text, ids = answer['answer'], answer['citation_ids']
    supplement = answer.get('supplement_md', '')
    if (not isinstance(text, str) or not isinstance(supplement, str)
            or not (text.strip() or supplement.strip()) or len(text) + len(supplement) > 6000):
        raise AnswerValidationError('invalid_answer')
    if not isinstance(ids, list) or len(ids) > 5 or any(not isinstance(key, str) for key in ids):
        raise AnswerValidationError('invalid_citation_list')
    if any(key not in passages for key in ids):
        raise AnswerValidationError('unknown_citation')
    if passages and not ids:
        if guide or re.search(r'\[([a-zA-Z0-9_-]+:\d+)\]', text):
            raise AnswerValidationError('missing_citations')
        if text.strip():
            # A retrieval hit does not force the model to claim it as evidence.
            # Legacy two-field general answers remain usable but explicitly
            # become unbacked supplements instead of locally sourced text.
            supplement = text + ('\n\n' + supplement if supplement.strip() else '')
            text = ''
    if supplement and re.search(r'\[(?:[a-zA-Z0-9_-]+:\d+|\d+|citation_id)\]', supplement):
        raise AnswerValidationError('supplement_citation')
    if ids and not text.strip():
        raise AnswerValidationError('invalid_answer')
    if guide and re.search(r'!?\[[^\]]*\]\(|https?://|<a\b', text, re.I):
        raise AnswerValidationError('disallowed_links')
    inline = set(re.findall(r'\[([a-zA-Z0-9_-]+:\d+)\]', text))
    if inline - passages.keys():
        raise AnswerValidationError('unknown_citation')
    if not passages and (ids or re.search(r'\[(?:\d+|citation_id|source[^\]]*|来源[^\]]*)\]', text, re.I)):
        raise AnswerValidationError('unexpected_citations')
    if not inline and ids and not guide:
        # All IDs were actually retrieved and explicitly supplied by the model.
        # This adds only a reference footer, not sentence-level attribution.
        text += '\n\n参考片段：' + ' '.join(f'[{key}]' for key in dict.fromkeys(ids))
    elif inline != set(ids):
        raise AnswerValidationError('citation_mismatch')
    result = {'answer': text, 'citations': [passages[key] for key in dict.fromkeys(ids)]}
    if supplement.strip():
        result['supplement_md'] = supplement
    return result
