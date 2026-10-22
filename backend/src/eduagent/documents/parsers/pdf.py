"""Extract PDF text; never treat image-only pages or formulas as verified."""

from eduagent.documents.models import DocumentError, MAX_UNITS, MAX_TEXT, result, unit


def image_objects(page):
    """Inspect resource dictionaries only; never decode image pixels here."""
    pending, visited, count, incomplete = [page.get('/Resources', {})], set(), 0, False
    def resolve(value):
        return value.get_object() if hasattr(value, 'get_object') else value
    while pending:
        resources = resolve(pending.pop())
        objects = resolve(resources.get('/XObject', {}))
        for reference in objects.values():
            obj = reference.get_object()
            key = id(obj)
            if key in visited:
                continue
            visited.add(key)
            if len(visited) > 500:
                incomplete = True; pending.clear(); break
            if obj.get('/Subtype') == '/Image':
                count += 1
            elif obj.get('/Subtype') == '/Form' and obj.get('/Resources'):
                pending.append(obj['/Resources'])
    return count, incomplete


def extract(path, kind='pdf'):
    from pypdf import PdfReader
    reader = PdfReader(path)
    if reader.is_encrypted:
        raise DocumentError('encrypted_document')
    if len(reader.pages) > MAX_UNITS:
        raise DocumentError('too_many_pages')
    units, count = [], 0
    labels = reader.page_labels
    for number, page in enumerate(reader.pages, 1):
        stream = page.get_contents()
        if stream is not None and len(stream.get_data()) > 8 * 1024 * 1024:
            raise DocumentError('document_too_large', 413)
        text = page.extract_text() or ''
        count += len(text)
        if count > MAX_TEXT:
            raise DocumentError('document_too_large', 413)
        warnings = ['pdf_layout_and_math_unverified']
        image_count, incomplete = image_objects(page)
        if image_count:
            warnings.append('image_content_not_extracted')
        if incomplete:
            warnings.append('image_resource_inspection_incomplete')
        # Inline image syntax is not a pixel extraction; flag it for review.
        import re
        if stream is not None and re.search(rb'\bBI\s', stream.get_data()):
            warnings.append('possible_inline_image_not_extracted')
        if len(text.strip()) < 20:
            warnings.append('possible_scan_or_image_content')
        if '\ufffd' in text or '\x00' in text:
            warnings.append('text_encoding_needs_review')
        units.append(unit(number, 'pdf_page', f'第{number}页', text,
                          dict(page_number=number, page_label=labels[number - 1]),
                          blocks=[dict(kind='unextracted_images', count=image_count)] if image_count else [], warnings=warnings))
    return result(units)
