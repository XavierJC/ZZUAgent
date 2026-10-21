"""Parse provider output without trusting model-supplied citations or actions."""

import json
import re


class AnswerValidationError(ValueError):
    """Only a fixed diagnostic code is persisted, never rejected private text."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise AnswerValidationError('duplicate_json_fields')
        result[key] = value
    return result


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
    if (not isinstance(answer, dict) or not required <= set(answer)
            or set(answer) - (required if guide else required | {'supplement_md'})):
        raise AnswerValidationError('invalid_fields')
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
