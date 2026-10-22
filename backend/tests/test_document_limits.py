"""Exercise actual OS jobs with small synthetic programs, never real documents."""
import json
import os
from pathlib import Path
from threading import Event

import pytest
from eduagent.documents import limits
from eduagent.documents.models import DocumentError


def replace_worker(monkeypatch, tmp_path, code):
    script = tmp_path / 'synthetic_worker.py'
    script.write_text('import sys, json, os\nsys.stdin.readline()\n' + code, encoding='utf8')
    popen = limits.subprocess.Popen
    def launch(args, **kwargs):
        return popen([args[0], str(script), *args[-2:]], **kwargs)
    monkeypatch.setattr(limits.subprocess, 'Popen', launch)
    return tmp_path / 'manifest.json', tmp_path / 'output.json'


@pytest.mark.skipif(os.name != 'nt', reason='Windows Job Object specific')
@pytest.mark.parametrize('kind', ['memory', 'cpu', 'deadline'])
def test_real_resource_limit_stops_synthetic_process(monkeypatch, tmp_path, kind):
    job = limits.WindowsJob
    monkeypatch.setattr(limits, 'WindowsJob', lambda process: job(process, memory_mb=96, cpu_seconds=1))
    code = {'memory': 'x = bytearray(256 * 1024 * 1024)\n', 'cpu': 'while True: pass\n',
            'deadline': 'import time\ntime.sleep(30)\n'}[kind]
    manifest, output = replace_worker(monkeypatch, tmp_path, code)
    with pytest.raises(DocumentError) as failure:
        limits.run_worker(manifest, output, timeout=.2 if kind == 'deadline' else 8)
    assert failure.value.code == ('parse_timeout' if kind == 'deadline' else 'parse_resource_limit')


def test_worker_does_not_inherit_model_credentials(monkeypatch, tmp_path):
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'synthetic-secret-only')
    manifest, output = replace_worker(monkeypatch, tmp_path,
        'assert "DEEPSEEK_API_KEY" not in os.environ\n'
        'open(sys.argv[2], "w").write(json.dumps({"safe":True}))\n')
    assert limits.run_worker(manifest, output)['safe']


def test_coordinator_lock_prevents_a_second_parser(tmp_path):
    first = limits.WorkerLock(tmp_path)
    try:
        with pytest.raises(ValueError, match='单worker'): limits.WorkerLock(tmp_path)
    finally: first.close()
    limits.WorkerLock(tmp_path).close()
