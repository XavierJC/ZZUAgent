"""Credential-free parser entry point. Limits precede all document imports."""

import json
import os
from pathlib import Path
import sys


def main():
    if sys.stdin.buffer.readline(16) != b'start\n':
        return 2
    if os.name != 'nt':
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024,) * 2)
        resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
        resource.setrlimit(resource.RLIMIT_FSIZE, (8 * 1024 * 1024,) * 2)
    from eduagent.documents.models import DocumentError, MAX_OUTPUT
    output = Path(sys.argv[2])
    try:
        data = json.loads(Path(sys.argv[1]).read_text(encoding='utf8'))
        path = Path(data['path'])
        if data.get('mode') == 'render':
            from eduagent.documents.vision import render_pages
            payload = render_pages(path, data['pages'])
        else:
            from eduagent.documents.parsers import parse
            payload = parse(path, data['kind'])
        value = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode('utf8')
        if len(value) > MAX_OUTPUT:
            raise DocumentError('document_too_large', 413)
    except MemoryError:
        value = b'{"error":"parse_memory_limit"}'
    except ImportError:
        value = b'{"error":"parser_unavailable"}'
    except DocumentError as exc:
        value = json.dumps({'error': exc.code}).encode()
    except Exception:
        value = b'{"error":"parse_failed"}'
    with output.open('xb') as file:
        file.write(value)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
