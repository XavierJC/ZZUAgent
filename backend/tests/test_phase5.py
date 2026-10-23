"""Release immutability and actual learning services, never paid models."""
import json,sqlite3
from copy import deepcopy
from uuid import uuid4
import pytest
from eduagent.domain.architecture import ArchitectureError
from eduagent.services.course_releases import CourseReleases,digest
from eduagent.services.teaching import TeachingService
from eduagent.services.architectures import ArchitectureService
from eduagent.services.workbench import WorkbenchService
from eduagent.agent.settings import AgentSettings
from eduagent.agent.deepseek import ModelReply
from eduagent.services.knowledge import CourseSources
from eduagent.retrieval.index import CourseIndex
from eduagent.storage import migrations
from eduagent.storage.sqlite import SQLiteRepository
from test_architectures import example

def cmd(**kw):return dict(request_id=str(uuid4()),**kw)
@pytest.fixture
def course(service,data_dir):
    service.register('student-b');r=CourseReleases(service,data_dir);r.ensure_demo()
    return r
def begin(r):
    t=TeachingService(r.learning,r.data_dir)
    release=r.list('student-a')['items'][0]
    key=t.begin('student-a',cmd(release_id=release['id'],goals=['logistic_regression']))['session_id']
    return t,key
def draft(r,**changes):
    p=dict(title='自建发布测试',sources=[{k:s[k] for k in ('source_type','source_id','source_version')} for s in r.course_sources()],reviewed_question_ids=[],reviewer='')
    p.update(changes);key=r.save('student-a',cmd(payload=p))['draft_id'];return key,p
def publish(r,key,kind='demo'):
    c=r.check('student-a',key);return r.publish('student-a',key,cmd(expected_revision=c['revision'],snapshot_hash=c['snapshot_hash'],kind=kind,confirmed=True))

def test_demo_does_not_claim_review_or_activate_40_candidates(course):
    r=course;data=r.builder('student-a');release=data['releases'][0]
    assert release['kind']=='demo' and len(release['question_versions'])==10 and data['candidate_count']==40 and data['additional_candidate_count']==30
    assert all(q.review_status=='pending' for q in r.learning.catalog.questions.values())
    assert 'review_questions' not in release

def test_read_refresh_never_allocates_or_diagnoses_from_prior(course):
    t,key=begin(course);before=migrations.fact_snapshot(t.db)
    for _ in range(3):
        s=t.state('student-a',key);assert s['decision'] is None and not s['has_objective_evidence']
        assert all(i['objective']['probability'] is None for i in s['guidance']['items'])
        assert s['next_task']['action']=='diagnose'
        assert 'mastery' not in s['next_task']['evidence']
        assert t.latest('student-a')['session']['id']==key
    assert migrations.fact_snapshot(t.db)==before

def test_real_score_bkt_and_provenance_atomic_idempotent(course):
    t,key=begin(course);body=cmd(expected_learning_revision=0)
    allocation=t.allocate('student-a',key,body)
    assert t.allocate('student-a',key,body)['replayed']
    d=allocation['decision'];q=t.learning.catalog.questions[d['question']['id']]
    answer=cmd(decision_id=d['decision_id'],answer=q.answer)
    result=t.submit('student-a',key,answer);assert result['result']['correct'] and t.submit('student-a',key,answer)['replayed']
    assert t.learning.snapshot('student-a').revision==1
    history=t.history('student-a')['items'];assert history[0]['course_provenance']['release_id']==result['release_id']
    assert t.state('student-a',key)['next_task']['action']=='practice'
    assert t.current_decision('student-a') is None

def test_wrong_answer_changes_rule_reason_not_manual_probability(course):
    t,key=begin(course);d=t.allocate('student-a',key,cmd(expected_learning_revision=0))['decision']
    answer=t.learning.catalog.questions[d['question']['id']].answer
    t.submit('student-a',key,cmd(decision_id=d['decision_id'],answer=next(k for k in 'ABCD' if k!=answer)))
    state=t.state('student-a',key);assert state['next_task']['action']=='review' and '答错' in state['next_task']['reason']

def test_legacy_history_and_allocation_remain_unbound(course):
    l=course.learning;d=l.next_action('student-a');l.submit('student-a',d.decision_id,'A','legacy-event')
    legacy=l.next_action('student-a');before=migrations.fact_snapshot(l.repository.connection)
    t,key=begin(course);state=t.state('student-a',key)
    assert state['history'][0]['course_provenance']['release_id'] is None and state['decision_origin']['release_id'] is None
    allocated=t.allocate('student-a',key,cmd(expected_learning_revision=1))
    assert allocated['allocation_origin']=='legacy_unbound' and allocated['decision']['decision_id']==legacy.decision_id
    assert migrations.fact_snapshot(t.db)==before

def test_concurrent_old_revision_and_student_scope(course):
    t,key=begin(course)
    with pytest.raises(ArchitectureError):t.state('student-b',key)
    with pytest.raises(ArchitectureError):t.allocate('student-a',key,cmd(expected_learning_revision=99))
    body=cmd(expected_learning_revision=0);t.allocate('student-a',key,body)
    with pytest.raises(ArchitectureError):t.allocate('student-a',key,dict(body,expected_learning_revision=1))

def test_release_draft_publish_frozen_and_cas(course):
    r=course;key,p=draft(r);checked=r.check('student-a',key)
    assert not checked['formal_allowed']
    with pytest.raises(ArchitectureError):publish(r,key,'reviewed')
    body=cmd(expected_revision=1,snapshot_hash=checked['snapshot_hash'],kind='demo',confirmed=True)
    release=r.publish('student-a',key,body);assert r.publish('student-a',key,body)['replayed']
    original=r.row('student-a',release['release_id'])['snapshot_json']
    r.save('student-a',cmd(expected_revision=1,payload=dict(p,title='新草稿')),key)
    assert r.row('student-a',release['release_id'])['snapshot_json']==original
    with pytest.raises(ArchitectureError):r.save('student-a',cmd(expected_revision=1,payload=p),key)
    with pytest.raises(ArchitectureError):r.draft_row('student-b',key)

def test_explicit_reviewed_release_requires_published_architecture_and_all_original_answers(course):
    r=course;a=ArchitectureService(r.learning);key=a.create('student-a',cmd(name='已确认结构'))['architecture_id']
    g=example();a.save('student-a',key,cmd(expected_revision=1,graph=g));a.publish('student-a',key,cmd(expected_revision=2,confirmed=True))
    did,p=draft(r,architecture_id=key,architecture_version=1,reviewer='合成自动测试审核声明，非真实人工审核',reviewed_question_ids=list(r.learning.catalog.questions))
    assert r.check('student-a',did)['formal_allowed']
    published=publish(r,did,'reviewed');assert r.row('student-a',published['release_id'])['kind']=='reviewed'
    assert all(q.review_status=='pending' for q in r.learning.catalog.questions.values())

@pytest.mark.parametrize('reviewed',[['new-ai-question'],[{}],['lr_01','lr_01']])
def test_cannot_admit_candidate_or_personal_question(course,reviewed):
    with pytest.raises(ArchitectureError):draft(course,reviewed_question_ids=reviewed)

def test_versioned_source_change_invalidates_release_not_history(course,tmp_path):
    import shutil
    copied=tmp_path/'data';shutil.copytree(course.data_dir,copied,ignore=shutil.ignore_patterns('local','evaluation'))
    r=CourseReleases(course.learning,copied);key,p=draft(r);published=publish(r,key)
    row=r.row('student-a',published['release_id']);before=row['snapshot_json']
    path=copied/'materials/linear_regression.md';path.write_text(path.read_text(encoding='utf-8')+'\nchanged',encoding='utf-8')
    assert not r.validity(row)['usable'] and r.row('student-a',published['release_id'])['snapshot_json']==before
    with pytest.raises(ArchitectureError):r.publish('student-a',key,cmd(expected_revision=1,snapshot_hash='a'*64,kind='demo',confirmed=True))

def test_savepoint_failure_rolls_back_scoring_and_provenance(course,monkeypatch):
    t,key=begin(course);d=t.allocate('student-a',key,cmd(expected_learning_revision=0))['decision'];before=migrations.fact_snapshot(t.db)
    original=t.learning.submit
    def fail_after_score(*args):original(*args);raise RuntimeError('synthetic failure after core service')
    monkeypatch.setattr(t.learning,'submit',fail_after_score)
    with pytest.raises(RuntimeError):t.submit('student-a',key,cmd(decision_id=d['decision_id'],answer='A'))
    assert migrations.fact_snapshot(t.db)==before and t.db.execute('select count(*) from teaching_events').fetchone()[0]==0

def test_lesson_local_rag_sources_and_no_score_writes(course):
    r=course;t,key=begin(r);sources=CourseSources(CourseIndex(r.data_dir/'materials',set(r.learning.catalog.knowledge)),r.data_dir/'materials')
    t.workbench_factory=lambda l:WorkbenchService(l,sources,True,AgentSettings())
    selected=r.list('student-a')['items'][0]['retrieval_scope'];before=migrations.fact_snapshot(t.db)
    request=cmd(question='梯度下降的更新方向是什么',sources=selected,course_id='machine_learning',mode='local',allow_personal_external=False)
    answer=t.explain('student-a',key,request)
    assert answer['model_calls']==0 and answer['citations'] and answer['lesson_context']['goals']
    assert t.explain('student-a',key,request)['answer']==answer['answer']
    assert migrations.fact_snapshot(t.db)==before
    with pytest.raises(ArchitectureError):t.explain('student-a',key,dict(request,request_id=str(uuid4()),sources=[]))
    with pytest.raises(ArchitectureError):t.explain('student-a',key,dict(request,request_id=str(uuid4()),sources=[dict(selected[0],source_version='unselected-version')]))

def test_schema10_failure_backup_and_recovery(tmp_path,catalog,monkeypatch):
    from eduagent.services.learning import LearningService
    path=tmp_path/'old.sqlite3'
    with SQLiteRepository(path) as repo:
        LearningService(catalog,repo).register('a')
        for table in reversed(migrations.RELEASE_TABLES):repo.connection.execute('DROP TABLE '+table)
        repo.connection.execute('pragma user_version=10');before,columns=migrations.preserved_snapshot(repo.connection)
    ddl=migrations.RELEASES;monkeypatch.setattr(migrations,'RELEASES',(*ddl[:1],'INVALID SQL'))
    with pytest.raises(sqlite3.Error):SQLiteRepository(path)
    with sqlite3.connect(path) as db:assert db.execute('pragma user_version').fetchone()[0]==10 and migrations.preserved_snapshot(db)[0]==before
    monkeypatch.setattr(migrations,'RELEASES',ddl)
    with SQLiteRepository(path) as repo:
        assert repo.migration_report['from_version']==10 and len(migrations.table_names(repo.connection))==43
        assert migrations.preserved_snapshot(repo.connection,columns)[0]==before
        with sqlite3.connect(repo.migration_report['backup']) as old:assert migrations.preserved_snapshot(old)[0]==before

def test_star_demo_identifier_cannot_publish_to_global_scope(course):
    r=course;r.learning.register('*');payload=dict(title='私有演示资料',sources=[{k:s[k] for k in ('source_type','source_id','source_version')} for s in r.course_sources()],reviewed_question_ids=[],reviewer='')
    key=r.save('*',cmd(payload=payload))['draft_id'];c=r.check('*',key)
    value=r.publish('*',key,cmd(expected_revision=1,snapshot_hash=c['snapshot_hash'],kind='demo',confirmed=True))
    assert r.row('*',value['release_id'])['scope_key']=='student:*'
    assert r.db.execute("SELECT count(*) FROM course_releases WHERE scope_key='*'").fetchone()[0]==1

def test_course_question_exhaustion_is_explicit_without_allocating_preview(course):
    t,key=begin(course)
    for revision in range(2):
        d=t.allocate('student-a',key,cmd(expected_learning_revision=revision))['decision'];correct=t.learning.catalog.questions[d['question']['id']].answer
        t.submit('student-a',key,cmd(decision_id=d['decision_id'],answer=next(k for k in 'ABCD' if k!=correct)))
    before=migrations.fact_snapshot(t.db);state=t.state('student-a',key)
    assert state['next_task']['action']=='stopped' and state['next_task']['stop_reason']=='insufficient_questions'
    assert migrations.fact_snapshot(t.db)==before

def test_explicit_begin_continues_unanswered_legacy_without_new_allocation(course):
    old=course.learning.next_action('student-a');before=migrations.fact_snapshot(course.db)
    t,key=begin(course);assert migrations.fact_snapshot(course.db)==before
    result=t.submit('student-a',key,cmd(decision_id=old.decision_id,answer='B'))
    assert result['result']['decision_id']==old.decision_id
    assert t.history('student-a')['items'][0]['course_provenance']['allocation_origin']=='legacy_unbound'
