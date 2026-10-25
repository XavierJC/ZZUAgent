"""Isolated synthetic UI fixture; disabled provider, never touches the live database."""
import argparse
import json
import shutil
import sys
import time
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT/'data/local/ui-browser-v1'

def app(frontend=None):
    from eduagent.api.app import create_app
    from eduagent.api.settings import APISettings
    from eduagent.agent.settings import AgentSettings
    return create_app(APISettings(data_dir=FOLDER/'data', db_path=FOLDER/'ui.sqlite3',
        agent=AgentSettings(enabled=False), frontend_dir=frontend or ROOT/'frontend/dist'))

def prepare():
    from fastapi.testclient import TestClient
    sys.path.insert(0,str(ROOT/'backend/tests'))
    from document_fixtures import pdf_bytes
    assert not (FOLDER/'ui.sqlite3').exists(), 'Use the existing fixture; do not overwrite it.'
    FOLDER.mkdir(parents=True,exist_ok=True)
    shutil.copytree(ROOT/'data',FOLDER/'data',ignore=shutil.ignore_patterns('local','reference-code','evaluation'))
    root='/api/v1/students/ui-demo'
    def command(**kw): return dict(request_id=str(uuid4()),**kw)
    with TestClient(app()) as client:
        def call(path,body=None,method=None,**kwargs):
            response=client.request(method or ('POST' if body is not None else 'GET'),path,json=body,**kwargs)
            assert response.is_success,(path,response.status_code,response.text[:500])
            return response.json()
        call('/api/v1/students',dict(student_id='ui-demo',goals=['gradient_descent','model_evaluation']))
        source=next(s for s in call(root+'/knowledge/sources')['items'] if s['source_id']=='gradient')
        ref=lambda s:{k:s[k] for k in ('source_type','source_id','source_version')}
        books=[]
        for title,description in [('梯度下降与优化','理解更新方向、学习率与收敛条件'),('模型评估与选择','区分准确率、精确率与召回率'),('复习：从损失到泛化','整理公式和容易混淆的概念')]:
            key=str(uuid4());call(root+'/notebooks',command(id=key,title=title,description=description));books.append(key)
        pdf=pdf_bytes(('Synthetic UI fixture: Gradient descent updates weights along the negative gradient.','Learning rate controls step size. Formula and table should be checked against this original page.','Precision and recall measure model evaluation performance.'))
        metadata=command(title='合成优化课件（仅界面验收）',local_rights_confirmed=True)
        response=client.post(root+'/documents',data={'metadata':json.dumps(metadata)},files={'file':('synthetic-ui.pdf',pdf,'application/pdf')})
        assert response.status_code==202,response.text
        document=response.json()
        for _ in range(100):
            detail=call(root+'/documents/'+document['id'])
            if detail['parse']['status'] not in ('pending','processing'):break
            time.sleep(.05)
        docref=ref(next(s for s in call(root+'/knowledge/sources')['items'] if s['source_id']==document['id']))
        questions=[]
        stems=[('梯度下降更新方向','single_choice'),('学习率与收敛','single_choice'),('Precision 与 Recall','single_choice'),('写出你的推导过程','short_answer'),('选择所有合适的检查方法','multiple_choice')]
        for title,kind in stems:
            payload=dict(stem=f'**{title}**\n\n合成验收题：考虑损失函数 $L(w)=w^2$，更新式为 $w_{{t+1}}=w_t-\\eta\\nabla L(w_t)$。\n\n| 项目 | 含义 |\n| --- | --- |\n| $\\eta$ | 学习率 |\n\n```python\nw = w - learning_rate * gradient\n```',question_type=kind,answer='A' if kind=='single_choice' else None,explanation='合成示例解析：先求导数，再检查更新方向。普通练习不更新BKT。')
            if kind in ('single_choice','multiple_choice'):payload['options']=[dict(key='A',text='沿负梯度方向，$-\\nabla L(w)$'),dict(key='B',text='沿正梯度方向，$+\\nabla L(w)$')]
            result=call(root+'/personal-bank/questions',command(payload=payload,status='practice',reviewed=True,confirm_answer=kind=='single_choice'))
            questions.append(dict(source_type='personal_question',source_id=result['question_id'],source_version='r1'))
        path=root+'/notebooks/'+books[0]
        call(path+'/sources',command(expected_revision=1,sources=[ref(source),docref,*questions]),method='PUT')
        run=call(path+'/questions',command(question='梯度下降沿什么方向更新？',sources=[ref(source)],mode='local',allow_personal_external=False,expected_revision=2))
        saved=call(path+'/runs/'+run['request_id']+'/note',{})
        result=dict(student='ui-demo',books=books,pdf=document['id'],questions=questions,note=saved['note_id'],real_model_calls=0,provider_enabled=False)
        (FOLDER/'fixture.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--serve',action='store_true');parser.add_argument('--port',type=int,default=8765);parser.add_argument('--frontend',type=Path);parser.add_argument('--folder',type=Path);args=parser.parse_args()
    if args.folder: FOLDER=args.folder.resolve()
    if args.serve:
        import uvicorn
        uvicorn.run(app(args.frontend),host='127.0.0.1',port=args.port,log_level='warning')
    else: prepare()
