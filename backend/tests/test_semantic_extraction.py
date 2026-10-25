"""Engineering behavior with synthetic model replies, not teaching efficacy."""
from copy import deepcopy
import json
import sqlite3
from uuid import uuid4
import pytest
from eduagent.agent.deepseek import ModelReply,ModelError
from eduagent.agent.settings import AgentSettings
from eduagent.agent.question_extractor import validate
from eduagent.domain.architecture import ArchitectureError
from eduagent.domain.personal_bank import question,QUESTION_TYPES
from eduagent.services.personal_bank import PersonalBankService
from eduagent.services.question_extraction import QuestionExtractionService
from eduagent.storage import migrations
from eduagent.storage.sqlite import SQLiteRepository
from test_personal_bank import command,payload

RAW='1. 简答：说明过拟合。\nA. 解释现象。\nB. 描述解决方法。\n答案：训练好，泛化差。'
def response(raw=RAW,**changes):
    p=dict(number='1',question_type='short_answer',stem='简答：说明过拟合。\nA. 解释现象。\nB. 描述解决方法。',options=[],answer=None,answer_text='训练好，泛化差。',concepts=[],explanation='')
    return dict(questions=[dict(payload=dict(p,**changes),source_units=[1],quotes=[raw])],warnings=[])

class Fake:
    def __init__(self,values=None,hook=None):self.values=values or [response()];self.calls=0;self.hook=hook
    def complete(self,messages,tools):
        assert not tools
        self.calls+=1
        if self.hook:self.hook(messages)
        value=self.values[min(self.calls-1,len(self.values)-1)]
        if isinstance(value,Exception):raise value
        return ModelReply(dict(content=json.dumps(value,ensure_ascii=False)),10,30)

@pytest.fixture
def extraction(service,data_dir):
    service.register('student-b');bank=PersonalBankService(service,data_dir/'materials');fake=Fake()
    result=QuestionExtractionService(bank,AgentSettings(enabled=True,api_key='synthetic-only'),client_factory=lambda _:fake)
    result.fake=fake
    return result

def run(s,body=None):
    task=s.create('student-a',body or command(text=RAW,consent=True))
    s.execute(s.claim());return s.get('student-a',task['request_id'])

@pytest.mark.parametrize('kind',QUESTION_TYPES)
def test_all_types_save_without_rewriting_old_question(extraction,kind):
    bank=extraction.bank
    p=payload(question_type=kind)
    if kind=='true_false':p['answer']='true'
    if kind not in ('single_choice','true_false','multiple_choice'):p.update(options=[],answer=None,answer_text='原文参考 $x^2$')
    qid=bank.save('student-a',command(payload=p))['question_id']
    assert bank.get('student-a',qid)['payload']['question_type']==kind

def test_subjective_answer_subquestions_draft_restore_no_bkt(extraction):
    bank=extraction.bank;before=migrations.fact_snapshot(bank.db)
    p=question(dict(stem='公共题设',question_type='calculation',answer_text='原文结果',subquestions=[dict(stem='求导',question_type='calculation')]))
    qid=bank.save('student-a',command(payload=p,status='practice',reviewed=True,confirm_answer=True))['question_id']
    sid=bank.start('student-a',command(question_id=qid))['session_id']
    draft=command(expected_revision=0,response_text='我的计算 $2x$',needs_review=True)
    assert bank.save_practice_draft('student-a',sid,draft)['revision']==1
    assert bank.save_practice_draft('student-a',sid,draft)['replayed']
    assert bank.session('student-a',sid)['draft']['response_text']=='我的计算 $2x$'
    with pytest.raises(ArchitectureError):bank.save_practice_draft('student-a',sid,command(expected_revision=0,response_text='旧草稿',needs_review=False))
    result=bank.submit('student-a',sid,command(selected_answer='我的计算 $2x$',needs_review=True))['result']
    assert result['score'] is None and result['needs_review'] and result['reference_answer']=='原文结果'
    assert bank.sessions('student-a',wrong_only=True)['items']==[]
    assert migrations.fact_snapshot(bank.db)==before

def test_durable_task_replay_scope_and_locked_identity(extraction):
    s=extraction;before=migrations.fact_snapshot(s.db);body=command(text=RAW,consent=True)
    task=run(s,body);assert task['status']=='complete' and task['model_calls']==1
    assert s.fake.calls==1 and s.create('student-a',body)['result']==task['result']
    assert s.get('student-a',body['request_id'])['result']==task['result'] and s.fake.calls==1
    with pytest.raises(ArchitectureError):s.create('student-a',dict(body,text='different'))
    with pytest.raises(ArchitectureError):s.get('student-b',body['request_id'])
    assert s.list('student-b')['items']==[]
    q=s.bank.get('student-a',task['result']['question_ids'][0]);assert q['payload']['question_type']=='short_answer' and not q['payload']['options']
    assert q['payload']['answer_text']=='训练好，泛化差。' and q['answer_provenance']=='model_inferred'
    assert migrations.fact_snapshot(s.db)==before

def test_model_network_has_no_sqlite_write_transaction(extraction):
    s=extraction
    def check(_):
        assert not s.db.in_transaction
        path=s.db.execute('pragma database_list').fetchone()[2]
        with sqlite3.connect(path,timeout=.1) as second:second.execute('BEGIN IMMEDIATE');second.rollback()
    s.fake.hook=check
    assert run(s)['status']=='complete'

@pytest.mark.parametrize('code',['model_timeout','network_error','model_output_truncated'])
def test_model_failure_never_auto_retries_or_loses_original(extraction,code):
    s=extraction;s.fake.values=[ModelError(code)]
    result=run(s);assert result['status']==('uncertain' if code!='model_output_truncated' else 'failed') and s.fake.calls==1
    assert not s.bank.listing('student-a')['items']
    assert json.loads(s.row('student-a',result['request_id'])['context_json'])['units'][0]['text']==RAW
    s.recover();assert s.claim() is None and s.fake.calls==1

def test_invalid_output_repair_is_bounded_and_does_not_invent_answer(extraction):
    s=extraction;s.fake.values=[response(answer_text='模型自己算出的答案'),response()]
    result=run(s);assert result['status']=='complete' and s.fake.calls==2
    s.fake.values=[response(answer_text='模型自己算出的答案')];s.fake.calls=0
    failed=run(s);assert failed['status']=='failed' and s.fake.calls==2

@pytest.mark.parametrize('mutation',['scope','quote','option','answer','tools'])
def test_source_and_field_validation_rejects_fabrications(mutation):
    value=response()
    if mutation=='scope':value['questions'][0]['source_units']=[2]
    if mutation=='quote':value['questions'][0]['quotes']=['未选资料']
    if mutation=='option':value['questions'][0]['payload']['options']=[dict(key='A',text='编造选项')]
    if mutation=='answer':value['questions'][0]['payload']['answer_text']='编造答案'
    if mutation=='tools':value['student_id']='other'
    with pytest.raises(ValueError):validate(json.dumps(value),[dict(text=RAW)],False)

def test_source_update_during_network_prevents_publication(extraction):
    s=extraction
    def change(_):s.db.execute("UPDATE course_resources SET content_md='changed' WHERE source_type='text'")
    s.fake.hook=change
    result=run(s);assert result['status']=='stale' and not s.bank.listing('student-a')['items']

def test_target_edit_during_network_never_overwrites_human_work(extraction):
    s=extraction;bank=s.bank;qid=bank.save('student-a',command(payload=payload()))['question_id']
    def edit(_):bank.save('student-a',command(expected_revision=1,payload=payload(stem='人工新修改')),qid)
    s.fake.hook=edit
    result=run(s,command(text=RAW,consent=True,target_question_id=qid,target_revision=1))
    assert result['status']=='stale' and bank.get('student-a',qid)['payload']['stem']=='人工新修改'

def test_restart_marks_unconfirmed_without_reissue(extraction):
    s=extraction;task=s.create('student-a',command(text=RAW,consent=True));s.claim();s.recover()
    assert s.get('student-a',task['request_id'])['status']=='uncertain' and s.claim() is None and s.fake.calls==0

def test_consent_and_disabled_model_do_not_transmit(extraction):
    s=extraction
    with pytest.raises(ArchitectureError):s.create('student-a',command(text=RAW,consent=False))
    s.agent=AgentSettings()
    with pytest.raises(ArchitectureError):s.create('student-a',command(text=RAW,consent=True))
    assert s.fake.calls==0

def test_true_false_canonical_controls_are_not_source_options():
    raw='1. 判断：训练好保证泛化好。\n答案：错误'
    value=response(raw,stem='判断：训练好保证泛化好。',question_type='true_false',answer='false',answer_text='')
    entries,_=validate(json.dumps(value),[dict(text=raw)],False)
    assert entries[0]['payload']['answer']=='false' and len(entries[0]['payload']['options'])==2

def test_schema9_additive_backup_and_rollback(tmp_path,catalog,monkeypatch):
    from eduagent.services.learning import LearningService
    path=tmp_path/'v9.sqlite3'
    with SQLiteRepository(path) as repo:
        LearningService(catalog,repo).register('a')
        for name in reversed(migrations.EXTRACTION_TABLES + migrations.RELEASE_TABLES + migrations.TEACHER_TABLES + migrations.NOTEBOOK_TABLES):repo.connection.execute('DROP TABLE '+name)
        repo.connection.execute('pragma user_version=9');before,columns=migrations.preserved_snapshot(repo.connection)
    ddl=migrations.EXTRACTION;monkeypatch.setattr(migrations,'EXTRACTION',(*ddl[:1],'INVALID DDL'))
    with pytest.raises(sqlite3.Error):SQLiteRepository(path)
    with sqlite3.connect(path) as db:assert db.execute('pragma user_version').fetchone()[0]==9 and migrations.preserved_snapshot(db)[0]==before
    monkeypatch.setattr(migrations,'EXTRACTION',ddl)
    with SQLiteRepository(path) as repo:
        assert repo.migration_report['from_version']==9 and len(migrations.table_names(repo.connection))==50
        assert migrations.preserved_snapshot(repo.connection,columns)[0]==before
        with sqlite3.connect(repo.migration_report['backup']) as old:assert migrations.preserved_snapshot(old)[0]==before
