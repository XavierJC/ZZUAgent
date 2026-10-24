"""Stable graph identity, scoped versions/candidates and independent learning facts."""
from copy import deepcopy
from hashlib import sha256
import json
import sqlite3
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient

from eduagent.domain.architecture import graph,ArchitectureError
from eduagent.services.architectures import ArchitectureService
from eduagent.services.documents import DocumentsService
from eduagent.services.learning import LearningService
from eduagent.storage.sqlite import SQLiteRepository
from eduagent.storage import migrations
from eduagent.api.app import create_app
from eduagent.api.settings import APISettings
from test_documents import upload,tick


def uid(): return str(uuid4())
def mutation(revision,**extra): return dict(request_id=uid(),expected_revision=revision,**extra)
def example():
    a,b,c,d=[uid() for _ in range(4)]
    return dict(name='机器学习框架',chapters=[dict(id=a,title='基础',order=0),dict(id=b,title='应用',parent_id=a,order=1)],
        concepts=[dict(id=c,name='损失',chapter_ids=[a,b],formal_knowledge_ids=['linear_regression_loss']),dict(id=d,name='损失',chapter_ids=[b])],
        relations=[dict(id=uid(),source_id=c,target_id=d,kind='prerequisite_candidate')])


@pytest.fixture
def architecture(service):
    service.register('student-b')
    yield ArchitectureService(service)


def create(s): return s.create('student-a',dict(request_id=uid(),name='知识体系'))['architecture_id']
def original(s): return {k:v for k,v in migrations.preserved_snapshot(s.db)[0].items() if k not in migrations.ARCHITECTURE_TABLES + migrations.BANK_TABLES}


def test_manual_graph_stable_same_names_many_chapters_and_immutable_versions(architecture):
    s=architecture; before=original(s); key=create(s); data=example(); cid=data['concepts'][0]['id']
    result=s.save('student-a',key,mutation(1,graph=data)); assert result['revision']==2
    draft=s.get('student-a',key); assert draft['published_version']==0 and len(draft['draft']['graph']['concepts'])==2
    with pytest.raises(ArchitectureError): s.published('student-a',key)
    with pytest.raises(ArchitectureError): s.publish('student-a',key,mutation(2,confirmed=False))
    saved=s.publish('student-a',key,mutation(2,confirmed=True)); old=s.published('student-a',key)
    assert saved['version']==1 and old['graph']['concepts'][0]['review_status']=='confirmed'
    assert old['graph']['relations'][0]['kind']=='prerequisite_candidate'
    with pytest.raises(ArchitectureError) as locked:s.save('student-a',key,mutation(3,graph=data))
    assert locked.value.code=='draft_locked'
    s.fork('student-a',key,mutation(3,version=1)); data['concepts'][0]['name']='改名仍同ID'
    s.save('student-a',key,mutation(4,graph=data)); s.publish('student-a',key,mutation(5,confirmed=True))
    assert s.published('student-a',key,1)==old
    assert s.published('student-a',key)['graph']['concepts'][0]['id']==cid
    assert original(s)==before


@pytest.mark.parametrize('failure',['chapter_cycle','self_relation','reverse_related','contains_cycle','prereq_cycle','missing_chapter','missing_concept','duplicate_id','unknown_formal','extra_control','depth','bad_type'])
def test_graph_rejects_cycles_duplicate_edges_missing_refs_and_control_fields(failure,catalog):
    g=example(); a,b=g['chapters']; c,d=g['concepts']; r=g['relations'][0]
    if failure=='chapter_cycle': a['parent_id']=b['id']
    if failure=='self_relation': r['target_id']=c['id']
    if failure=='reverse_related':
        r['kind']='related_to';g['relations'].append(dict(r,id=uid(),source_id=d['id'],target_id=c['id']))
    if failure in ('contains_cycle','prereq_cycle'):
        r['kind']='contains' if failure=='contains_cycle' else 'prerequisite_candidate'
        g['relations'].append(dict(r,id=uid(),source_id=d['id'],target_id=c['id']))
    if failure=='missing_chapter': g['chapters'].pop()
    if failure=='missing_concept': g['concepts'].pop()
    if failure=='duplicate_id': d['id']=c['id']
    if failure=='unknown_formal': c['formal_knowledge_ids']=['new-bkt']
    if failure=='extra_control': g['mastery']=1
    if failure=='bad_type': a['order']=True
    if failure=='depth':
        for i in range(10): g['chapters'].append(dict(id=uid(),title='小节',parent_id=g['chapters'][-1]['id']))
    with pytest.raises(ValueError): graph(g,catalog.knowledge)


def test_idempotency_conflict_and_cross_student_no_leak(architecture):
    s=architecture; key=create(s); request=mutation(1,graph=example())
    result=s.save('student-a',key,request); assert s.save('student-a',key,request)['replayed']
    with pytest.raises(ArchitectureError) as conflict:s.save('student-a',key,{**request,'graph':example()})
    assert conflict.value.code=='request_id_conflict'
    with pytest.raises(ArchitectureError) as stale:s.save('student-a',key,mutation(1,graph=example()))
    assert stale.value.code=='revision_conflict'
    for call in (lambda:s.get('student-b',key),lambda:s.receipt('student-b',request['request_id']),lambda:s.states('student-b',key,request['graph']['concepts'][0]['id'],draft=True)):
        with pytest.raises(ArchitectureError) as denied:call()
        assert denied.value.status==404 and '知识体系' not in str(denied.value).replace('该知识体系','')
    assert s.listing('student-b')['items']==[]


def test_readonly_formal_states_prior_is_not_evidence(architecture):
    s=architecture; key=create(s); data=example();s.save('student-a',key,mutation(1,graph=data))
    before=original(s); linked=s.states('student-a',key,data['concepts'][0]['id'],draft=True)
    assert linked['items'][0]['status']=='pending_diagnosis' and linked['items'][0]['objective']['probability'] is None
    assert s.states('student-a',key,data['concepts'][1]['id'],draft=True)['items']==[]
    assert original(s)==before


def test_candidates_use_real_saved_native_parse_keep_evidence_and_stale_guard(architecture,tmp_path):
    s=architecture; key=create(s); docs=DocumentsService(s.repo,tmp_path/'files')
    raw='# 梯度下降\n\n概念：学习率\n\n# 课堂安排\n\n仅供参考。'.encode()
    doc,_=upload(docs,raw,student='student-a');tick(docs); doc=docs.get('student-a',doc['id'])
    before=original(s)
    body=mutation(1,documents=[dict(document_id=doc['id'],version_id=doc['version']['id'],run_id=doc['parse']['id'])])
    receipt=s.candidates('student-a',key,body); batch=s.batch('student-a',key,receipt['batch_id'])
    assert s.candidates('student-a',key,body)['batch_id']==receipt['batch_id']
    assert len(batch['graph']['chapters'])==2 and len(batch['graph']['concepts'])==2 and batch['graph']['relations']==[]
    assert all(raw.decode()[e['start_offset']:e['end_offset']]==e['raw_text'] for e in batch['evidence'])
    g=batch['graph']; g['name']='候选已编辑';g['concepts'][0]['summary']='人工修改'
    s.save('student-a',key,mutation(1,graph=g)); assert original(s)==before
    docs.mutate('student-a',doc['id'],mutation(doc['revision'],title='资料修改'),'update')
    assert all(e['current_status']=='metadata_modified' for e in s.batch('student-a',key,batch['id'])['evidence'])
    with pytest.raises(ArchitectureError) as stale:s.publish('student-a',key,mutation(2,confirmed=True))
    assert stale.value.code=='source_changed' and s.get('student-a',key)['published_version']==0
    with pytest.raises(ArchitectureError):s.batch('student-b',key,batch['id'])


def test_atomic_save_rollback_and_identity_kind_cannot_be_repurposed(architecture):
    s=architecture;key=create(s);g=example();s.save('student-a',key,mutation(1,graph=g))
    bad=deepcopy(g);bad['chapters'].append(dict(id=bad['concepts'].pop()['id'],title='错误复用'))
    bad['relations']=[]
    with pytest.raises(ArchitectureError):s.save('student-a',key,mutation(2,graph=bad))
    assert s.get('student-a',key)['revision']==2
    # SQL failure at publication: neither version, lock nor receipt can survive.
    s.db.execute("CREATE TRIGGER fail_publish BEFORE INSERT ON knowledge_versions BEGIN SELECT RAISE(ABORT,'synthetic'); END")
    request=mutation(2,confirmed=True)
    with pytest.raises(sqlite3.IntegrityError):s.publish('student-a',key,request)
    assert s.get('student-a',key)['draft']['status']=='editing' and s.get('student-a',key)['published_version']==0
    with pytest.raises(ArchitectureError):s.receipt('student-a',request['request_id'])


def test_isolated_api_without_model_and_refresh_only_reads(tmp_path,data_dir):
    settings=APISettings(data_dir=data_dir,db_path=tmp_path/'api.sqlite3')
    with TestClient(create_app(settings)) as client:
        client.post('/api/v1/students',json=dict(student_id='api-a'))
        base='/api/v1/students/api-a/knowledge-architectures'
        receipt=client.post(base,json=dict(request_id=uid(),name='人工体系'));assert receipt.status_code==200,receipt.text
        key=receipt.json()['architecture_id']; g=example()
        response=client.put(base+'/'+key+'/draft',json=mutation(1,graph=g));assert response.status_code==200,response.text
        assert client.get(base+'/'+key+'/published').status_code==404
        assert client.post(base+'/'+key+'/publish',json=mutation(2,confirmed=True)).status_code==200
        for _ in range(2):assert client.get(base+'/'+key+'/published').json()['version']==1
        assert client.get('/api/v1/students/api-a/history').json()['items']==[]
        assert client.get(base+'/'+key+'/concepts/'+g['concepts'][0]['id']+'/learning-state').json()['items'][0]['status']=='pending_diagnosis'
        assert client.post(base,json=dict(request_id=uid(),name='bad',student_id='other')).status_code==422


def test_concurrent_writers_use_independent_architecture_revision(architecture,catalog):
    from concurrent.futures import ThreadPoolExecutor
    s=architecture;key=create(s);path=s.db.execute('pragma database_list').fetchone()[2]
    before=original(s)
    def save(name):
        with SQLiteRepository(path) as repo:
            service=ArchitectureService(LearningService(catalog,repo)); value=example();value['name']=name
            try: return service.save('student-a',key,mutation(1,graph=value))
            except ArchitectureError as exc:return exc.code
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(save,['one','two']))
    assert sum(isinstance(x,dict) for x in results)==1 and 'revision_conflict' in results
    assert s.get('student-a',key)['revision']==2 and original(s)==before


@pytest.mark.parametrize('change',['new_version','reparse','delete'])
def test_old_candidate_evidence_never_becomes_current_after_source_change(architecture,tmp_path,change):
    s=architecture;key=create(s);docs=DocumentsService(s.repo,tmp_path/'files')
    doc,_=upload(docs,b'# PCA\n\nDefinition text',student='student-a');tick(docs);doc=docs.get('student-a',doc['id'])
    batch=s.candidates('student-a',key,mutation(1,documents=[dict(document_id=doc['id'],version_id=doc['version']['id'],run_id=doc['parse']['id'])]))
    g=s.batch('student-a',key,batch['batch_id'])['graph'];s.save('student-a',key,mutation(1,graph=g))
    if change=='new_version':upload(docs,b'# PCA\n\nNew version',student='student-a',doc=doc['id'],meta=dict(request_id=uid(),course_id='machine_learning',expected_revision=doc['revision']))
    elif change=='reparse':docs.mutate('student-a',doc['id'],mutation(doc['revision']),'parse')
    else:docs.mutate('student-a',doc['id'],mutation(doc['revision']),'delete')
    expected={'new_version':'modified','reparse':'reparsed','delete':'deleted'}[change]
    assert s.get('student-a',key)['draft']['sources'][0]['current_status']==expected
    with pytest.raises(ArchitectureError) as caught:s.publish('student-a',key,mutation(2,confirmed=True))
    assert caught.value.code=='source_changed'


def test_candidate_scope_cannot_be_forged_via_graph_origins(architecture,tmp_path):
    s=architecture;key=create(s);other=s.create('student-b',dict(request_id=uid(),name='private'))['architecture_id']
    docs=DocumentsService(s.repo,tmp_path/'files');doc,_=upload(docs,b'# PCA',student='student-b');tick(docs);doc=docs.get('student-b',doc['id'])
    selection=dict(document_id=doc['id'],version_id=doc['version']['id'],run_id=doc['parse']['id'])
    with pytest.raises(ValueError):s.candidates('student-a',key,mutation(1,documents=[selection]))
    batch=s.candidates('student-b',other,mutation(1,documents=[selection]));private=s.batch('student-b',other,batch['batch_id'])
    with pytest.raises(ArchitectureError) as denied:s.save('student-a',key,mutation(1,graph=private['graph']))
    assert denied.value.status==404
    assert s.get('student-a',key)['revision']==1


def test_numbered_bullets_code_and_formulas_do_not_create_chapters(architecture,tmp_path):
    from eduagent.documents.architecture_candidates import extract
    raw='1. 这是句子。\n2. 下一步操作\n```python\n# not a chapter\n```\n$$\n# formula\n$$\n'
    unit=dict(id=uid(),kind='markdown_section',title='',text=raw,location={},content_hash='synthetic')
    data=extract(uid(),[(dict(id=uid(),revision=1,title='自建'),dict(id=uid(),file_revision=1,content_hash='x'),dict(id=uid(),parser_version='test'),[unit])])
    assert data['graph']['chapters']==[] and data['graph']['concepts']==[] and len(data['unclassified'])==1


def test_schema7_migration_preserves_twenty_one_tables_and_rollback(tmp_path,catalog,monkeypatch):
    path=tmp_path/'migration.sqlite3'
    with SQLiteRepository(path) as repo:
        learning=LearningService(catalog,repo);learning.register('student-a')
        docs=DocumentsService(repo,tmp_path/'files');upload(docs,b'# Original',student='student-a');tick(docs)
        for table in reversed(migrations.ARCHITECTURE_TABLES + migrations.BANK_TABLES + migrations.EXTRACTION_TABLES + migrations.RELEASE_TABLES + migrations.TEACHER_TABLES):repo.connection.execute('drop table '+table)
        repo.connection.execute('pragma user_version=7');before,columns=migrations.preserved_snapshot(repo.connection)
    assert len(before)==21
    with pytest.raises(ValueError,match='显式迁移'):SQLiteRepository(path,allow_upgrade=False)
    ddl=migrations.ARCHITECTURES;monkeypatch.setattr(migrations,'ARCHITECTURES',(*ddl[:1],'INVALID DDL'))
    with pytest.raises(sqlite3.Error):SQLiteRepository(path)
    with sqlite3.connect(path) as db:
        assert db.execute('pragma user_version').fetchone()[0]==7 and migrations.preserved_snapshot(db)[0]==before
    monkeypatch.setattr(migrations,'ARCHITECTURES',ddl)
    with SQLiteRepository(path) as repo:
        assert repo.migration_report['to_version']==13 and migrations.preserved_snapshot(repo.connection,columns)[0]==before
        assert repo.connection.execute('pragma integrity_check').fetchone()[0]=='ok' and not repo.connection.execute('pragma foreign_key_check').fetchall()
        with sqlite3.connect(repo.migration_report['backup']) as old:assert migrations.preserved_snapshot(old)[0]==before

