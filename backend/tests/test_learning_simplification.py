"""Upload -> ask and extract -> practice, with synthetic providers only."""
import json
import sqlite3
from copy import deepcopy
from uuid import uuid4
import pytest

from eduagent.services.documents import DocumentsService
from eduagent.services.knowledge import KnowledgeService, SourceChanged, IndexUnavailable
from eduagent.services.workbench import WorkbenchService
from eduagent.services.question_intake import auto_entry, organize
from eduagent.agent.settings import AgentSettings
from eduagent.storage import migrations
from eduagent.storage.sqlite import SQLiteRepository
from eduagent.domain.notes import NoteNotFound
from test_documents import upload, tick, metadata
from test_personal_bank import bank, command, payload
from test_semantic_extraction import extraction, run, RAW, response
from test_workbench import FakeModel, body


@pytest.fixture
def reading(service,tmp_path):
    service.register('student-b')
    docs=DocumentsService(service.repository,tmp_path/'files')
    text='# 梯度下降\n\n梯度下降沿着负梯度方向更新参数，学习率控制每一步的大小。公式 $w_{t+1}=w_t-\\eta\\nabla L(w_t)$。'
    doc,_=upload(docs,text.encode('utf-8'),student='student-a');tick(docs)
    knowledge=KnowledgeService(service.catalog,service.repository)
    source=next(s for s in knowledge.sources('student-a')['items'] if s['source_type']=='uploaded_document')
    ref={k:source[k] for k in ('source_type','source_id','source_version')}
    return service,docs,doc,knowledge,ref


def test_upload_can_search_without_architecture_mapping_or_release(reading):
    l,d,doc,k,ref=reading;before=migrations.preserved_snapshot(l.repository.connection)[0]
    out=k.search('student-a','梯度下降',[ref]);assert out['items']
    for item in out['items']:
        assert item['source_type']=='uploaded_document' and item['review_status']=='document_unverified'
        assert item['page_number']==1 and item['document_id']==doc['id']
        assert item['raw_md']==d.units('student-a',doc['id'])['items'][0]['content_md'][item['start_offset']:item['end_offset']]
    assert migrations.preserved_snapshot(l.repository.connection)[0]==before
    assert not l.repository.connection.execute('SELECT 1 FROM knowledge_versions').fetchone()


def test_upload_scope_empty_selection_and_formal_filter_stay_strict(reading):
    l,d,doc,k,ref=reading
    with pytest.raises(NoteNotFound):k.search('student-b','梯度下降',[ref])
    with pytest.raises(ValueError):k.search('student-a','梯度下降',[])
    assert not k.search('student-a','梯度下降',[ref],knowledge_id='gradient_descent')['items']
    assert k.sources('student-b')['items']==[]


def test_uploaded_source_update_reparse_and_delete_invalidate_immediately(reading):
    l,d,doc,k,ref=reading
    d.mutate('student-a',doc['id'],command(expected_revision=1,title='新标题'),'update')
    with pytest.raises(SourceChanged):k.search('student-a','梯度下降',[ref])
    source=k.documents.source('student-a',doc['id']);newref={key:source[key] for key in ref}
    d.mutate('student-a',doc['id'],command(expected_revision=2),'parse')
    with pytest.raises(SourceChanged):k.search('student-a','梯度下降',[newref])
    tick(d)
    source=k.documents.source('student-a',doc['id']);newref={key:source[key] for key in ref}
    d.mutate('student-a',doc['id'],command(expected_revision=3),'delete')
    with pytest.raises(NoteNotFound):k.search('student-a','梯度下降',[newref])
    assert not k.sources('student-a')['items']


def test_uploaded_original_hash_verified(reading):
    _,d,doc,k,ref=reading
    row=d.storage.version(d._document('student-a',doc['id']))
    d.files.path(row['storage_key']).write_bytes(b'changed')
    with pytest.raises(IndexUnavailable):k.search('student-a','梯度下降',[ref])


def test_sparse_scan_and_hidden_slides_are_not_falsely_ready(service,tmp_path):
    d=DocumentsService(service.repository,tmp_path/'files')
    doc,_=upload(d,b'# Short\n\nabc',student='student-a');tick(d)
    k=KnowledgeService(service.catalog,service.repository)
    s=k.sources('student-a')['items'][0]
    assert s['index_status']=='empty' and s['readable_units']==0 and s['total_units']==1
    assert d.get('student-a',doc['id'])['index_status']=='empty'
    ref={key:s[key] for key in ('source_type','source_id','source_version')}
    preview=WorkbenchService(service).preview('student-a',ref)
    assert preview['document_id']==doc['id'] and preview['version_id']==doc['version']['id']
    assert '尚未提取到可读正文' in preview['raw_md']


def test_uploaded_external_consent_zero_calls_then_replay_citations(reading):
    l,d,doc,k,ref=reading;model=FakeModel();w=WorkbenchService(l,None,True,AgentSettings(enabled=True,api_key='synthetic'),lambda:model)
    no=w.ask('student-a',body([ref]));assert no['reason']=='teacher_consent_required' and model.calls==0
    before=migrations.fact_snapshot(l.repository.connection)
    request=body([ref],allow_teacher_external=True);out=w.ask('student-a',request)
    assert out['status']=='complete' and out['citations'][0]['page_number']==1 and model.calls==1
    assert w.ask('student-a',request)['answer']==out['answer'] and model.calls==1
    assert w.preview('student-a',ref)['raw_md']
    assert migrations.fact_snapshot(l.repository.connection)==before
    d.mutate('student-a',doc['id'],command(expected_revision=1,title='后来改名'),'update')
    history=w.get('student-a',request['request_id'])
    assert history['citations']==out['citations'] and history['source_statuses'][0]['current_status']=='modified'


def test_uploaded_agent_cannot_expand_source_scope(reading):
    l,_,_,_,ref=reading;model=FakeModel(tool=('retrieve_selected_sources',{'query':'梯度下降','source_ids':['other']}))
    w=WorkbenchService(l,None,True,AgentSettings(enabled=True,api_key='synthetic'),lambda:model)
    out=w.ask('student-a',body([ref],allow_teacher_external=True))
    assert out['reason']=='tool_scope_rejected' and model.calls==1


def test_ai_extract_auto_practice_without_human_claim_or_bkt(extraction):
    s=extraction;before=migrations.fact_snapshot(s.db)
    task=run(s,command(text=RAW,consent=True,auto_import=True))
    assert task['status']=='complete' and task['result']['intake']['ready']==1
    q=s.bank.get('student-a',task['result']['question_ids'][0])
    assert q['status']=='practice' and not q['review']['reviewed'] and not q['review']['answer_confirmed']
    assert q['review']['automation']['admitted']
    session=s.bank.start('student-a',command(question_id=q['id']))['session_id']
    out=s.bank.submit('student-a',session,command(selected_answer='我的回答'))['result']
    assert out['correct'] is None and out['score'] is None and not out['bkt_updated']
    assert out['reference_answer']=='训练好，泛化差。'
    assert migrations.fact_snapshot(s.db)==before


def test_ai_intake_duplicate_tasks_reuse_question_and_receipt(extraction):
    s=extraction;request=command(text=RAW,consent=True,auto_import=True)
    a=run(s,request);assert s.create('student-a',request)['result']==a['result'] and s.fake.calls==1
    b=run(s,command(text=RAW,consent=True,auto_import=True))
    assert b['result']['question_ids']==a['result']['question_ids'] and b['result']['intake']['duplicate']==1
    assert len(s.bank.listing('student-a')['items'])==1


@pytest.mark.parametrize('change',[{'question_type':'unknown'},{'stem':'[无法辨认] 内容'}, {'dependencies':['缺少图1']}, {'issues':['missing_condition']}])
def test_incomplete_questions_stay_actionable_drafts(bank,change):
    p=payload(**change);p.setdefault('concepts',[])
    qid,state=auto_entry(bank,'student-a',p,{},None,'unknown')
    assert state=='needs_attention' and bank.get('student-a',qid)['status']=='draft'


def test_auto_reference_comparison_never_becomes_objective_score(bank):
    p=payload();p['concepts']=[]
    qid,state=auto_entry(bank,'student-a',p,{},None,'model_inferred')
    session=bank.start('student-a',command(question_id=qid))['session_id']
    out=bank.submit('student-a',session,command(selected_answer='A'))['result']
    assert out['reference_match'] is True and out['content_verified'] is False
    assert out['correct'] is None and out['score'] is None
    assert bank.sessions('student-a',wrong_only=True)['items']==[]


def test_reimport_does_not_resolve_to_an_archived_unusable_question(bank):
    p=payload();p['concepts']=[]
    old,_=auto_entry(bank,'student-a',p,{},None,'unknown')
    bank.archive('student-a',old,command(expected_revision=1))
    fresh,state=auto_entry(bank,'student-a',p,{},None,'unknown')
    assert fresh!=old and state=='ready' and bank.get('student-a',old)['status']=='archived'


def test_existing_drafts_explicit_organize_is_idempotent_and_scoped(bank):
    key=bank.save('student-a',command(payload=payload()))['question_id'];request=command(question_ids=[key])
    before=migrations.fact_snapshot(bank.db)
    out=organize(bank,'student-a',request);assert out['ready']==1
    assert organize(bank,'student-a',request)['replayed'] and bank.get('student-a',key)['revision']==2
    with pytest.raises(ValueError):organize(bank,'student-b',command(question_ids=[key]))
    assert migrations.fact_snapshot(bank.db)==before


def test_contract13_migration_keeps_all_45_tables_and_backup(tmp_path):
    path=tmp_path/'v12.sqlite3'
    with SQLiteRepository(path) as r:r.connection.execute('PRAGMA user_version=12');before,columns=migrations.preserved_snapshot(r.connection)
    with pytest.raises(ValueError):SQLiteRepository(path,allow_upgrade=False)
    with SQLiteRepository(path) as r:
        report=r.migration_report;assert report['from_version']==12 and report['to_version']==13
        assert migrations.preserved_snapshot(r.connection,columns)[0]==before and len(migrations.table_names(r.connection))==45
        with sqlite3.connect(report['backup']) as db:assert db.execute('PRAGMA user_version').fetchone()[0]==12
