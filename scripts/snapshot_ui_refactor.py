"""Backup the actual working tree and read-only live data for this UI-only change."""
import json
import sqlite3
import zipfile
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from eduagent.storage.migrations import preserved_snapshot

root = Path(__file__).resolve().parents[1]
folder = root / 'data/local' / ('ui-refactor-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
folder.mkdir(parents=True)
with sqlite3.connect((root/'data/local/eduagent.sqlite3').as_uri()+'?mode=ro', uri=True) as live, sqlite3.connect(folder/'before.sqlite3') as db:
    live.backup(db)
    tables, columns = preserved_snapshot(db)
    schema = db.execute('PRAGMA user_version').fetchone()[0]
    assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    assert not db.execute('PRAGMA foreign_key_check').fetchall()
files = {}
with zipfile.ZipFile(folder/'code-before.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
    for prefix in ('frontend/src', 'backend/src', 'backend/tests', 'docs', 'scripts'):
        for file in (root/prefix).rglob('*'):
            if file.is_file() and '__pycache__' not in file.parts:
                name = file.relative_to(root).as_posix()
                archive.write(file, name)
                files[name] = sha256(file.read_bytes()).hexdigest()
    for name in ('README.md', 'AGENTS.md', 'frontend/package.json', 'frontend/package-lock.json'):
        archive.write(root/name, name)
        files[name] = sha256((root/name).read_bytes()).hexdigest()
protected = {}
for prefix in ('data/materials', 'data/questions', 'data/knowledge', 'data/evaluation'):
    for file in (root/prefix).rglob('*'):
        if file.is_file(): protected[file.relative_to(root).as_posix()] = sha256(file.read_bytes()).hexdigest()
(folder/'baseline.json').write_text(json.dumps(dict(schema=schema, tables=tables, columns=columns, files=files, protected=protected), ensure_ascii=False, indent=2), encoding='utf-8')
(root/'data/local/ui-refactor-current.json').write_text(json.dumps(dict(folder=str(folder))), encoding='utf-8')
print(json.dumps(dict(backup=str(folder), schema=schema, tables=len(tables), source_files=len(files), protected_files=len(protected))))
