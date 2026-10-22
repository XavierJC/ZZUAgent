"""Explicit additive schema6→7 migration and rollback audit. Stop API first.

Never copies an old backup over the live database. Legacy-code tests use copies.
"""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sqlite3
import subprocess
import sys
from uuid import uuid4
from zipfile import ZipFile

from eduagent.storage.migrations import preserved_snapshot, table_names
from eduagent.storage.sqlite import SQLiteRepository


def audit(db_path, before_dir, output):
    db_path=db_path.resolve(); before_dir=before_dir.resolve()
    baseline=json.loads((before_dir/'before.json').read_text(encoding='utf-8-sig'))
    archive=before_dir/'code-before.zip'
    assert sha256(archive.read_bytes()).hexdigest()==baseline['backup_sha256']
    with sqlite3.connect(db_path.as_uri()+'?mode=ro',uri=True) as db:
        assert db.execute('PRAGMA user_version').fetchone()[0]==6, 'only explicit schema6 upgrade supported here'
        before,columns=preserved_snapshot(db)
        assert len(before)==15 and db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert not db.execute('PRAGMA foreign_key_check').fetchall()
    with SQLiteRepository(db_path) as repo:
        migration=repo.migration_report
        assert migration['from_version']==6 and migration['to_version']==7
        assert preserved_snapshot(repo.connection,columns)[0]==before
        assert len(table_names(repo.connection))==21
        assert repo.connection.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert not repo.connection.execute('PRAGMA foreign_key_check').fetchall()
    backup=Path(migration['backup'])
    directory=db_path.parent/('phase4b1-rollback-audit-'+uuid4().hex[:8]); directory.mkdir()
    source=directory/'legacy'; source.mkdir()
    with ZipFile(archive) as zip:
        for item in zip.infolist():
            key=PurePosixPath(item.filename)
            if not item.filename.startswith('backend/src/eduagent/') or item.is_dir(): continue
            target=source.joinpath(*key.parts).resolve()
            assert target.is_relative_to(source) and not key.is_absolute() and '..' not in key.parts
            target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(zip.read(item))
    old_copy=directory/'restored-schema6.sqlite3'; shutil.copy2(backup,old_copy)
    new_copy=directory/'preserved-schema7.sqlite3'
    with sqlite3.connect(db_path) as current, sqlite3.connect(new_copy) as preserved: current.backup(preserved)
    code='''import sys
from eduagent.storage.sqlite import SQLiteRepository
if sys.argv[2]=='accept':
    with SQLiteRepository(sys.argv[1]) as repo:
        assert repo.connection.execute('PRAGMA user_version').fetchone()[0]==6
else:
    try: SQLiteRepository(sys.argv[1])
    except ValueError as exc: assert '7' in str(exc)
    else: raise AssertionError('old service accepted schema7')
print('ok')
'''
    env=dict(os.environ); env['PYTHONPATH']=str(source/'backend/src')
    for path,expect in ((old_copy,'accept'),(new_copy,'reject')):
        completed=subprocess.run([sys.executable,'-c',code,str(path),expect],cwd=directory,env=env,
            capture_output=True,text=True,timeout=15,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        assert completed.returncode==0,(expect,completed.stderr[:250])
    with sqlite3.connect(old_copy) as old:
        assert preserved_snapshot(old,columns)[0]==before
    root=Path.cwd(); data_ok=all((root/name).is_file() and sha256((root/name).read_bytes()).hexdigest()==digest
                              for name,digest in baseline['data_files'].items())
    assert data_ok,'pre-existing non-local data changed'
    output.write_text(json.dumps({'passed':True,'verified_at':datetime.now(timezone.utc).isoformat(),
        'migration':migration,'backup_sha256':sha256(backup.read_bytes()).hexdigest(),'code_backup':str(archive),
        'code_backup_sha256':baseline['backup_sha256'],'original_table_count':15,'current_table_count':21,
        'original_tables_match':True,'integrity':'ok','foreign_key_errors':0,'pre_existing_data_files_unchanged':data_ok,
        'pre_existing_data_file_count':len(baseline['data_files']),'rollback_audit_directory':str(directory),
        'legacy_accepts_restored_schema6':True,'legacy_rejects_schema7':True,'live_database_overwritten':False,
        'new_data_retention':'Preserve upgraded DB, its WAL/SHM when applicable and document directory; never overwrite with schema6.'},
        ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'passed':True,'from':6,'to':7,'preserved_tables':15,'backup':str(backup),'report':str(output)}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db',type=Path,required=True); parser.add_argument('--before',type=Path,required=True)
    parser.add_argument('--output',type=Path,default=Path('data/evaluation/phase4b1-migration-v1.json')); args=parser.parse_args()
    audit(args.db,args.before,args.output)
