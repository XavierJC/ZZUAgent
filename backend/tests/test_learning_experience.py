"""Local page reading retains scope and versions; no model or learning writes."""
import json
import pytest
from pydantic import ValidationError
from eduagent.services.documents import DocumentsService
from eduagent.services.knowledge import KnowledgeService, SourceChanged
from eduagent.services.workbench import WorkbenchService
from eduagent.domain.notes import NoteNotFound
from eduagent.storage import migrations
from eduagent.api.workbench_schemas import SourceOpen, SourcePreview
from test_documents import upload, tick
from test_personal_bank import command
from test_personal_bank import bank
from eduagent.services.question_intake import auto_entry
from document_fixtures import pdf_bytes


@pytest.fixture
def pages(service, tmp_path):
    service.register('student-b')
    documents=DocumentsService(service.repository,tmp_path/'files')
    doc,_=upload(documents,pdf_bytes(('Gradient descent follows negative gradients and updates weights.', '',
                                    'Model evaluation uses precision and recall to compare predictions.')),
                 name='synthetic.pdf',student='student-a')
    tick(documents)
    knowledge=KnowledgeService(service.catalog,service.repository)
    source=next(s for s in knowledge.sources('student-a')['items'] if s['source_type']=='uploaded_document')
    ref={key:source[key] for key in ('source_type','source_id','source_version')}
    return service,documents,doc,knowledge,ref


def test_page_reader_recovers_exact_text_and_sparse_pages_without_changing_facts(pages):
    learning,docs,doc,knowledge,ref=pages
    before=migrations.preserved_snapshot(learning.repository.connection)[0]
    bench=WorkbenchService(learning)
    first=bench.preview('student-a',ref,1)
    third=bench.preview('student-a',ref,3)
    sparse=bench.preview('student-a',ref,2)
    assert first['raw_md']==docs.units('student-a',doc['id'])['items'][0]['content_md']
    assert 'precision' in third['raw_md'] and 'precision' not in first['raw_md']
    assert [p['ordinal'] for p in first['pages']]==[1,2,3]
    assert [p['readable'] for p in first['pages']]==[True,False,True]
    assert sparse['raw_md']=='' and not sparse['pages'][1]['readable']
    assert SourcePreview.model_validate(first).page_number==1
    assert migrations.preserved_snapshot(learning.repository.connection)[0]==before
    assert 'preview_units' not in knowledge.sources('student-a')['items'][0]
    assert not learning.repository.connection.execute('SELECT 1 FROM workbench_runs').fetchone()


def test_page_reader_refuses_wrong_student_missing_page_and_stale_versions(pages):
    learning,docs,doc,_,ref=pages;bench=WorkbenchService(learning)
    with pytest.raises(NoteNotFound):bench.preview('student-b',ref,1)
    with pytest.raises(NoteNotFound):bench.preview('student-a',ref,4)
    docs.mutate('student-a',doc['id'],command(expected_revision=1,title='Updated source'),'update')
    with pytest.raises(SourceChanged):bench.preview('student-a',ref,1)


@pytest.mark.parametrize('page',[0,201,-1,True,'1'])
def test_preview_rejects_invalid_page_at_service_boundary(pages,page):
    learning,_,_,_,ref=pages
    with pytest.raises(ValueError):WorkbenchService(learning).preview('student-a',ref,page)


def test_preview_json_remains_strict_and_legacy_open_is_compatible(pages):
    learning,_,_,_,ref=pages
    assert SourceOpen.model_validate(ref).page is None
    assert SourceOpen.model_validate(dict(ref,page=2)).page==2
    with pytest.raises(ValidationError):SourceOpen.model_validate(dict(ref,student_id='student-b'))
    assert 'Gradient' in WorkbenchService(learning).preview('student-a',ref)['raw_md']


def test_deleted_source_cannot_be_read_with_previous_page_reference(pages):
    learning,docs,doc,_,ref=pages
    docs.mutate('student-a',doc['id'],command(expected_revision=1),'delete')
    with pytest.raises(NoteNotFound):WorkbenchService(learning).preview('student-a',ref,1)


def test_auto_intake_fills_optional_defaults_and_next_practice_does_not_change_bkt(bank):
    before=migrations.fact_snapshot(bank.db)
    key,status=auto_entry(bank,'student-a',dict(question_type='short_answer',stem='解释学习率对梯度下降步长的影响。'),{},None,'unknown')
    assert status=='ready' and bank.get('student-a',key)['payload']['concepts']==[]
    result=bank.start('student-a',command())
    assert bank.session('student-a',result['session_id'])['question_id']==key
    assert migrations.fact_snapshot(bank.db)==before


def test_legacy_missing_optional_concept_list_is_read_compatibly_without_rewriting_question(bank):
    key,_=auto_entry(bank,'student-a',dict(question_type='short_answer',stem='解释学习率对梯度下降步长的影响。'),{},None,'unknown')
    raw=json.loads(bank.db.execute('SELECT payload_json FROM personal_questions WHERE id=?',(key,)).fetchone()[0]);raw.pop('concepts')
    encoded=json.dumps(raw);bank.db.execute('UPDATE personal_questions SET payload_json=? WHERE id=?',(encoded,key))
    result=bank.start('student-a',command())
    assert bank.session('student-a',result['session_id'])['question_id']==key
    assert bank.db.execute('SELECT payload_json FROM personal_questions WHERE id=?',(key,)).fetchone()[0]==encoded
