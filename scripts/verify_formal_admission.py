"""Real loopback HTTP checks against an isolated admitted DB, no paid providers."""
import argparse
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from uuid import uuid4

from eduagent.services.formal_admission import KEY


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():raise ValueError('拒绝覆盖旧验证证据')
    with sqlite3.connect(args.db) as db:
        record=json.loads(db.execute('SELECT value FROM metadata WHERE key=?',(KEY,)).fetchone()[0])
        scopes={r[0] for r in db.execute('SELECT DISTINCT student_id FROM personal_questions')}
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    env=dict(os.environ,EDUAGENT_DB_PATH=str(args.db.resolve()),EDUAGENT_AGENT_ENABLED='false',EDUAGENT_RETRIEVAL_ENABLED='false',EDUAGENT_DOCUMENT_VISION_ENABLED='false')
    process=subprocess.Popen([sys.executable,'-m','uvicorn','eduagent.api.app:create_app','--factory','--host','127.0.0.1','--port',str(port),'--log-level','warning'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    root=f'http://127.0.0.1:{port}'
    checks=[]
    def request(path,body=None):
        payload=json.dumps(body).encode() if body is not None else None
        with urlopen(Request(root+path,data=payload,headers={'Content-Type':'application/json'}),timeout=10) as response:return json.load(response)
    def check(name,value):
        assert value,name
        checks.append(dict(name=name,passed=True))
    try:
        for _ in range(100):
            if process.poll() is not None:raise RuntimeError('隔离HTTP服务启动失败：'+process.stderr.read().decode(errors='replace')[-1200:])
            try:health=request('/health');break
            except (OSError,TimeoutError):time.sleep(.1)
        else:raise RuntimeError('隔离HTTP服务未就绪')
        check('shared_bank_40_ai_checked',health['question_count']==40 and health['ai_checked_count']==40)
        learner='formal-http-'+uuid4().hex[:12]
        request('/api/v1/students',dict(student_id=learner,goals=['linear_regression_loss']))
        with sqlite3.connect(args.db) as db:before=db.execute('SELECT revision FROM students WHERE id=?',(learner,)).fetchone()[0]
        for _ in range(2):request('/api/v1/students/'+learner+'/teaching-sessions')
        with sqlite3.connect(args.db) as db:after=db.execute('SELECT revision FROM students WHERE id=?',(learner,)).fetchone()[0]
        check('refresh_does_not_score',before==after==0)
        ids=[]
        for i in range(5):
            decision=request('/api/v1/students/'+learner+'/next',{})
            question=decision['question'];ids.append(question['id'])
            check('answer_hidden_'+str(i),'answer' not in question and 'explanation' not in question)
            correct=next(q['answer'] for q in record['shared_questions'] if q['id']==question['id'])
            answer=next(k for k in question['options'] if k!=correct) if i<2 else correct
            body=dict(decision_id=decision['decision_id'],answer=answer,event_id=str(uuid4()))
            result=request('/api/v1/students/'+learner+'/answers',body)
            replay=request('/api/v1/students/'+learner+'/answers',body)
            check('score_and_idempotency_'+str(i),result['bank_version']==record['bank_version'] and replay['replayed'])
        check('exhaustion_resolved_without_repetition',ids==['lr_01','lr_02','lr_03','lr_04','lr_05'])
        mastery=request('/api/v1/students/'+learner+'/mastery')
        check('five_real_submissions_update_revision_once',mastery['revision']==5)
        check('finish_after_recovery',request('/api/v1/students/'+learner+'/next',{})['action']=='finish')
        for owner in scopes:
            info=request('/api/v1/students/'+owner+'/teaching-sessions')['assessment_bank']
            private=sum(e['student_id']==owner for e in record['personal_questions'])
            check('owner_scope_count_'+str(len(checks)),info['question_count']==40+private and info['personal_count']==private)
        result=dict(checks=checks,passed=len(checks),real_http=True,paid_model_calls=0,simulated_provider_calls=0,
                    isolated_database=True,shared_questions=40,private_admissions=len(record['personal_questions']))
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(dict(passed=len(checks),paid_model_calls=0,shared_questions=40,private_admissions=len(record['personal_questions']))))
    finally:
        process.terminate()
        try:process.wait(timeout=10)
        except subprocess.TimeoutExpired:process.kill();process.wait()


if __name__=='__main__':main()
