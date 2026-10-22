"""Keep UTF-8 original Unicode positions; code and math remain intact."""

from eduagent.documents.models import DocumentError, result, unit, MAX_TEXT
from eduagent.retrieval.note_chunks import blocks


def extract(path, kind):
    try:
        text = path.read_bytes().decode('utf-8-sig')
    except UnicodeError:
        raise DocumentError('invalid_encoding') from None
    if len(text) > MAX_TEXT:
        raise DocumentError('document_too_large', 413)
    parts = blocks(text) if kind == 'md' else []
    # One text unit retains the exact entire original; block locations describe
    # sections without imposing a PDF's 200-page limit on every paragraph.
    groups = [dict(kind='protected' if part.protected else 'text', section=part.section,
                   start_offset=part.start, end_offset=part.end,
                   start_line=text.count('\n', 0, part.start) + 1,
                   end_line=text.count('\n', 0, max(part.start, part.end - 1)) + 1)
              for part in parts]
    return result([unit(1, 'markdown_section' if kind == 'md' else 'text_block', '', text,
                        dict(start_line=1, end_line=max(1, len(text.splitlines()))), blocks=groups)])
