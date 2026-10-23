"""Import one authorised PDF and recognise only pages 11,12,32. Never auto-retry a paid claim."""
import hashlib
import json
import time
from pathlib import Path
from uuid import uuid4
import httpx

root=Path.cwd();manifest=root/'data/local/pilot-real.json'
student='learner-8ab5e4c4';prefix=f'/api/v1/students/{student}/documents'
folder=Path('C:/Users/fengj/Desktop/机器学习课件')
path=next(p for p in folder.glob('*.pdf') if '模型评估' in p.name)
state=json.loads(manifest.read_text(encoding='utf-8')) if manifest.exists() else dict(student_id=student,file=str(path),file_hash=hashlib.sha256(path.read_bytes()).hexdigest(),pages=[11,12,32],upload_request=str(uuid4()))
def save():manifest.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
save()
with httpx.Client(base_url='http://127.0.0.1:8000',trust_env=False,timeout=40) as client:
    def get(p):
        r=client.get(p);r.raise_for_status();return r.json()
    if 'document_id' not in state:
        # Recover the original idempotent receipt before sending an upload.
        found=client.get(prefix+'/operations/'+state['upload_request'])
        if found.status_code==200:
            receipt=found.json();state['document_id']=receipt.get('document_id') or receipt.get('result',{}).get('document_id') or receipt.get('result',{}).get('id')
        if not state.get('document_id'):
            meta=dict(request_id=state['upload_request'],title=path.stem,material_role='teaching_slides',source_note='用户提供的本机课程资料；模型评估试点；尚待负责人审核',local_rights_confirmed=True)
            with path.open('rb') as f:r=client.post(prefix,data={'metadata':json.dumps(meta,ensure_ascii=False)},files={'file':(path.name,f,'application/pdf')})
            r.raise_for_status();state['document_id']=r.json()['id']
        save()
    document=get(prefix+'/'+state['document_id'])
    while document['parse']['status'] in ('pending','processing'):
        time.sleep(1);document=get(prefix+'/'+state['document_id'])
    assert document['parse']['status'] in ('ready','partial','empty')
    state.setdefault('local_run_id',document['parse']['id']);state['version_id']=document['version']['id'];save()
    if 'vision_request' not in state:
        state['vision_request']=str(uuid4());state['vision_intent_recorded']=True;save()
        r=client.post(prefix+'/'+state['document_id']+'/vision',json=dict(request_id=state['vision_request'],expected_revision=document['revision'],version_id=state['version_id'],pages=state['pages'],consent_external=True))
        r.raise_for_status();state['vision_run_id']=r.json()['id'];save()
    elif 'vision_run_id' not in state:
        receipt=client.get(prefix+'/operations/'+state['vision_request'])
        if receipt.status_code!=200:raise RuntimeError('Paid intent unresolved; no automatic resend')
        runs=get(prefix+'/'+state['document_id']+'/parse-runs')
        selected=[r for r in runs if r['mode']=='vision']
        assert len(selected)==1
        state['vision_run_id']=selected[0]['id'];save()
    run=get(prefix+'/'+state['document_id']+'/parse-runs/'+state['vision_run_id'])
    while run['status'] in ('pending','processing'):
        time.sleep(2);run=get(prefix+'/'+state['document_id']+'/parse-runs/'+state['vision_run_id'])
    state['vision_result']={k:run.get(k) for k in ('status','model_calls','error_code','usage','model','warnings')};save()
    print(json.dumps(dict(document_id=state['document_id'],pages=state['pages'],result=state['vision_result']),ensure_ascii=True))
