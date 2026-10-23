"""Read-only local deployment checks; never allocate questions or invoke models."""
import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
from urllib.request import ProxyHandler, build_opener

from eduagent.storage.migrations import preserved_snapshot, table_names


root = Path.cwd()
audit = json.loads((root / 'data/evaluation/phase5-migration-v1.json').read_text(encoding='utf-8'))
folder = Path(json.loads((root / 'data/local/phase5-current.json').read_text())['folder'])
baseline = json.loads((folder / 'before.json').read_text(encoding='utf-8'))
opener = build_opener(ProxyHandler({}))


def get(path):
    with opener.open('http://127.0.0.1:8000' + path, timeout=10) as response:
        return response.read()


assert json.loads(get('/health'))['status'] == 'ok'
assert len(json.loads(get('/openapi.json'))['paths']) == 83
assets = re.findall(rb'(?:src|href)="(/assets/[^"]+)"', get('/'))
assert assets and all(get(path.decode()) for path in assets)
public = json.loads(get('/api/v1/courses/published'))['items']
assert len(public) == 1 and public[0]['kind'] == 'demo' and public[0]['usable']
assert 'review_questions' not in public[0]
assert len(public[0]['question_versions']) == 10 and len(public[0]['knowledge']) == 5
with sqlite3.connect(root / 'data/local/eduagent.sqlite3') as db:
    assert db.execute('pragma user_version').fetchone()[0] == 11
    assert len(table_names(db)) == 43
    assert preserved_snapshot(db, audit['original_columns'])[0] == audit['original_table_summaries']
    assert db.execute('pragma integrity_check').fetchone()[0] == 'ok'
    assert not db.execute('pragma foreign_key_check').fetchall()
    new_counts = {table: db.execute('select count(*) from ' + table).fetchone()[0] for table in (
        'course_release_drafts', 'course_releases', 'teaching_sessions', 'teaching_decisions',
        'teaching_events', 'teaching_explanations', 'course_workflow_operations')}
    assert new_counts == dict.fromkeys(new_counts, 0) | {'course_releases': 1}
    students = [row[0] for row in db.execute('select id from students order by id')]
    counts = {table: db.execute('select count(*) from ' + table).fetchone()[0] for table in (
        'personal_questions', 'notes', 'course_documents', 'attempts', 'decisions')}
    # Counts describe old saved calls. They are not Phase 5 model requests.
    historical_calls = {table: db.execute('select coalesce(sum(model_calls),0) from ' + table).fetchone()[0]
                        for table in ('document_parse_runs', 'workbench_runs', 'study_guide_runs', 'question_extraction_tasks')}
for student in students:
    prefix = '/api/v1/students/' + quote(student, safe='')
    assert json.loads(get(prefix + '/teaching-sessions'))['session'] is None
    assert json.loads(get(prefix + '/teaching-explanations'))['items'] == []
    for item in json.loads(get(prefix + '/teaching-history'))['items']:
        assert item['course_provenance']['release_id'] is None
        assert item['course_provenance']['allocation_origin'] == 'legacy_unbound'
    assert len(json.loads(get(prefix + '/course-releases'))['items']) == 1
    get(prefix + '/current-decision')  # Read-only even for an unanswered old allocation.
with sqlite3.connect(root / 'data/local/eduagent.sqlite3') as db:
    assert preserved_snapshot(db, audit['original_columns'])[0] == audit['original_table_summaries']
    assert {table: db.execute('select count(*) from ' + table).fetchone()[0] for table in new_counts} == new_counts
for path, checksum in audit['formal_files'].items():
    assert hashlib.sha256((root / path).read_bytes()).hexdigest() == checksum
for group in ('original_files', 'data_files'):
    assert all(hashlib.sha256((root / path).read_bytes()).hexdigest() == checksum
               for path, checksum in baseline[group].items())
protected = [
    'backend/src/eduagent/services/learning.py',
    'backend/src/eduagent/domain/bkt.py',
]
# Check the actual immutable source files present in the original archive.
from zipfile import ZipFile
with ZipFile(folder / 'code-before.zip') as archive:
    protected += [name for name in archive.namelist()
                  if name.startswith('backend/src/eduagent/') and
                  (name.endswith('/policy.py') or name.endswith('/scoring.py'))]
    protected = [name for name in protected if name in archive.namelist()]
    for name in protected:
        assert (root / name).read_bytes() == archive.read(name), name
report = dict(
    passed=True, verified_at=datetime.now(timezone.utc).isoformat(), schema=11, tables=43, api_paths=83,
    assets=[path.decode() for path in assets], original_36_tables_unchanged=True,
    original_files_unchanged=True, original_evaluations_unchanged=True, formal_files_unchanged=True,
    protected_learning_sources=protected, existing_counts=counts, new_table_counts=new_counts,
    old_students_read_only_checked=len(students), old_history_remains_unbound=True,
    historical_saved_model_calls=historical_calls, phase5_real_model_calls=0,
    browser_manual='not_performed',
    browser_limitation='Earlier browser access to localhost was denied; no bypass attempted.',
    integrity='ok', foreign_key_errors=0,
)
output = root / 'data/evaluation/phase5-deployment-v1.json'
output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(dict(passed=True, schema=11, tables=43, api_paths=83,
                      counts=counts, real_model_calls=0, report=str(output))))
