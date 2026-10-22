"""Explicit schema8→9 audit with retained rollback copies. Stop writes first."""
import argparse,hashlib,json,os,shutil,sqlite3,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path,PurePosixPath
from uuid import uuid4
from zipfile import ZipFile
from eduagent.storage.migrations import preserved_snapshot,table_names
from eduagent.storage.sqlite import SQLiteRepository


def audit(output):
    root=Path.cwd();db_path=root/'data/local/eduagent.sqlite3'
    folder=Path(json.loads((root/'data/local/phase4c-current.json').read_text())['folder'])
    baseline=json.loads((folder/'before.json').read_text(encoding='utf-8'))
    archive=folder/'code-before.zip';assert hashlib.sha256(archive.read_bytes()).hexdigest()==baseline['archive_sha256']
    with sqlite3.connect(db_path.as_uri()+'?mode=ro',uri=True) as db:
        assert db.execute('pragma user_version').fetchone()[0]==8
        before,columns=preserved_snapshot(db);assert len(before)==27
        assert not db.execute("select id from document_parse_runs where status in ('pending','processing')").fetchall(),'unfinished document jobs; stop and inspect before deployment'
        assert not db.execute("select request_id from workbench_runs where status='running'").fetchall()
        assert not db.execute("select request_id from study_guide_runs where status='running'").fetchall()
        assert before==baseline['facts'],'database changed since baseline; audit before proceeding'
    with SQLiteRepository(db_path) as repo:
        migration=repo.migration_report;assert migration['from_version']==8 and migration['to_version']==9
        assert preserved_snapshot(repo.connection,columns)[0]==before
        assert len(table_names(repo.connection))==34 and not repo.connection.execute('pragma foreign_key_check').fetchall()
        assert repo.connection.execute('pragma integrity_check').fetchone()[0]=='ok'
    backup=Path(migration['backup']);rollback=root/'data/local'/('phase4c-rollback-audit-'+uuid4().hex[:8]);rollback.mkdir()
    legacy=rollback/'legacy';legacy.mkdir()
    with ZipFile(archive) as zip:
        for item in zip.infolist():
            if item.is_dir() or not item.filename.startswith('backend/src/eduagent/'):continue
            part=PurePosixPath(item.filename);target=legacy.joinpath(*part.parts).resolve()
            assert target.is_relative_to(legacy) and not part.is_absolute() and '..' not in part.parts
            target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(zip.read(item))
    old=rollback/'restored-schema8.sqlite3';shutil.copy2(backup,old)
    new=rollback/'preserved-schema9.sqlite3'
    with sqlite3.connect(db_path) as current,sqlite3.connect(new) as copy:current.backup(copy)
    code="""import sys
from eduagent.storage.sqlite import SQLiteRepository
if sys.argv[2]=='accept':
 with SQLiteRepository(sys.argv[1]) as r: assert r.connection.execute('pragma user_version').fetchone()[0]==8
else:
 try:SQLiteRepository(sys.argv[1])
 except ValueError as e:assert '9' in str(e)
 else:raise AssertionError('legacy code accepted schema9')
print('ok')
"""
    env={k:v for k,v in os.environ.items() if k in ('SYSTEMROOT','SystemRoot','WINDIR','TEMP','TMP','PATH')};env['PYTHONPATH']=str(legacy/'backend/src')
    for path,mode in ((old,'accept'),(new,'reject')):
        p=subprocess.run([sys.executable,'-c',code,str(path),mode],cwd=rollback,env=env,capture_output=True,text=True,timeout=20,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        assert p.returncode==0,(mode,p.stderr[:200])
    with sqlite3.connect(old) as copy:assert preserved_snapshot(copy,columns)[0]==before
    assert all((root/p).is_file() and hashlib.sha256((root/p).read_bytes()).hexdigest()==value for p,value in baseline['original_files'].items())
    assert all((root/p).is_file() and hashlib.sha256((root/p).read_bytes()).hexdigest()==value for p,value in baseline['data_files'].items())
    report=dict(passed=True,verified_at=datetime.now(timezone.utc).isoformat(),migration=migration,old_tables=27,new_tables=34,
        original_table_data_unchanged=True,original_files_unchanged=True,original_evaluations_and_course_files_unchanged=True,
        backup_sha256=hashlib.sha256(backup.read_bytes()).hexdigest(),code_archive=str(archive),code_archive_sha256=baseline['archive_sha256'],
        old_code_accepts_restored8=True,old_code_rejects9=True,rollback_directory=str(rollback),upgraded_copy=str(new),
        live_database_overwritten=False,format_constraint_change='document_versions rebuilt transactionally to allow PNG/JPEG/WebP; original rows/columns preserved',
        integrity='ok',foreign_key_errors=0,real_model_calls=0)
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(dict(passed=True,old_tables=27,new_tables=34,backup=str(backup),report=str(output))))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=Path('data/evaluation/phase4c-migration-v1.json'));a=p.parse_args();audit(a.output)
