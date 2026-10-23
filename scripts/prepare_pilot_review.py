"""Prepare real, unreviewed pilot material. No paid calls or formal attempts."""
import json,time,sqlite3,hashlib
from pathlib import Path
from uuid import uuid4
import httpx
from eduagent.domain.catalog import Catalog
from eduagent.services.learning import LearningService
from eduagent.services.personal_bank import PersonalBankService
from eduagent.services.resources import resource_id
from eduagent.domain.personal_bank import question
from eduagent.storage.sqlite import SQLiteRepository,encode

root=Path.cwd();path=root/'data/local/pilot-review.json';owner='pilot-model-evaluation'
state=json.loads(path.read_text(encoding='utf-8')) if path.exists() else dict(student_id=owner,goals=['model_evaluation'],status='awaiting_owner_review')
def save():path.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
def cmd(**kw):return dict(request_id=str(uuid4()),**kw)
save();base=Path('C:/Users/fengj/Desktop')
course=next(p for p in (base/'机器学习课件').glob('*.pdf') if '模型评估' in p.name)
exercise=base/'机器学习习题/机器学习测试题3.pdf'
with httpx.Client(base_url='http://127.0.0.1:8000',trust_env=False,timeout=40) as client:
    prefix=f'/api/v1/students/{owner}'
    def req(url,body=None,method=None):
        r=client.request(method or ('POST' if body is not None else 'GET'),url,json=body) if body is not None else client.get(url)
        r.raise_for_status();return r.json()
    req('/api/v1/students',dict(student_id=owner,goals=['model_evaluation']))
    for role,file in [('course',course),('exercise',exercise)]:
        if role not in state:
            checksum=hashlib.sha256(file.read_bytes()).hexdigest()
            matches=[d for d in req(prefix+'/documents')['items'] if d['version']['content_hash']==checksum]
            if matches:doc=matches[0]
            else:
                rid=state.setdefault(role+'_request',str(uuid4()));save()
                meta=dict(request_id=rid,title=file.stem,material_role='teaching_slides' if role=='course' else 'handout',source_note='单知识点试点，本机资料；尚待负责人审核',local_rights_confirmed=True)
                with file.open('rb') as f:r=client.post(prefix+'/documents',data={'metadata':json.dumps(meta,ensure_ascii=False)},files={'file':(file.name,f,'application/pdf')})
                r.raise_for_status();doc=r.json()
            state[role]=dict(id=doc['id'],file_name=file.name,hash=checksum);save()
        doc=req(prefix+'/documents/'+state[role]['id'])
        while doc['parse']['status'] in ('pending','processing'):time.sleep(.5);doc=req(prefix+'/documents/'+doc['id'])
        assert doc['parse']['status']=='partial'
        state[role].update(version_id=doc['version']['id'],run_id=doc['parse']['id']);save()
    if 'architecture_id' not in state:
        a=req(prefix+'/knowledge-architectures',cmd(name='模型评估真实课程试点',description='只关联原model_evaluation；候选，须负责人确认'))
        state['architecture_id']=a['architecture_id'];state['concept_id']=str(uuid4());state['chapter_id']=str(uuid4());save()
        g=dict(name='模型评估真实课程试点',description='待负责人对照真实资料确认',chapters=[dict(id=state['chapter_id'],title='模型评估与选择',order=0)],concepts=[dict(id=state['concept_id'],name='模型评估',summary='测试集、验证方法、性能度量；关联既有正式知识点',chapter_ids=[state['chapter_id']],formal_knowledge_ids=['model_evaluation'])],relations=[])
        req(prefix+'/knowledge-architectures/'+state['architecture_id']+'/draft',cmd(expected_revision=1,graph=g),'PUT')
    if 'link_ids' not in state:
        units={}
        for offset in range(0,80,20):
            result=req(prefix+'/documents/'+state['course']['id']+'/units?run_id='+state['course']['run_id']+'&limit=20&offset='+str(offset))
            units.update({u['ordinal']:u for u in result['items']})
        assert len(units)==72
        existing=req(prefix+'/teaching-material-links')['items'];links=[]
        for proposal in json.loads((root/'data/local/pilot-page-proposals.json').read_text(encoding='utf-8'))['pages']:
            page=proposal['page'];u=units[page]
            found=next((r for r in existing if r['page_number']==page and r['document_id']==state['course']['id']),None)
            if found:links.append(found['id']);continue
            body=cmd(document_id=state['course']['id'],run_id=state['course']['run_id'],ordinal=page,architecture_id=state['architecture_id'],concept_id=state['concept_id'],start_offset=0,end_offset=len(u['content_md']),excerpt_md=proposal['excerpt_md'] or u['content_md'])
            links.append(req(prefix+'/teaching-material-links',body)['id'])
        state['link_ids']=links;save()

# Reuse exactly three previously extracted questions from the same file hash,
# under a separate goal scope. No new recognition/model calls and no old edits.
if 'question_ids' not in state:
    old_ids=['2d5db7e5-7177-4fb9-8d39-fba0aeb0deb5','19e16098-3805-4c39-aa02-01e6057c34b6','2767fdca-8ea4-402f-839a-4763c1edf714']
    with SQLiteRepository(root/'data/local/eduagent.sqlite3',allow_upgrade=False) as repo:
        learning=LearningService(Catalog.load(root/'data'),repo);bank=PersonalBankService(learning,root/'data/materials')
        item=bank.resources.row(owner,resource_id(owner,'document',state['exercise']['id']))
        units,_=bank.resources.units(owner,item,state['exercise']['run_id'],[1]);raw=units[0]['text']
        payloads=[]
        for oid in old_ids:
            r=repo.connection.execute('SELECT payload_json,source_json FROM personal_questions WHERE id=? AND student_id=?',(oid,'learner-8ab5e4c4')).fetchone()
            original=json.loads(r['source_json']);assert original['content_hash']==state['exercise']['hash']
            p=question(json.loads(r['payload_json']));assert all(o['text'].replace(' ','') in raw.replace(' ','') for o in p['options'])
            payloads.append(p)
        body=dict(request_id=state.setdefault('questions_request',str(uuid4())),document_id=item['original_source_id']);save()
        def insert():
            bank.resources.register(owner,item);ids=[]
            source=dict(resource_id=item['resource_id'],title=item['title'],original_source_type='document',original_source_id=item['original_source_id'],source_version=item['source_version'],content_hash=item['content_hash'],run_id=state['exercise']['run_id'],origin_mode='local',evidence=[dict(unit_id=units[0]['id'],location=units[0]['location'],raw_md=raw,origin='local_extraction',warnings=units[0]['warnings'])],warnings=['existing_extraction_reused_requires_owner_review'])
            for p in payloads:ids.append(bank._insert_question(owner,p,source=source,origin='unknown',review=dict(reviewed=False,answer_confirmed=False)))
            return dict(question_ids=ids)
        result=bank._write(owner,body,'selected-existing-extraction-pilot',insert);state['question_ids']=result['question_ids'];save()
print(json.dumps(dict(student_id=owner,course=state['course']['id'],exercise=state['exercise']['id'],pages=5,questions=len(state['question_ids']),status=state['status'],new_paid_calls=0)))
