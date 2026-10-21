"""Read-only deployment checks; no browser automation or provider requests."""

from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3
from urllib.parse import quote
from urllib.request import build_opener, ProxyHandler


def main():
    opener = build_opener(ProxyHandler({}))
    base = 'http://127.0.0.1:8000'
    def get(path):
        with opener.open(base + path, timeout=10) as response:
            return response.read(), {k.lower(): v for k, v in response.headers.items()}
    health = json.loads(get('/health')[0])
    schema = json.loads(get('/openapi.json')[0])
    index, headers = get('/')
    assert health['status'] == 'ok' and len(schema['paths']) == 23 and headers.get('cache-control') == 'no-store'
    assets = [s.decode() for s in re.findall(rb'(?:src|href)="(/assets/[^\"]+)"', index)]
    assert assets and all(get(path)[0] for path in assets)
    # Existing demo ID is read locally but not recorded in the public report.
    path = Path('data/local/eduagent.sqlite3').resolve()
    db = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
    try:
        owner = db.execute('SELECT id FROM students ORDER BY id LIMIT 1').fetchone()[0]
        assert db.execute('PRAGMA user_version').fetchone()[0] == 5
        assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    finally:
        db.close()
    prefix = '/api/v1/students/' + quote(owner, safe='')
    capabilities = json.loads(get(prefix + '/workbench/capabilities')[0])
    runs = json.loads(get(prefix + '/workbench/runs')[0])
    sources = json.loads(get(prefix + '/knowledge/sources')[0])
    report = dict(base_url=base, health_ok=True, schema=5, openapi_paths=len(schema['paths']),
        workbench_capabilities_ok=True, source_catalog_ok=bool(sources['items']), history_get_ok=isinstance(runs, list),
        index_cache_control=headers.get('cache-control'), index_sha256=sha256(index).hexdigest(), assets=assets, assets_http_ok=True,
        model_enabled=capabilities['model_enabled'], model_service=capabilities['provider'], model=capabilities['model'],
        real_model_calls=0, production_learning_writes=0, browser_visual_validation='not_performed')
    Path('data/evaluation/workbench-deployment-v1.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
