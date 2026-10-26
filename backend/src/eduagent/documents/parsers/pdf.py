"""Extract PDF text; never treat image-only pages or formulas as verified."""

from eduagent.documents.models import DocumentError, MAX_UNITS, MAX_TEXT, result, unit


def readable_unicode(value):
    """Repair UTF-16 pairs from PDF CMaps; visibly mark only damaged characters.

    Some PDFs map the two halves of a mathematical character separately.
    Combining a valid pair is lossless. Isolated surrogates and NUL cannot be
    useful extracted text, so keep a visible gap instead of failing the file.
    TXT/Markdown's strict UTF-8 validation is deliberately unchanged.
    """
    text = value
    if any(0xD800 <= ord(char) <= 0xDFFF for char in text):
        text = text.encode('utf-16-le', errors='surrogatepass').decode('utf-16-le', errors='replace')
    text = text.replace('\x00', '\ufffd')
    return text, text != value, '\ufffd' in text


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
    page_count = len(reader.pages)
    if page_count > MAX_UNITS:
        raise DocumentError('too_many_pages')
    units, count = [], 0
    label_warnings = []
    try:
        labels = reader.page_labels
        if len(labels) != page_count:
            raise ValueError('Invalid page labels')
    except (MemoryError, DocumentError):
        raise
    except Exception:
        labels = [str(number) for number in range(1, page_count + 1)]
        label_warnings = ['pdf_page_labels_unavailable']
    for number in range(1, page_count + 1):
        warnings = ['pdf_layout_and_math_unverified', *label_warnings]
        label, repaired_label, damaged_label = readable_unicode(str(labels[number - 1]))
        location = dict(page_number=number, page_label=label)
        try:
            # Access each page separately so a damaged page cannot renumber or
            # discard later pages. File/resource limits remain fatal.
            page = reader.pages[number - 1]
            stream = page.get_contents()
            content = stream.get_data() if stream is not None else b''
            if len(content) > 8 * 1024 * 1024:
                raise DocumentError('document_too_large', 413)
            extracted = page.extract_text() or ''
            if not isinstance(extracted, str):
                raise ValueError('Invalid extracted text')
            text, repaired, damaged = readable_unicode(extracted)
        except (MemoryError, DocumentError):
            raise
        except Exception:
            # Empty text cannot enter retrieval. The original and physical page
            # remain available for comparison; never invent missing content.
            units.append(unit(number, 'pdf_page', f'第{number}页', '', location,
                              warnings=[*warnings, 'pdf_page_text_extraction_failed']))
            continue
        count += len(text)
        if count > MAX_TEXT:
            raise DocumentError('document_too_large', 413)
        if repaired or repaired_label:
            warnings.append('pdf_text_encoding_repaired')
        if damaged or damaged_label:
            warnings.append('text_encoding_needs_review')
        try:
            image_count, incomplete = image_objects(page)
        except (MemoryError, DocumentError):
            raise
        except Exception:
            image_count, incomplete = 0, False
            warnings.append('pdf_image_inspection_failed')
        if image_count:
            warnings.append('image_content_not_extracted')
        if incomplete:
            warnings.append('image_resource_inspection_incomplete')
        # Inline image syntax is not a pixel extraction; flag it for review.
        import re
        if re.search(rb'\bBI\s', content):
            warnings.append('possible_inline_image_not_extracted')
        if len(text.strip()) < 20:
            warnings.append('possible_scan_or_image_content')
        units.append(unit(number, 'pdf_page', f'第{number}页', text,
                          location,
                          blocks=[dict(kind='unextracted_images', count=image_count)] if image_count else [], warnings=warnings))
    return result(units)
