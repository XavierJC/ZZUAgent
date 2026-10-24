"""Capture a recoverable local baseline without opening the application or model."""
import json
import sqlite3
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from eduagent.storage.migrations import preserved_snapshot


def main():
    root = Path(__file__).resolve().parents[1]
    folder = root / 'data/local' / ('learning-experience-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
    folder.mkdir(parents=True)
    source = root / 'data/local/eduagent.sqlite3'
    with sqlite3.connect(source.as_uri() + '?mode=ro', uri=True) as live, sqlite3.connect(folder / 'before.sqlite3') as backup:
        live.backup(backup)
        summaries, columns = preserved_snapshot(backup)
        assert backup.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        assert not backup.execute('PRAGMA foreign_key_check').fetchall()
        schema = backup.execute('PRAGMA user_version').fetchone()[0]
    with zipfile.ZipFile(folder / 'code-before.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        for relative in ('frontend/src', 'backend/src', 'backend/tests', 'docs'):
            for path in (root / relative).rglob('*'):
                if path.is_file() and '__pycache__' not in path.parts:
                    archive.write(path, path.relative_to(root))
        for name in ('AGENTS.md', 'README.md', 'frontend/package.json', 'frontend/package-lock.json'):
            archive.write(root / name, name)
    record = dict(folder=str(folder), schema=schema, tables=summaries, columns=columns,
                  created_at=datetime.now(timezone.utc).isoformat(), model_calls=0)
    (folder / 'baseline.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
    (root / 'data/local/learning-experience-current.json').write_text(json.dumps(dict(folder=str(folder))), encoding='utf-8')
    print(json.dumps(dict(folder=str(folder), schema=schema, tables=len(summaries), integrity='ok')))


if __name__ == '__main__':
    main()
