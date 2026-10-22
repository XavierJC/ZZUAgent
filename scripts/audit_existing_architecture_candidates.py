"""Read-only rule extraction on existing local parses; never publishes a graph."""
from datetime import datetime,timezone
import json
from pathlib import Path
import sqlite3
from uuid import uuid4
from eduagent.documents.architecture_candidates import extract

path=Path('data/local/eduagent.sqlite3').resolve();results=[]
with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as db:
    db.row_factory=sqlite3.Row;db.execute('pragma query_only=on')
    for row in db.execute('select * from course_documents where deleted_at is null'):
        doc=dict(row);ver=dict(db.execute('select * from document_versions where id=?',(doc['current_version_id'],)).fetchone())
        run=dict(db.execute('select * from document_parse_runs where id=?',(doc['current_parse_id'],)).fetchone())
        if run['mode']!='local' or run['status'] not in ('ready','partial','empty'):continue
        units=[]
        for row in db.execute('select * from document_units where run_id=? order by ordinal',(run['id'],)):
            unit=dict(row);unit['location']=json.loads(unit['location_json']);units.append(unit)
        value=extract(str(uuid4()),[(doc,ver,run,units)]);by_id={u['id']:u for u in units}
        assert all(by_id[e['unit_id']]['text'][e['start_offset']:e['end_offset']]==e['raw_text'] for e in value['evidence'])
        results.append(dict(format=ver['format'],units=len(units),chapter_candidates=len(value['graph']['chapters']),
            concept_candidates=len(value['graph']['concepts']),unclassified=len(value['unclassified']),evidence_offsets_match=True))
report=dict(passed=True,verified_at=datetime.now(timezone.utc).isoformat(),mode='actual saved local parse, read-only extraction in memory',
    documents=results,production_database_writes=0,model_calls=0,private_source_content_saved_in_report=False,accuracy='not manually evaluated')
Path('data/evaluation/phase4b2-existing-material-v1.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(report))
