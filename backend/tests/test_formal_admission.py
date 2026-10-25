"""Additive real scoring, owner isolation, restart and old-version safety."""
from dataclasses import asdict
from copy import deepcopy
import importlib.util
import json
from pathlib import Path

import pytest

from eduagent.domain.catalog import Catalog
from eduagent.services.formal_admission import KEY, VERSION, checksum
from eduagent.services.learning import LearningService, SubmissionConflict
from eduagent.services.course_releases import CourseReleases
from eduagent.services.teaching import TeachingService
from eduagent.storage.sqlite import encode
from eduagent.storage.migrations import preserved_snapshot

spec = importlib.util.spec_from_file_location('admission_installer', Path(__file__).resolve().parents[2]/'scripts/admit_formal_questions.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


def record_for(service, data_dir):
    data = json.loads((data_dir/'candidates/questions-v2.json').read_text(encoding='utf-8'))
    return dict(version=VERSION, bank_version='admission-test-v1',
                previous_configuration=json.loads(service.repository.connection.execute("SELECT value FROM metadata WHERE key='configuration'").fetchone()[0]),
                shared_questions=data['questions'], personal_questions=[])


def activate(service, data_dir, record=None):
    record = record or record_for(service, data_dir)
    with service.repository.transaction():
        installer.install(service.repository, service.formal_admission.base, record)
    return LearningService(service.formal_admission.base, service.repository)


def test_admission_changes_only_metadata_and_old_code_cannot_bind(service, data_dir):
    before = preserved_snapshot(service.repository.connection)[0]
    base_config = record_for(service, data_dir)['previous_configuration']
    upgraded = activate(service, data_dir)
    after = preserved_snapshot(service.repository.connection)[0]
    assert {k:v for k,v in before.items() if k!='metadata'} == {k:v for k,v in after.items() if k!='metadata'}
    assert len(upgraded.catalog.questions) == 40
    assert len(upgraded.catalog.knowledge) == 5
    assert all(q.review_status == 'ai_checked' for q in upgraded.catalog.questions.values())
    with pytest.raises(ValueError, match='不能静默混用'):
        service.repository.bind_configuration(base_config)


def test_new_questions_fix_exhaustion_and_duplicate_submission_updates_once(service, data_dir):
    for index in range(2):
        decision = service.next_action('student-a')
        service.submit('student-a', decision.decision_id, 'A' if index==0 else 'B', 'old-'+str(index))
    stopped = service.next_action('student-a')
    assert stopped.stop_reason == 'insufficient_questions'
    old_receipts = service.history('student-a')
    upgraded = activate(service, data_dir)
    assert upgraded.repository.decision_at('student-a',2) == stopped
    assert upgraded.history('student-a') == old_receipts
    decision = upgraded.next_action('student-a')
    assert decision.question['id'] == 'lr_03'
    assert json.loads(upgraded.repository.connection.execute('SELECT value FROM metadata WHERE key=?',('formal-resumed:'+stopped.decision_id,)).fetchone()[0])['stop_reason']=='insufficient_questions'
    first = upgraded.submit('student-a',decision.decision_id,'C','new-event')
    assert first.bank_version == 'admission-test-v1'
    assert upgraded.submit('student-a',decision.decision_id,'C','new-event').replayed
    assert upgraded.snapshot('student-a').revision == 3
    assert len(upgraded.history('student-a')['items'])==3


def test_old_pending_question_keeps_original_bank_version(service, data_dir):
    old = service.next_action('student-a')
    upgraded = activate(service, data_dir)
    assert upgraded.next_action('student-a') == old
    result = upgraded.submit('student-a',old.decision_id,'B','pending-old')
    assert result.bank_version == service.formal_admission.base.bank_version


def test_old_release_remains_frozen_and_can_complete_new_question(service, data_dir):
    releases = CourseReleases(service,data_dir)
    key = releases.ensure_demo()
    frozen = releases.row('student-a',key)['snapshot_json']
    upgraded = activate(service,data_dir)
    releases = CourseReleases(upgraded,data_dir)
    assert releases.validity(releases.row('student-a',key))['usable']
    assert releases.row('student-a',key)['snapshot_json']==frozen
    teaching = TeachingService(upgraded,data_dir)
    session = teaching.begin('student-a',dict(request_id='c80c2aba-a111-4111-a111-111111111111',release_id=key,goals=['logistic_regression']))['session_id']
    state = teaching.state('student-a',session)
    assert state['assessment_bank']['question_count']==40 and state['decision'] is None
    assert state['guidance']['items'][0]['available_questions']==8
    for step in range(3):
        decision = teaching.allocate('student-a',session,dict(request_id=f'c80c2aba-a111-4111-a111-{step:012d}',expected_learning_revision=step))['decision']
        question = upgraded.catalog.questions[decision['question']['id']]
        answer = next(k for k in question.options if k!=question.answer) if step<2 else question.answer
        teaching.submit('student-a',session,dict(request_id=f'c80c2aba-a222-4222-a222-{step:012d}',decision_id=decision['decision_id'],answer=answer))
    assert upgraded.snapshot('student-a').revision==3
    assert teaching.history('student-a')['items'][0]['course_provenance']['question_snapshot']['id']=='lr_03'


@pytest.mark.parametrize('change',['answer','knowledge','parameters'])
def test_reject_changed_baseline_and_rollback_metadata(service,data_dir,change):
    record=record_for(service,data_dir)
    if change=='answer':record['shared_questions'][0]['answer']='A'
    elif change=='knowledge':record['shared_questions'][0]['knowledge_id']='unknown'
    else:record['previous_configuration']['parameters']['initial']=0.7
    before=preserved_snapshot(service.repository.connection)[0]
    with pytest.raises(ValueError):activate(service,data_dir,record)
    assert preserved_snapshot(service.repository.connection)[0]==before


@pytest.fixture
def private_admission(service,data_dir,tmp_path):
    from eduagent.services.documents import DocumentsService
    from eduagent.services.personal_bank import PersonalBankService
    from test_documents import upload,tick
    service.register('student-b')
    docs=DocumentsService(service.repository,tmp_path/'files')
    upload(docs,raw='判断题原文与参考答案'.encode(),student='student-a');tick(docs)
    bank=PersonalBankService(service,data_dir/'materials')
    item=next(i for i in bank.resources.items('student-a') if i['original_source_type']=='document')
    payload=dict(question_type='true_false',stem='逻辑回归标准训练损失是交叉熵。',answer='true')
    source=dict(original_source_type='document',original_source_id=item['original_source_id'],source_version=item['source_version'],run_id=item['parse_id'],origin_mode='local')
    key=bank._insert_question('student-a',payload,source)
    row=bank.row('student-a',key)
    record=record_for(service,data_dir)
    record['personal_questions']=[dict(student_id='student-a',personal_id=key,revision=1,payload_hash=checksum(payload),source_hash=checksum(source),source=source,answer_origin='source_extracted_by_ai',
        question=dict(id='private-test',version='r1',knowledge_id='logistic_regression',difficulty='medium',stem=payload['stem'],options={'A':'正确','B':'错误'},answer='A',explanation='标准逻辑回归通常以交叉熵训练。',source='本标识原题',review_status='ai_checked'))]
    return activate(service,data_dir,record),key,item['original_source_id']


def test_private_scope_and_source_change(private_admission):
    learning,key,document=private_admission
    assert len(learning.catalog_for('student-a').questions)==41
    assert len(learning.catalog_for('student-b').questions)==40
    assert 'private-test' not in learning.catalog_for('student-b').questions
    learning.repository.connection.execute('UPDATE personal_questions SET revision=revision+1 WHERE id=?',(key,))
    assert 'private-test' not in learning.catalog_for('student-a').questions


@pytest.mark.parametrize('change',['deleted','not_ready','new_version','archived'])
def test_private_deletion_and_not_ready_cannot_be_used(private_admission,change):
    learning,key,document=private_admission
    if change=='deleted':learning.repository.connection.execute("UPDATE course_documents SET deleted_at='deleted' WHERE id=?",(document,))
    elif change=='not_ready':learning.repository.connection.execute("UPDATE document_parse_runs SET status='failed' WHERE document_id=?",(document,))
    elif change=='new_version':learning.repository.connection.execute('UPDATE personal_questions SET revision=revision+1 WHERE id=?',(key,))
    else:learning.repository.connection.execute("UPDATE personal_questions SET status='archived' WHERE id=?",(key,))
    assert 'private-test' not in learning.catalog_for('student-a').questions


def test_private_question_really_scores_and_replay_is_idempotent(private_admission):
    learning,key,document=private_admission
    from eduagent.domain.models import Recommendation
    pending=Recommendation('private-decision','student-a',0,'diagnose','logistic_regression','fixture',
        {'bank_version':learning.catalog.bank_version},learning.catalog_for('student-a').questions['private-test'].public_view())
    learning.repository.save_decision(pending,'now')
    result=learning.submit('student-a','private-decision','A','private-event')
    assert result.correct and result.next_mastery > result.prior
    assert learning.submit('student-a','private-decision','A','private-event').replayed
    assert learning.snapshot('student-a').revision==1
    with pytest.raises(SubmissionConflict):learning.submit('student-b','private-decision','A','cross-owner')


def test_api_health_and_next_hide_answers(service,data_dir,tmp_path):
    from fastapi.testclient import TestClient
    from eduagent.api.app import create_app
    from eduagent.api.settings import APISettings
    activate(service,data_dir)
    app=create_app(APISettings(data_dir=data_dir,db_path=Path(service.repository.connection.execute('PRAGMA database_list').fetchone()[2]),retrieval_enabled=False))
    with TestClient(app) as client:
        assert client.get('/health').json()['question_count']==40
        decision=client.post('/api/v1/students/student-a/next').json()
        assert decision['question']['review_status']=='ai_checked'
        assert 'answer' not in decision['question'] and 'explanation' not in decision['question']
