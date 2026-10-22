"""Bounded format/OOXML validation. No archive extraction or URL fetching."""

from pathlib import PurePosixPath
from zipfile import ZipFile, BadZipFile
from eduagent.documents.models import DocumentError, MAX_FILE, MAX_TEXT_FILE


def signature(path, kind):
    size = path.stat().st_size
    if size > (MAX_TEXT_FILE if kind in ('md', 'txt') else MAX_FILE):
        raise DocumentError('document_too_large', 413)
    with path.open('rb') as file:
        head = file.read(512)
    if kind == 'pdf' and not head.startswith(b'%PDF-'):
        raise DocumentError('invalid_document')
    if kind == 'pptx' and not head.startswith(b'PK\x03\x04'):
        raise DocumentError('invalid_document')
    if kind in ('md', 'txt'):
        try:
            text = path.read_bytes().decode('utf-8-sig')
            if '\x00' in text:
                raise UnicodeError()
        except UnicodeError:
            raise DocumentError('invalid_encoding') from None


def pptx_package(path):
    from defusedxml.ElementTree import fromstring
    total = 0
    names = set()
    try:
        with ZipFile(path) as archive:
            infos = archive.infolist()
            if len(infos) > 4096 or sum(i.file_size for i in infos) > 100 * 1024 * 1024:
                raise DocumentError('archive_limits_exceeded')
            for info in infos:
                name = info.filename
                part = PurePosixPath(name)
                if (part.is_absolute() or '..' in part.parts or '\\' in name or ':' in name
                        or any(ord(c) < 32 for c in name) or name.casefold() in names or info.flag_bits & 1):
                    raise DocumentError('unsafe_document')
                names.add(name.casefold())
                if 'vbaproject' in name.lower() or name.lower().startswith('ppt/embeddings/'):
                    raise DocumentError('unsafe_document')
                if info.file_size > max(1, info.compress_size) * 100:
                    raise DocumentError('archive_limits_exceeded')
                # Validate XML before python-pptx opens its own parser. All other
                # parts are bounded by the actual total while reading the ZIP.
                with archive.open(info) as file:
                    size, chunks = 0, []
                    while block := file.read(65536):
                        total += len(block); size += len(block)
                        if total > 100 * 1024 * 1024 or size > info.file_size:
                            raise DocumentError('archive_limits_exceeded')
                        if name.endswith(('.xml', '.rels')):
                            if size > 8 * 1024 * 1024:
                                raise DocumentError('archive_limits_exceeded')
                            chunks.append(block)
                if chunks:
                    xml = b''.join(chunks)
                    tree = fromstring(xml, forbid_dtd=True, forbid_entities=True, forbid_external=True)
                    if sum(1 for _ in tree.iter()) > 100_000:
                        raise DocumentError('archive_limits_exceeded')
                    if name == '[Content_Types].xml':
                        if b'macroEnabled' in xml or b'presentationml.presentation.main+xml' not in xml:
                            raise DocumentError('unsafe_document')
            if not {'[content_types].xml', 'ppt/presentation.xml'} <= names:
                raise DocumentError('invalid_document')
    except DocumentError:
        raise
    except (BadZipFile, OSError, ValueError, KeyError):
        raise DocumentError('invalid_document') from None
    except Exception:
        raise DocumentError('unsafe_document') from None
