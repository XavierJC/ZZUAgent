"""Format-specific local extraction adapters."""


def parse(path, kind):
    from eduagent.documents.preflight import signature
    signature(path, kind)
    if kind == 'pdf':
        from .pdf import extract
    elif kind == 'pptx':
        from .pptx import extract
    else:
        from .text import extract
    return extract(path, kind)
