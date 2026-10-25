"""Rehearse additive 13->14 on a backup; retain new data before rollback."""
import json, os, sqlite3, subprocess, sys, zipfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from eduagent.storage import migrations
from eduagent.storage.sqlite import SQLiteRepository

def copy_db(source,target):
    with sqlite3.connect(source) as a,sqlite3.connect(target) as b:a.backup(b)

def verify():
    base=Path(json.loads(Path('data/local/notebook-rebuild-current.json').read_text())['folder'])
    folder=base/('migration-'+uuid4().hex[:8]);folder.mkdir()
    source=base/'before.sqlite3';upgrade=folder/'upgraded.sqlite3';copy_db(source,upgrade)
    with sqlite3.connect(source) as db:before,columns=migrations.preserved_snapshot(db)
    assert len(before)==45
    with SQLiteRepository(upgrade) as repo:
        report=repo.migration_report
        assert report['from_version']==13 and report['to_version']==14
        assert migrations.preserved_snapshot(repo.connection,columns)[0]==before
        assert len(migrations.table_names(repo.connection))==50
        assert repo.connection.execute('PRAGMA integrity_check').fetchone()[0]=='ok' and not repo.connection.execute('PRAGMA foreign_key_check').fetchall()
        student=repo.connection.execute('SELECT id FROM students LIMIT 1').fetchone()[0]
        new_id=str(uuid4())
        repo.connection.execute('INSERT INTO notebooks VALUES (?,?,?,?,?,?,?,?,?)',(new_id,student,'machine_learning','Synthetic new notebook','',1,0,'test','test'))
    retained=folder/'retained-schema14-with-new-data.sqlite3';copy_db(upgrade,retained)
    restored=folder/'restored-schema13-copy.sqlite3';copy_db(report['backup'],restored)
    with sqlite3.connect(retained) as db:assert db.execute('SELECT id FROM notebooks WHERE id=?',(new_id,)).fetchone()
    with sqlite3.connect(restored) as db:assert migrations.preserved_snapshot(db)[0]==before and db.execute('PRAGMA user_version').fetchone()[0]==13
    old=folder/'old-code';old.mkdir()
    with zipfile.ZipFile(base/'code-before.zip') as z:
        for name in z.namelist():
            if not name.startswith('backend/src/') or not name.endswith('.py'):continue
            dest=(old/name).resolve();assert dest.is_relative_to(old.resolve());dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(z.read(name))
    env=dict(os.environ,PYTHONPATH=str((old/'backend/src').resolve()))
    code='from eduagent.storage.sqlite import SQLiteRepository;import sys;r=SQLiteRepository(sys.argv[1],allow_upgrade=False);r.close()'
    accepted=subprocess.run([sys.executable,'-c',code,str(restored)],env=env,capture_output=True)
    rejected=subprocess.run([sys.executable,'-c',code,str(retained)],env=env,capture_output=True)
    assert accepted.returncode==0 and rejected.returncode!=0
    failure=folder/'failure.sqlite3';copy_db(source,failure)
    class FailCommit:
        def __init__(self,db):self.db=db
        def __getattr__(self,name):return getattr(self.db,name)
        def execute(self,sql,*args):
            if sql=='PRAGMA user_version=14':raise sqlite3.OperationalError('synthetic failure before commit')
            return self.db.execute(sql,*args)
    with sqlite3.connect(failure,isolation_level=None) as db:
        try:migrations.migrate(FailCommit(db),failure)
        except sqlite3.OperationalError:pass
        else:raise AssertionError('failed to inject migration error')
        assert db.execute('PRAGMA user_version').fetchone()[0]==13 and migrations.preserved_snapshot(db)[0]==before
    output=dict(passed=True,from_version=13,to_version=14,tables_before=45,tables_after=50,original_table_digests_preserved=True,backup_verified=True,integrity_and_foreign_keys=True,precommit_failure_rollback=True,old13_accepts_restored=True,old13_rejects14=True,rollback_retains_new_data=str(retained),rollback_copy=str(restored),production_writes=0,directory=str(folder),verified_at=datetime.now(timezone.utc).isoformat())
    Path('data/evaluation/notebook-rebuild-migration-v1.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(output,ensure_ascii=False))
if __name__=='__main__':verify()
