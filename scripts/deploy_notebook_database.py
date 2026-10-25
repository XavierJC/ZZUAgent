"""Explicit backed-up additive migration; never replace or delete the live DB."""
import json,sqlite3
from datetime import datetime,timezone
from pathlib import Path
from eduagent.storage.sqlite import SQLiteRepository
from eduagent.storage.migrations import preserved_snapshot

def main():
    root=Path(__file__).resolve().parents[1];path=root/'data/local/eduagent.sqlite3'
    base=Path(json.loads((root/'data/local/notebook-rebuild-current.json').read_text())['folder'])
    baseline=json.loads((base/'baseline.json').read_text(encoding='utf-8'))
    assert json.loads((root/'data/evaluation/notebook-rebuild-migration-v1.json').read_text())['passed']
    assert json.loads((root/'data/evaluation/notebook-rebuild-http-v1.json').read_text())['passed']
    with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as db:
        before,columns=preserved_snapshot(db);version=db.execute('PRAGMA user_version').fetchone()[0]
        assert version==13,'Use this entry only once on the verified schema13 database'
        assert before==baseline['tables'],'Current facts changed since baseline; investigate and take a new verified baseline'
    with SQLiteRepository(path) as repo:
        report=repo.migration_report
        after,_=preserved_snapshot(repo.connection)
        assert preserved_snapshot(repo.connection,columns)[0]==before
        assert len(after)==50 and repo.connection.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert not repo.connection.execute('PRAGMA foreign_key_check').fetchall()
    with sqlite3.connect(report['backup']) as db:assert preserved_snapshot(db)[0]==before and db.execute('PRAGMA user_version').fetchone()[0]==13
    output=dict(passed=True,from_version=13,to_version=14,tables_before=45,tables_after=50,backup=report['backup'],original_45_table_summaries_unchanged=True,all_table_summaries=after,integrity=True,foreign_keys=True,migrated_at=datetime.now(timezone.utc).isoformat())
    (root/'data/evaluation/notebook-rebuild-production-migration-v1.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in output.items() if k!='all_table_summaries'},ensure_ascii=False))
if __name__=='__main__':main()
