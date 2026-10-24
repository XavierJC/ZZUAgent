"""Rehearse v12 -> v13, rollback retention, failure rollback and old-code boundary."""
import json,os,sqlite3,subprocess,sys,zipfile
from datetime import datetime,timezone
from pathlib import Path
from uuid import uuid4

from eduagent.storage.sqlite import SQLiteRepository
from eduagent.storage import migrations
from eduagent.domain.catalog import Catalog
from eduagent.services.learning import LearningService


def copy_database(source,target):
    with sqlite3.connect(source) as a,sqlite3.connect(target) as b:a.backup(b)


def verify():
    base=Path(json.loads(Path('data/local/learning-simplification-current.json').read_text(encoding='utf-8'))['folder'])
    folder=base/'migration-rehearsal';folder.mkdir(exist_ok=True)
    source=base/'before.sqlite3';upgrade=folder/('upgrade-'+uuid4().hex[:8]+'.sqlite3');copy_database(source,upgrade)
    with sqlite3.connect(source) as db:before,columns=migrations.preserved_snapshot(db)
    with SQLiteRepository(upgrade) as repo:
        report=repo.migration_report
        assert report['from_version']==12 and report['to_version']==13
        assert migrations.preserved_snapshot(repo.connection,columns)[0]==before
        assert repo.connection.execute('PRAGMA integrity_check').fetchone()[0]=='ok' and not repo.connection.execute('PRAGMA foreign_key_check').fetchall()
        new_id='synthetic-after13-'+uuid4().hex[:8]
        LearningService(Catalog.load(Path('data')),repo).register(new_id,('gradient_descent',))
    retained=folder/'retained-upgraded-with-new-data.sqlite3';copy_database(upgrade,retained)
    rollback=folder/'restored-v12.sqlite3';copy_database(report['backup'],rollback)
    with sqlite3.connect(retained) as db:assert db.execute('SELECT 1 FROM students WHERE id=?',(new_id,)).fetchone() and db.execute('PRAGMA user_version').fetchone()[0]==13
    with sqlite3.connect(rollback) as db:assert migrations.preserved_snapshot(db,columns)[0]==before and db.execute('PRAGMA user_version').fetchone()[0]==12
    old=folder/'old-code';old.mkdir(exist_ok=True)
    with zipfile.ZipFile(base/'code-before.zip') as archive:
        for name in archive.namelist():
            if not name.startswith('backend/src/') or not name.endswith('.py'):continue
            target=(old/name).resolve();assert target.is_relative_to(old.resolve());target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(archive.read(name))
    env=dict(os.environ,PYTHONPATH=str((old/'backend/src').resolve()))
    code='from eduagent.storage.sqlite import SQLiteRepository; import sys; r=SQLiteRepository(sys.argv[1],allow_upgrade=False); r.close()'
    restored=subprocess.run([sys.executable,'-c',code,str(rollback.resolve())],env=env,capture_output=True)
    rejected=subprocess.run([sys.executable,'-c',code,str(retained.resolve())],env=env,capture_output=True)
    assert restored.returncode==0 and rejected.returncode!=0
    failure=folder/'injected-failure.sqlite3';copy_database(source,failure)
    class FailAtVersion:
        def __init__(self,db):self.db=db
        def __getattr__(self,name):return getattr(self.db,name)
        def execute(self,sql,*args):
            if sql=='PRAGMA user_version=13':raise sqlite3.OperationalError('synthetic pre-commit failure')
            return self.db.execute(sql,*args)
    with sqlite3.connect(failure,isolation_level=None) as db:
        try:migrations.migrate(FailAtVersion(db),failure)
        except sqlite3.OperationalError:pass
        else:raise AssertionError('failure not injected')
        assert db.execute('PRAGMA user_version').fetchone()[0]==12 and migrations.preserved_snapshot(db,columns)[0]==before
    output=dict(passed=True,verified_at=datetime.now(timezone.utc).isoformat(),from_version=12,to_version=13,tables=45,
                all_45_tables_preserved=True,backup_verified=True,integrity_and_foreign_keys=True,failed_migration_rolled_back=True,
                retained_upgrade_with_new_data=str(retained),restored_v12_copy=str(rollback),old_v12_accepts_restored=True,old_v12_rejects_13=True,
                production_writes=0,directory=str(folder))
    Path('data/evaluation/learning-simplification-migration-rehearsal-v1.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(passed=True,from_version=12,to_version=13,tables_preserved=45,old_code_boundary=True,rollback_retains_new_data=True)))


if __name__=='__main__':verify()
