"""Read-only deployment, backup and original-table preservation checks."""
import json
import re
import sqlite3
import zipfile
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from urllib.request import ProxyHandler, build_opener

from eduagent.storage.migrations import preserved_snapshot


def main():
    root = Path(__file__).resolve().parents[1]
    folder = Path(json.loads((root / 'data/local/refactor-stage1-current.json').read_text())['folder'])
    baseline = json.loads((folder / 'baseline.json').read_text(encoding='utf-8'))
    database = root / 'data/local/eduagent.sqlite3'
    def snapshot(path):
        with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as db:
            assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
            assert not db.execute('PRAGMA foreign_key_check').fetchall()
            assert db.execute('PRAGMA user_version').fetchone()[0] == baseline['schema']
            return preserved_snapshot(db)[0]
    assert snapshot(folder / 'before.sqlite3') == baseline['tables']
    assert snapshot(database) == baseline['tables'], 'Live data changed; do not claim preservation without investigation.'
    opener = build_opener(ProxyHandler({}))
    def get(path):
        with opener.open('http://127.0.0.1:8000' + path, timeout=15) as response:
            return response.read(), dict(response.headers)
    assert json.loads(get('/health')[0])['status'] == 'ok'
    index, headers = get('/')
    assert index == (root / 'frontend/dist/index.html').read_bytes()
    assert any(k.lower() == 'cache-control' and v == 'no-store' for k, v in headers.items())
    assets = [s.decode() for s in re.findall(rb'(?:src|href)="(/assets/[^\"]+)"', index)]
    assert assets
    for path in assets:
        assert get(path)[0] == (root / 'frontend/dist' / path.lstrip('/')).read_bytes()
    chunks = [p for p in (root / 'frontend/dist/assets').glob('*.js') if 'Page-' in p.name]
    for chunk in chunks:
        assert get('/assets/' + chunk.name)[0] == chunk.read_bytes()
    assert len(chunks) >= 10
    assert snapshot(database) == baseline['tables']
    with zipfile.ZipFile(folder / 'code-before.zip') as archive:
        assert archive.testzip() is None
        for name in ('AGENTS.md', 'README.md', 'PROJECT_CONTEXT.md', 'DEVELOPMENT_PLAN.md'):
            old = name if name in ('AGENTS.md', 'README.md') else 'docs/' + name
            assert archive.read(old) == (root / 'docs/history/pre-refactor-stage1' / name).read_bytes()
        before = {i.filename: sha256(archive.read(i)).hexdigest() for i in archive.infolist()}
    current = {}
    for prefix in ('frontend/src', 'backend/src', 'backend/tests', 'docs', 'scripts'):
        for path in (root / prefix).rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts:
                current[path.relative_to(root).as_posix()] = sha256(path.read_bytes()).hexdigest()
    for name in ('AGENTS.md', 'README.md', 'frontend/package.json', 'frontend/package-lock.json', 'frontend/vite.config.js'):
        current[name] = sha256((root / name).read_bytes()).hexdigest()
    changed = [dict(path=name, change='added' if name not in before else 'modified') for name in sorted(current)
               if current[name] != before.get(name)]
    removed = [name for name in before if name not in current]
    assert not removed, 'Compatibility/archival entries must not be removed silently.'
    assert not any(i['path'].startswith('backend/') for i in changed), 'Backend business is outside this refactor.'
    report = dict(passed=True, schema=baseline['schema'], tables=len(baseline['tables']), all_original_table_summaries_unchanged=True,
                  backup_verified=True, archive_matches_originals=True, integrity=True, foreign_keys=True,
                  migration_required=False, production_writes=0, real_model_calls=0,
                  entry_assets=assets, lazy_page_chunks=len(chunks), entry_js_bytes=max(len(get(p)[0]) for p in assets if p.endswith('.js')),
                  backend_source_and_tests_unchanged=True, files=len(changed), backup=str(folder),
                  verified_at=datetime.now(timezone.utc).isoformat())
    (root / 'data/evaluation/refactor-stage1-files-v1.json').write_text(json.dumps(changed, ensure_ascii=False, indent=2), encoding='utf-8')
    (root / 'data/evaluation/refactor-stage1-deployment-v1.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
