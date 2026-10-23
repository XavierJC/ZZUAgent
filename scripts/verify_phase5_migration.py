"""Explicit additive schema10→11; stop the old API before running on live DB."""
import argparse,hashlib,json,sqlite3,shutil,subprocess,sys,os
from pathlib import Path,PurePosixPath
from zipfile import ZipFile
from uuid import uuid4
from datetime import datetime,timezone
from eduagent.storage.migrations import preserved_snapshot,table_names
from eduagent.storage.sqlite import SQLiteRepository

def audit(path,output):
    root=Path.cwd();folder=Path(json.loads((root/'data/local/phase5-current.json').read_text())['folder'])
    baseline=json.loads((folder/'before.json').read_text(encoding='utf-8'));archive=folder/'code-before.zip'
    assert hashlib.sha256(archive.read_bytes()).hexdigest()==baseline['archive_sha256']
    with sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True) as db:
        assert db.execute('pragma user_version').fetchone()[0]==10
        before,columns=preserved_snapshot(db);assert len(before)==36
        for table,field,states in [('document_parse_runs','status',('pending','processing')),('workbench_runs','status',('running',)),('study_guide_runs','status',('running',)),('question_extraction_tasks','status',('running',))]:
            assert not db.execute('SELECT 1 FROM '+table+' WHERE '+field+' IN ('+','.join('?' for _ in states)+')',states).fetchone(),'unfinished request; inspect before deployment'
        changed_since_start=[t for t in before if before[t]!=baseline['facts'][t]]
        # New user activity is retained, never reverted to the start-of-work copy.
    with SQLiteRepository(path) as repo:
        migration=repo.migration_report;assert migration['from_version']==10 and migration['to_version']==11
        assert preserved_snapshot(repo.connection,columns)[0]==before
        assert len(table_names(repo.connection))==43
        assert repo.connection.execute('pragma integrity_check').fetchone()[0]=='ok' and not repo.connection.execute('pragma foreign_key_check').fetchall()
    directory=root/'data/local'/('phase5-rollback-'+uuid4().hex[:8]);directory.mkdir();legacy=directory/'legacy';legacy.mkdir()
    with ZipFile(archive) as z:
        for item in z.infolist():
            if item.is_dir() or not item.filename.startswith('backend/src/eduagent/'):continue
            part=PurePosixPath(item.filename);target=legacy.joinpath(*part.parts).resolve()
            assert target.is_relative_to(legacy) and '..' not in part.parts
            target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(z.read(item))
    old=directory/'restored-schema10.sqlite3';shutil.copy2(migration['backup'],old)
    new=directory/'preserved-schema11.sqlite3'
    with sqlite3.connect(path) as source,sqlite3.connect(new) as target:source.backup(target)
    code='''import sys
from eduagent.storage.sqlite import SQLiteRepository
if sys.argv[2]=='accept':
 with SQLiteRepository(sys.argv[1]) as r:assert r.connection.execute('pragma user_version').fetchone()[0]==10
else:
 try:SQLiteRepository(sys.argv[1])
 except ValueError:pass
 else:raise AssertionError('old code accepted schema11')
print('ok')'''
    env={k:v for k,v in os.environ.items() if k in ('SYSTEMROOT','SystemRoot','WINDIR','TEMP','TMP','PATH')};env['PYTHONPATH']=str(legacy/'backend/src')
    for db,mode in ((old,'accept'),(new,'reject')):
        result=subprocess.run([sys.executable,'-c',code,str(db),mode],cwd=directory,env=env,capture_output=True,text=True,timeout=20,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        assert result.returncode==0,(mode,result.stderr[:200])
    with sqlite3.connect(old) as db:assert preserved_snapshot(db,columns)[0]==before
    for group in ('original_files','data_files'):
        assert all((root/p).is_file() and hashlib.sha256((root/p).read_bytes()).hexdigest()==checksum for p,checksum in baseline[group].items()),group+' changed'
    formal_files={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [*(root/'data').glob('*.json'),*(root/'data/materials').rglob('*')] if p.is_file()}
    report=dict(passed=True,verified_at=datetime.now(timezone.utc).isoformat(),migration=migration,old_tables=36,new_tables=43,original_table_summaries=before,
        original_columns=columns,original_tables_unchanged=True,original_files_unchanged=True,original_evaluations_unchanged=True,
        changed_since_start_retained=changed_since_start,code_archive=str(archive),rollback_directory=str(directory),
        restored_old_copy=str(old),retained_upgraded_copy=str(new),old_code_accepts_restored10=True,old_code_rejects11=True,
        live_database_overwritten=False,integrity='ok',foreign_key_errors=0,backup_sha256=hashlib.sha256(Path(migration['backup']).read_bytes()).hexdigest(),formal_files=formal_files,
        recovery='Stop API; retain schema11 DB and documents, run archived schema10 code against restored-schema10 copy using a separate DB path. New tasks/drafts remain in retained schema11 copy; never overwrite it.')
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(dict(passed=True,backup=migration['backup'],rollback=str(directory),changed_since_start=changed_since_start,report=str(output))))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--db',type=Path,required=True);p.add_argument('--output',type=Path,default=Path('data/evaluation/phase5-migration-v1.json'));a=p.parse_args();audit(a.db,a.output)
