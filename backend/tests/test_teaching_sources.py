"""Reviewed teacher evidence; all provider responses in this file are mocked."""
from dataclasses import replace
import json
from uuid import uuid4
import pytest
from eduagent.services.teaching_sources import TeachingSources
from eduagent.services.documents import DocumentsService
from eduagent.services.architectures import ArchitectureService
from eduagent.services.knowledge import KnowledgeService,SourceChanged,IndexUnavailable
from eduagent.services.resources import resource_id
from eduagent.services.workbench import WorkbenchService
from eduagent.services.course_releases import CourseReleases
from eduagent.storage import migrations
from eduagent.agent.settings import AgentSettings
from test_documents import upload,tick
from test_workbench import FakeModel

def cmd(**kw):return dict(request_id=str(uuid4()),**kw)

@pytest.fixture
def pilot(service,tmp_path):
    service.register('student-b')
    repo=service.repository;repo.document_root=tmp_path/'files';d=DocumentsService(repo,repo.document_root)
    doc,_=upload(d,b'# Precision and recall\n\nPrecision is TP/(TP+FP). Recall is TP/(TP+FN).',student='student-a')
    tick(d);doc=d.get('student-a',doc['id'])
    a=ArchitectureService(service);key=a.create('student-a',cmd(name='Synthetic test framework'))['architecture_id'];cid=str(uuid4())
    chapter=str(uuid4())
    g=dict(name='Synthetic test framework',chapters=[dict(id=chapter,title='Evaluation')],concepts=[dict(id=cid,name='Precision and recall',chapter_ids=[chapter],formal_knowledge_ids=['model_evaluation'])],relations=[])
    a.save('student-a',key,cmd(expected_revision=1,graph=g))
    t=TeachingSources(repo);u=dict(repo.connection.execute('SELECT * FROM document_units WHERE document_id=?',(doc['id'],)).fetchone())
    body=cmd(document_id=doc['id'],run_id=u['run_id'],ordinal=u['ordinal'],architecture_id=key,concept_id=cid,start_offset=0,end_offset=len(u['content_md']))
    return service,d,doc,a,key,t,body

def confirm(p):
    l,d,doc,a,key,t,body=p
    x=t.create('student-a',body)
    a.publish('student-a',key,cmd(expected_revision=2,confirmed=True))
    review=cmd(expected_revision=1,confirmed=True,architecture_version=1,reviewer='synthetic fixture, not real material review')
    t.review('student-a',x['id'],review)
    s=t.sources('student-a')[0];ref={k:s[k] for k in ('source_type','source_id','source_version')}
    return x,ref,review

def test_candidate_requires_confirmed_concept_and_is_not_searchable(pilot):
    l,d,doc,a,key,t,b=pilot;x=t.create('student-a',b)
    assert t.sources('student-a')==[]
    with pytest.raises(ValueError):t.review('student-a',x['id'],cmd(expected_revision=1,confirmed=True,architecture_version=1,reviewer='fixture'))
    assert t.row('student-a',x['id'])['status']=='candidate'

def test_real_page_slice_citation_and_scope_without_bkt(pilot):
    l,d,doc,a,key,t,b=pilot;facts=migrations.fact_snapshot(l.repository.connection);x,ref,_=confirm(pilot)
    k=KnowledgeService(l.catalog,l.repository);r=k.search('student-a','Precision recall',[ref])['items']
    assert len(r)==1 and r[0]['document_id']==doc['id'] and r[0]['page_number']==1
    assert r[0]['raw_md']==t.row('student-a',x['id'])['original_text']
    assert k.sources('student-b')['items']==[]
    with pytest.raises(ValueError):k.search('student-b','Precision',[ref])
    with pytest.raises(ValueError):k.search('student-a','Precision',[])
    assert migrations.fact_snapshot(l.repository.connection)==facts

def test_idempotency_conflict_and_old_revision(pilot):
    _,_,_,_,_,t,b=pilot;x,ref,review=confirm(pilot)
    assert t.create('student-a',b)['replayed'] and t.review('student-a',x['id'],review)['replayed']
    with pytest.raises(ValueError):t.create('student-a',dict(b,excerpt_md='different'))
    with pytest.raises(ValueError):t.review('student-a',x['id'],cmd(expected_revision=1,confirmed=False))

@pytest.mark.parametrize('change',['revoke','delete','reparse','tamper'])
def test_current_retrieval_invalidates_on_source_or_review_change(pilot,change):
    l,d,doc,a,key,t,b=pilot;x,ref,_=confirm(pilot);k=KnowledgeService(l.catalog,l.repository)
    assert k.search('student-a','Precision',[ref])['items']
    if change=='revoke':t.review('student-a',x['id'],cmd(expected_revision=2,confirmed=False))
    elif change=='tamper':
        version=l.repository.connection.execute('SELECT storage_key FROM document_versions WHERE id=?',(doc['version']['id'],)).fetchone()[0]
        (d.files.root/version).write_bytes(b'damaged')
    else:
        d.mutate('student-a',doc['id'],cmd(expected_revision=doc['revision']),'delete' if change=='delete' else 'parse')
    with pytest.raises(ValueError):k.search('student-a','Precision',[ref])

def test_only_selected_teacher_source_is_scored(pilot):
    l,d,doc,a,key,t,b=pilot;_,ref,_=confirm(pilot)
    # A course-only request with no course component never enumerates teacher chunks.
    from unittest.mock import patch
    with patch.object(TeachingSources,'search',side_effect=AssertionError('must not read teacher content')):
        with pytest.raises(ValueError):KnowledgeService(l.catalog,l.repository).search('student-a','Precision',[dict(source_type='course_material',source_id='missing',source_version='old')])

def test_teacher_model_consent_is_independent_and_per_round(pilot):
    l,d,doc,a,key,t,b=pilot;_,ref,_=confirm(pilot);model=FakeModel()
    settings=AgentSettings(api_key='synthetic',enabled=True)
    w=WorkbenchService(l,None,True,settings,lambda:model)
    body=cmd(question='Precision recall',sources=[ref],course_id='machine_learning',mode='model',allow_personal_external=True)
    out=w.ask('student-a',body);assert out['reason']=='teacher_consent_required' and model.calls==0
    allowed=cmd(**{k:v for k,v in body.items() if k!='request_id'},allow_teacher_external=True)
    out=w.ask('student-a',allowed);assert out['status']=='complete' and model.calls==1 and out['citations'][0]['page_number']==1
    assert w.ask('student-a',allowed)['request_id']==allowed['request_id'] and model.calls==1
    assert w.get('student-a',allowed['request_id'])['citations'][0]['raw_md']

def test_teacher_tool_cannot_expand_source_scope(pilot):
    l,d,doc,a,key,t,b=pilot;_,ref,_=confirm(pilot)
    model=FakeModel(tool=('retrieve_selected_sources',{'query':'Precision','student_id':'student-b'}))
    w=WorkbenchService(l,None,True,AgentSettings(api_key='synthetic',enabled=True),lambda:model)
    out=w.ask('student-a',cmd(question='Precision',sources=[ref],course_id='machine_learning',mode='model',allow_personal_external=False,allow_teacher_external=True))
    assert out['reason']=='tool_scope_rejected' and model.calls==1

def test_release_binds_reviewed_teacher_segments_without_changing_bank(pilot,data_dir):
    l,d,doc,a,key,t,b=pilot;_,ref,_=confirm(pilot);r=CourseReleases(l,data_dir)
    draft=r.save('student-a',cmd(payload=dict(title='Synthetic pilot',architecture_id=key,architecture_version=1,sources=[ref],reviewed_question_ids=[],reviewer='')))['draft_id']
    checked=r.check('student-a',draft)
    release=r.publish('student-a',draft,cmd(expected_revision=1,snapshot_hash=checked['snapshot_hash'],kind='demo',confirmed=True))
    out=r.view(r.row('student-a',release['release_id']))
    assert out['retrieval_scope']==[ref] and len(out['question_versions'])==10 and out['usable']
    row=t.listing('student-a')['items'][0];t.review('student-a',row['id'],cmd(expected_revision=2,confirmed=False))
    assert not r.view(r.row('student-a',release['release_id']))['usable']

def test_unclear_transcription_stays_candidate_and_bad_range_rejected(pilot):
    l,d,doc,a,key,t,b=pilot
    with pytest.raises(ValueError):t.create('student-a',dict(b,end_offset=999999))
    x=t.create('student-a',dict(b,excerpt_md='Unverified image transcription'))
    assert t.row('student-a',x['id'])['excerpt_origin']=='corrected_transcription' and t.sources('student-a')==[]

def test_release_cannot_claim_an_unrelated_architecture_version(pilot,data_dir):
    l,d,doc,a,key,t,b=pilot;_,ref,_=confirm(pilot);r=CourseReleases(l,data_dir)
    with pytest.raises(ValueError):r.save('student-a',cmd(payload=dict(title='Wrong structure',sources=[ref],reviewed_question_ids=[],reviewer='')))
