"""Non-destructive baseline for the notebook/product rebuild."""
import json
import sqlite3
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from hashlib import sha256
from eduagent.storage.migrations import preserved_snapshot


def main():
    root = Path(__file__).resolve().parents[1]
    folder = root / 'data/local' / ('notebook-rebuild-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
    folder.mkdir(parents=True)
    path = root / 'data/local/eduagent.sqlite3'
    with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as live, sqlite3.connect(folder / 'before.sqlite3') as db:
        live.backup(db)
        tables, columns = preserved_snapshot(db)
        version = db.execute('PRAGMA user_version').fetchone()[0]
        assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        assert not db.execute('PRAGMA foreign_key_check').fetchall()
    fingerprints = {}
    for name in ('data/materials', 'data/questions', 'data/knowledge', 'data/evaluation'):
        for file in (root / name).rglob('*'):
            if file.is_file(): fingerprints[file.relative_to(root).as_posix()] = sha256(file.read_bytes()).hexdigest()
    with zipfile.ZipFile(folder / 'code-before.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        for name in ('frontend/src', 'backend/src', 'backend/tests', 'docs', 'scripts'):
            for file in (root / name).rglob('*'):
                if file.is_file() and '__pycache__' not in file.parts: archive.write(file, file.relative_to(root))
        for name in ('AGENTS.md', 'README.md', 'frontend/package.json', 'frontend/package-lock.json', 'frontend/vite.config.js'):
            archive.write(root / name, name)
    record = dict(folder=str(folder), schema=version, tables=tables, columns=columns, fingerprints=fingerprints,
                  created_at=datetime.now(timezone.utc).isoformat())
    (folder / 'baseline.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
    (root / 'data/local/notebook-rebuild-current.json').write_text(json.dumps(dict(folder=str(folder))), encoding='utf-8')
    print(json.dumps(dict(folder=str(folder), schema=version, tables=len(tables), fingerprinted_files=len(fingerprints))))


if __name__ == '__main__': main()
