"""Read-only localhost deployment audit; no browser or provider requests."""

from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3
from urllib.parse import quote
from urllib.request import build_opener, ProxyHandler
from eduagent.storage.migrations import preserved_snapshot


def main():
    base='http://127.0.0.1:8000'; opener=build_opener(ProxyHandler({}))
    def get(path):
        with opener.open(base+path,timeout=10) as response:
            return response.read(),{k.lower():v for k,v in response.headers.items()}
    health=json.loads(get('/health')[0]); schema=json.loads(get('/openapi.json')[0]); index,headers=get('/')
    assert health['status']=='ok' and len(schema['paths'])==29 and headers['cache-control']=='no-store'
    assets=[value.decode() for value in re.findall(rb'(?:src|href)="(/assets/[^\"]+)"',index)]
    assert assets and all(get(path)[0] for path in assets)
    db=sqlite3.connect(Path('data/local/eduagent.sqlite3').resolve().as_uri()+'?mode=ro',uri=True)
    try:
        db.execute('PRAGMA query_only=ON')
        owner=db.execute('SELECT id FROM students ORDER BY id LIMIT 1').fetchone()[0]
        assert db.execute('PRAGMA user_version').fetchone()[0]==6
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok' and not db.execute('PRAGMA foreign_key_check').fetchall()
        tables=preserved_snapshot(db)[0]
    finally:db.close()
    migration=json.loads(Path('data/evaluation/phase4a-migration-v1.json').read_text(encoding='utf8'))
    assert all(tables[k]==v for k,v in migration['facts'].items())
    prefix='/api/v1/students/'+quote(owner,safe='')
    reports=json.loads(get(prefix+'/self-assessments/latest')[0]); guidance=json.loads(get(prefix+'/learning-guidance')[0])
    guides=json.loads(get(prefix+'/study-guides')[0]); capabilities=json.loads(get(prefix+'/workbench/capabilities')[0])
    assert reports['assessment_revision']==guidance['assessment_revision'] and len(guidance['items'])==5
    report=dict(base_url=base,schema=6,openapi_paths=29,health_ok=True,assets=assets,assets_http_ok=True,
        index_sha256=sha256(index).hexdigest(),index_cache_control=headers['cache-control'],
        self_latest_and_guidance_read_ok=True,guide_history_read_ok=isinstance(guides,list),original_twelve_tables_equal=True,
        model_service=capabilities['provider'],model=capabilities['model'],model_enabled=capabilities['model_enabled'],
        real_model_calls=0,production_learning_writes=0,browser_manual_validation='not_performed')
    Path('data/evaluation/phase4a-deployment-v1.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(report))


if __name__=='__main__':main()
