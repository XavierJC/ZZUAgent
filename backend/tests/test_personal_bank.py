"""Personal extraction/review/practice never writes formal learning facts."""
from copy import deepcopy
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from uuid import uuid4
import json,sqlite3
import pytest
from fastapi.testclient import TestClient
from eduagent.api.app import create_app
from eduagent.api.settings import APISettings
from eduagent.domain.architecture import ArchitectureError
from eduagent.documents.question_extraction import extract
from eduagent.services.personal_bank import PersonalBankService
from eduagent.services.documents import DocumentsService
from eduagent.services.architectures import ArchitectureService
from eduagent.storage import migrations
from eduagent.storage.sqlite import SQLiteRepository
from eduagent.services.learning import LearningService
from test_documents import upload,tick
from test_architectures import example


def uid():return str(uuid4())
def command(**kw):return dict(request_id=uid(),**kw)
def payload(**kw):return dict(dict(stem='最小化 $L(w)$ 应沿什么方向更新？',question_type='single_choice',options=[dict(key='A',text='负梯度'),dict(key='B',text='正梯度')],answer='A',explanation='沿负梯度下降。'),**kw)
TEXT='1. 梯度下降沿什么方向？\nA. 负梯度\nB. 正梯度\n答案：A\n解析：最小化 $L(w)$。\n2. 判断：损失越小一定泛化越好？\n答案：错误\n'


@pytest.fixture
def bank(service,data_dir):
    service.register('student-b');return PersonalBankService(service,data_dir/'materials')


def facts(bank):return {k:v for k,v in migrations.preserved_snapshot(bank.db)[0].items() if k not in migrations.BANK_TABLES}
def create(bank,**kw):return bank.save('student-a',command(payload=payload(),status='practice',reviewed=True,confirm_answer=True,**kw))['question_id']


def test_complete_extraction_review_practice_no_formal_writes(bank):
    before=facts(bank);body=command(text=TEXT)
    batch=bank.extract('student-a',body)
    assert bank.extract('student-a',body)['question_ids']==batch['question_ids']
    rows=bank.listing('student-a')['items'];assert len(rows)==2
    row=next(r for r in rows if r['payload']['question_type']=='single_choice')
    assert row['answer_provenance']=='source_provided' and row['status']=='draft'
    bank.save('student-a',command(expected_revision=1,payload=row['payload'],status='practice',reviewed=True,confirm_answer=True),row['id'])
    session=bank.start('student-a',command(question_id=row['id']))['session_id']
    hidden=bank.session('student-a',session)
    assert 'answer' not in hidden['question'] and 'explanation' not in hidden['question']
    submit=command(selected_answer='A');result=bank.submit('student-a',session,submit)
    assert result['result']['correct'] is True and result['result']['bkt_updated'] is False
    assert bank.submit('student-a',session,submit)['replayed']
    assert bank.session('student-a',session)['result']==result['result']
    assert bank.start('student-a',command(question_id=row['id']))['session_id']!=session
    changed=dict(row['payload'],answer='B')
    bank.save('student-a',command(expected_revision=2,payload=changed),row['id'])
    edited=bank.get('student-a',row['id'])
    assert edited['answer_provenance']=='unknown' and edited['review']['original_answer_origin']=='source_provided'
    assert facts(bank)==before


def test_source_answer_is_not_scoring_until_human_confirmation(bank):
    key=bank.save('student-a',command(payload=payload(),status='practice',reviewed=True,confirm_answer=False))['question_id']
    session=bank.start('student-a',command(question_id=key))['session_id']
    result=bank.submit('student-a',session,command(selected_answer='A'))['result']
    assert result['score'] is None and result['correct'] is None and result['correct_answer'] is None


@pytest.mark.parametrize('answer',[None,'true','false'])
def test_true_false_unknown_and_wrong_answer_history(bank,answer):
    p=dict(stem='判断：正则化总能提高训练拟合程度。',question_type='true_false',answer=answer,explanation='需区分训练误差与泛化误差。')
    key=bank.save('student-a',command(payload=p,status='practice',reviewed=True,confirm_answer=answer is not None))['question_id']
    session=bank.start('student-a',command(question_id=key))['session_id']
    result=bank.submit('student-a',session,command(selected_answer='true'))['result']
    assert result['correct'] is (None if answer is None else answer=='true')
    assert len(bank.sessions('student-a',True)['items'])==int(answer=='false')


def test_scope_conflicts_request_mismatch_and_snapshot(bank):
    body=command(payload=payload());key=bank.save('student-a',body)['question_id']
    with pytest.raises(ArchitectureError):bank.save('student-a',dict(body,payload=payload(stem='different')))
    for op in [lambda:bank.get('student-b',key),lambda:bank.revisions('student-b',key)]:
        with pytest.raises(ArchitectureError) as exc:op()
        assert exc.value.status==404
    edit=command(expected_revision=1,payload=payload(),status='practice',reviewed=True,confirm_answer=True)
    bank.save('student-a',edit,key)
    with pytest.raises(ArchitectureError):bank.save('student-a',dict(edit,request_id=uid()),key)
    sid=bank.start('student-a',command(question_id=key))['session_id']
    bank.save('student-a',command(expected_revision=2,payload=payload(stem='Changed current question'),status='draft'),key)
    bank.archive('student-a',key,command(expected_revision=3))
    assert bank.submit('student-a',sid,command(selected_answer='A'))['result']['correct'] is True
    assert bank.session('student-a',sid)['question']['stem']!=bank.get('student-a',key)['payload']['stem']
    with pytest.raises(ArchitectureError):bank.session('student-b',sid)


def test_document_reuse_update_and_delete_status(bank,tmp_path):
    docs=DocumentsService(bank.repo,tmp_path/'files')
    doc,_=upload(docs,TEXT.encode(),name='questions.md',student='student-a');tick(docs)
    resources=bank.catalogue('student-a')['items'];item=next(r for r in resources if r['original_source_id']==doc['id'])
    batch=bank.extract('student-a',command(resource_id=item['resource_id'],source_version=item['source_version']))
    assert len(batch['question_ids'])==2 and bank.db.execute('select count(*) from course_documents').fetchone()[0]==1
    old=bank.get('student-a',batch['question_ids'][0])
    doc=docs.get('student-a',doc['id'])
    updated,_=upload(docs,(TEXT+'\n新版本').encode(),name='q.md',meta=command(expected_revision=doc['revision'],course_id='machine_learning'),student='student-a',doc=doc['id']);tick(docs)
    assert bank.get('student-a',old['id'])['source_status']=='modified'
    with pytest.raises(ArchitectureError):bank.extract('student-a',command(resource_id=item['resource_id'],source_version=item['source_version']))
    current=docs.get('student-a',doc['id']);docs.mutate('student-a',doc['id'],command(expected_revision=current['revision']),'delete')
    assert bank.get('student-a',old['id'])['source_status']=='deleted'
    assert bank.get('student-a',old['id'])['payload']==old['payload']


def test_many_concepts_resource_links_chapter_filter(bank):
    s=ArchitectureService(bank.learning);key=s.create('student-a',command(name='框架'))['architecture_id'];g=example()
    s.save('student-a',key,command(expected_revision=1,graph=g));s.publish('student-a',key,command(expected_revision=2,confirmed=True))
    refs=[dict(architecture_id=key,concept_id=c['id']) for c in g['concepts']]
    q=bank.save('student-a',command(payload=payload(concepts=refs)))['question_id']
    assert len(bank.listing('student-a',chapter_id=g['chapters'][0]['id'])['items'])==1
    item=bank.catalogue('student-a')['items'][0]
    links=[dict(architecture_id=key,node_id=r['concept_id'],kind='concept',review_status='candidate') for r in refs]
    bank.tag_resource('student-a',item['resource_id'],command(expected_revision=0,resource_type='exercise_material',links=links))
    assert bank.catalogue('student-a')['items'][0]['links']==links
    with pytest.raises(ArchitectureError):bank.save('student-b',command(payload=payload(concepts=refs)))


def test_merge_split_atomic_and_duplicate_hints(bank):
    first=create(bank);second=create(bank)
    assert second in bank.listing('student-a')['items'][0]['duplicate_ids'] or first in bank.listing('student-a')['items'][0]['duplicate_ids']
    body=command(originals=[dict(question_id=first,expected_revision=1),dict(question_id=second,expected_revision=2)],questions=[payload()])
    with pytest.raises(ArchitectureError):bank.restructure('student-a',body)
    assert bank.get('student-a',first)['status']=='practice'
    body['originals'][1]['expected_revision']=1
    merged=bank.restructure('student-a',body)['question_ids'][0]
    assert bank.get('student-a',first)['status']=='archived'
    split=bank.restructure('student-a',command(originals=[dict(question_id=merged,expected_revision=1)],questions=[payload(),payload(stem='Split second')]))
    assert len(split['question_ids'])==2 and len(bank.get('student-a',merged)['source']['restructured_from'])==2


def test_pdf_cross_page_formula_and_ambiguous_raw_evidence():
    units=[dict(id=uid(),text='1. 求 $w^2$ 的导数？\nA. $2w$\n',location=dict(page_number=1)),
           dict(id=uid(),text='B. $w$\n答案：A\n2. 见图求解\n|A|B|\n|1|2|\n',location=dict(page_number=2))]
    rows,warnings=extract(units)
    assert len(rows)==2 and len(rows[0]['evidence'])==2 and rows[0]['payload']['answer']=='A'
    assert rows[1]['payload']['answer'] is None and 'visual_or_table_requires_review' in rows[1]['warnings']
    assert all(e['raw_md']==u['text'][e['start_offset']:e['end_offset']] for e,u in zip(rows[0]['evidence'],units))


def test_shared_context_before_question_numbers_is_not_discarded():
    rows,_=extract([dict(text='共有背景：给定 $f(x)=x^2$。\n1. 求导\nA. 2x\nB. x\n答案：A\n2. 判断：函数是线性。')])
    assert all('共有背景' in r['payload']['stem'] for r in rows)
    assert all('shared_context_requires_review' in r['warnings'] for r in rows)
    assert all('共有背景' in r['evidence'][0]['raw_md'] for r in rows)


@pytest.mark.parametrize('raw',['1. 题干\nA. x\nA. y\n答案：A','1. x\n2. y\n1. z','无编号题目 $x$','1. 题目\n答案：AB','1. $$\nx^2'])
def test_malformed_extract_is_draft_not_guessed(raw):
    rows,warnings=extract([dict(text=raw)])
    assert rows and all(r['payload']['answer'] is None for r in rows)
    assert all(r['warnings'] or warnings for r in rows)


def test_images_reuse_pipeline_keep_original_no_fake_ocr(bank,tmp_path):
    from PIL import Image
    im=Image.new('RGB',(320,240),'white');buf=BytesIO();im.save(buf,format='PNG');raw=buf.getvalue()
    docs=DocumentsService(bank.repo,tmp_path/'files');doc,_=upload(docs,raw,'q.png',student='student-a');tick(docs)
    current=docs.get('student-a',doc['id']);assert current['parse']['status']=='empty'
    path,name=docs.original('student-a',doc['id']);assert path.read_bytes()==raw
    item=next(r for r in bank.catalogue('student-a')['items'] if r['original_source_id']==doc['id'])
    result=bank.extract('student-a',command(resource_id=item['resource_id'],source_version=item['source_version']))
    q=bank.get('student-a',result['question_ids'][0]);assert q['answer_provenance']=='unknown' and q['status']=='draft'
    assert 'no_text_manual_transcription_required' in q['source']['warnings']


def test_api_real_contract_errors_scope_and_no_model(tmp_path,data_dir):
    settings=APISettings(db_path=tmp_path/'api.sqlite3',data_dir=data_dir,retrieval_enabled=False)
    with TestClient(create_app(settings)) as client:
        for s in ['bank-a','bank-b']:assert client.post('/api/v1/students',json=dict(student_id=s)).status_code==200
        base='/api/v1/students/bank-a/personal-bank'
        body=command(text=TEXT);res=client.post(base+'/extractions',json=body);assert res.status_code==200
        key=res.json()['question_ids'][0]
        assert client.get('/api/v1/students/bank-b/personal-bank/questions/'+key).status_code==404
        assert client.post(base+'/questions',json=command(payload=dict(payload(),bkt=1))).status_code==422
        assert client.post(base+'/extractions',json=command(text=TEXT,resource_id=uid())).status_code==422
        assert client.get('/api/v1/students/bank-a/course-resources').status_code==200
        assert client.post(base+'/questions',json=command(payload=payload(),status='diagnostic')).status_code==422
        assert client.post(base+'/questions',content=b'x'*270000,headers={'content-type':'application/json'}).status_code==413


def test_schema8_migration_rollback_and_all_27_tables(tmp_path,catalog,monkeypatch):
    path=tmp_path/'old.sqlite3'
    with SQLiteRepository(path) as repo:
        LearningService(catalog,repo).register('old')
        for table in reversed(migrations.BANK_TABLES + migrations.EXTRACTION_TABLES + migrations.RELEASE_TABLES + migrations.TEACHER_TABLES):repo.connection.execute('DROP TABLE '+table)
        repo.connection.execute('PRAGMA user_version=8');before,columns=migrations.preserved_snapshot(repo.connection)
    ddl=migrations.BANK;monkeypatch.setattr(migrations,'BANK',(*ddl[:1],'INVALID SQL'))
    with pytest.raises(sqlite3.Error):SQLiteRepository(path)
    with sqlite3.connect(path) as db:
        assert db.execute('pragma user_version').fetchone()[0]==8 and migrations.preserved_snapshot(db)[0]==before
    monkeypatch.setattr(migrations,'BANK',ddl)
    with SQLiteRepository(path) as repo:
        assert repo.migration_report['to_version']==12 and len(before)==27
        assert migrations.preserved_snapshot(repo.connection,columns)[0]==before
        assert repo.connection.execute('pragma foreign_keys').fetchone()[0]==1
        assert not repo.connection.execute('pragma foreign_key_check').fetchall()


def test_concurrent_http_writes_and_submissions_are_serialized(tmp_path,data_dir):
    from concurrent.futures import ThreadPoolExecutor
    settings=APISettings(db_path=tmp_path/'race.sqlite3',data_dir=data_dir,retrieval_enabled=False)
    with TestClient(create_app(settings)) as client:
        client.post('/api/v1/students',json=dict(student_id='a'))
        base='/api/v1/students/a/personal-bank';body=command(payload=payload(),status='practice',reviewed=True,confirm_answer=True)
        key=client.post(base+'/questions',json=body).json()['question_id']
        mutations=[command(expected_revision=1,payload=payload(stem=stem),status='practice',reviewed=True,confirm_answer=True) for stem in ('Writer one','Writer two')]
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda b:client.put(base+'/questions/'+key,json=b),mutations))
        assert sorted(r.status_code for r in results)==[200,409]
        assert client.get(base+'/questions/'+key).json()['revision']==2
        sid=client.post(base+'/practice',json=command(question_id=key)).json()['session_id'];answer=command(selected_answer='A')
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:client.post(base+'/practice/'+sid+'/answer',json=answer),range(2)))
        assert [r.status_code for r in results]==[200,200]
        assert sorted(r.json()['replayed'] for r in results)==[False,True]


@pytest.mark.parametrize('count',[1,2])
def test_saved_mock_vision_questions_never_become_scoring_answers(bank,tmp_path,count):
    from eduagent.agent.settings import AgentSettings
    from eduagent.agent.deepseek import ModelReply
    from eduagent.documents.vision import render_pages
    class Model:
        calls=0
        def complete(self,messages,tools):
            self.calls+=1;assert not tools
            text=TEXT.split('2. 判断')[0] if count==1 else TEXT
            return ModelReply(dict(content=json.dumps(dict(transcription_md=text,interpretation_md='',warnings=[]))),1,2)
    docs=DocumentsService(bank.repo,tmp_path/'files',vision_enabled=True,agent_settings=AgentSettings(api_key='synthetic'))
    buf=BytesIO()
    from PIL import Image
    Image.new('RGB',(30,30),'white').save(buf,format='PNG')
    doc,_=upload(docs,buf.getvalue(),'q.png',student='student-a');tick(docs)
    current=docs.get('student-a',doc['id'])
    job,_=docs.mutate('student-a',doc['id'],command(expected_revision=current['revision'],version_id=current['version']['id'],pages=[1],consent_external=True),'vision')
    def runner(manifest,output,**kw):
        value=json.loads(manifest.read_text(encoding='utf-8'));return render_pages(Path(value['path']),value['pages'])
    model=Model();tick(docs,runner,model)
    item=next(r for r in bank.catalogue('student-a')['items'] if r['original_source_id']==doc['id'])
    result=bank.extract('student-a',command(resource_id=item['resource_id'],source_version=item['source_version'],run_id=job['id']))
    assert len(result['question_ids'])==count and model.calls==1
    for key in result['question_ids']:
        row=bank.get('student-a',key);assert row['answer_provenance']=='model_inferred' and row['status']=='draft'
        assert 'model_transcription_unverified' in row['source']['warnings']


def test_published_note_is_reused_and_source_stale_without_changing_original(bank):
    from eduagent.services.notes import NotesService
    service=NotesService(bank.learning.catalog,bank.repo)
    note,_=service.create('student-a',id=uid(),title='原题笔记',content_md=TEXT,knowledge_point_ids=[])
    item=next(r for r in bank.catalogue('student-a')['items'] if r['original_source_id']==note['id'])
    batch=bank.extract('student-a',command(resource_id=item['resource_id'],source_version=item['source_version']))
    assert bank.db.execute('select count(*) from notes').fetchone()[0]==1
    assert bank.db.execute('select content_md from notes').fetchone()[0]==TEXT
    service.update('student-a',note['id'],1,dict(content_md=TEXT+'\n新内容'))
    assert bank.get('student-a',batch['question_ids'][0])['source_status']=='modified'


def test_merge_manual_first_still_tracks_other_source_version(bank):
    from eduagent.services.notes import NotesService
    manual=create(bank);notes=NotesService(bank.learning.catalog,bank.repo)
    note,_=notes.create('student-a',id=uid(),title='已有原题',content_md=TEXT,knowledge_point_ids=[])
    item=next(r for r in bank.catalogue('student-a')['items'] if r['original_source_id']==note['id'])
    imported=bank.extract('student-a',command(resource_id=item['resource_id'],source_version=item['source_version']))['question_ids'][0]
    combined=bank.restructure('student-a',command(originals=[dict(question_id=k,expected_revision=1) for k in [manual,imported]],questions=[payload()]))['question_ids'][0]
    notes.update('student-a',note['id'],1,dict(content_md=TEXT+'\n已修改'))
    assert bank.get('student-a',combined)['source_status']=='modified'
