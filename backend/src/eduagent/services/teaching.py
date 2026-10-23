"""Release-bound orchestration. The existing scorer/policy/BKT stay authoritative."""
from dataclasses import asdict
import json
from uuid import uuid4
from eduagent.domain.personal_bank import fail
from eduagent.documents.models import uuid_text
from eduagent.services.course_releases import CourseReleases,digest
from eduagent.services.guidance import GuidanceService
from eduagent.services.learning import now
from eduagent.storage.sqlite import encode

class TeachingService:
    def __init__(self,learning,data_dir,workbench_factory=None):
        self.learning,self.repo=learning,learning.repository;self.db=self.repo.connection
        self.releases=CourseReleases(learning,data_dir);self.workbench_factory=workbench_factory

    def session_row(self,student,key):
        self.learning._student(student);uuid_text(key)
        row=self.db.execute('SELECT * FROM teaching_sessions WHERE id=? AND student_id=? AND course_id=?',(key,student,'machine_learning')).fetchone()
        if not row:fail('当前学习标识下没有该学习会话','teaching_session_not_found',404)
        return dict(row)

    def _check(self,student,session):
        release=self.releases.row(student,session['release_id'])
        if not self.releases.validity(release)['usable']:fail('课程版本的来源或配置已变化，请检查课程发布状态','release_unavailable',409)
        return release

    def begin(self,student,body):
        def apply():
            release=self.releases.row(student,body['release_id'])
            if not self.releases.validity(release)['usable']:fail('所选课程版本暂不可开始','release_unavailable',409)
            learner=self.learning._student(student);goals=json.loads(learner['goals_json'])
            pending=self.repo.decision_at(student,learner['revision'])
            if pending and pending.question and self.db.execute('SELECT 1 FROM teaching_decisions WHERE decision_id=?',(pending.decision_id,)).fetchone():fail('当前学习会话还有未完成正式分配，请先恢复并完成','pending_other_session',409)
            if body['goals']!=goals:fail('已有学习标识目标固定；更换目标请使用新的演示学习标识','goal_conflict',409)
            self.learning.catalog.expand_goals(goals)
            if self.db.execute('SELECT count(*) FROM teaching_sessions WHERE student_id=?',(student,)).fetchone()[0]>=100:fail('本机标识最多保留100个学习会话',status=413)
            key=str(uuid4());stamp=now()
            self.db.execute('INSERT INTO teaching_sessions VALUES (?,?,?,?,?,?,?,?,?)',(key,student,'machine_learning',release['id'],encode(goals),learner['revision'],'goals',stamp,stamp))
            if pending and pending.question:
                # Explicitly entering a session may continue an already assigned
                # legacy question, without claiming its original release or
                # allocating another question. GET/refresh never does this.
                self.db.execute('INSERT INTO teaching_decisions VALUES (?,?,?,?,?,?,?)',(pending.decision_id,key,student,None,'legacy_unbound',encode(pending.question),stamp))
            return dict(session_id=key,release_id=release['id'])
        return self.releases.operation(student,body,'begin-session',apply)

    def _state(self,student,session):
        learner=self.learning._student(student);overview=GuidanceService(self.learning)._snapshot(student)
        decision=self.repo.decision_at(student,learner['revision'])
        next_task=self.learning.policy.decide(decision_id='read-only-preview',student_id=student,revision=learner['revision'],
            goals=tuple(json.loads(learner['goals_json'])),states=self.learning.status(student),answered=self.repo.answered_questions(student),catalog=self.learning.catalog)
        public=asdict(next_task);public.pop('question',None);public.pop('decision_id',None)
        # A preview is advice, never an assigned question or fabricated decision.
        if public['evidence'].get('attempts')==0:public['evidence'].pop('mastery',None)
        release=self.releases.row(student,session['release_id'])
        last=self.repo.recent_attempts(student,1)
        origin=None
        if decision:
            link=self.db.execute('SELECT * FROM teaching_decisions WHERE decision_id=?',(decision.decision_id,)).fetchone()
            origin=dict(release_id=link['release_id'],origin=link['origin']) if link else dict(release_id=None,origin='legacy_unbound')
        items=self.history(student)['items']
        explanations=[dict(request_id=r['request_id'],status=r['status'],context=json.loads(r['context_json'])) for r in self.db.execute('SELECT * FROM teaching_explanations WHERE session_id=? AND student_id=? ORDER BY created_at DESC,request_id LIMIT 20',(session['id'],student))]
        return dict(session={k:session[k] for k in ('id','release_id','stage','started_revision','created_at','updated_at')},release=self.releases.view(release),
            snapshot=asdict(self.learning.snapshot(student)),guidance=overview,next_task=public,
            decision=asdict(decision) if decision else None,decision_origin=origin,last_feedback=last[0] if last else None,
            history=items,explanations=explanations,has_objective_evidence=any(i['objective']['has_evidence'] for i in overview['items']),
            pending_diagnosis=[i['knowledge_id'] for i in overview['items'] if i['in_goal_path'] and not i['objective']['has_evidence']],
            history_compatibility='Old attempts and allocations without provenance remain legacy_unbound; no release is assigned retrospectively.')

    def state(self,student,key):
        with self.repo.transaction():return self._state(student,self.session_row(student,key))

    def latest(self,student):
        with self.repo.transaction():
            self.learning._student(student)
            row=self.db.execute('SELECT * FROM teaching_sessions WHERE student_id=? ORDER BY created_at DESC,id DESC LIMIT 1',(student,)).fetchone()
            return self._state(student,dict(row)) if row else dict(session=None,release=None,history=self.history(student)['items'])

    def current_decision(self,student):
        with self.repo.transaction():
            learner=self.learning._student(student);value=self.repo.decision_at(student,learner['revision'])
            return asdict(value) if value else None

    def allocate(self,student,key,body):
        def apply():
            session=self.session_row(student,key);release=self._check(student,session)
            learner=self.learning._student(student)
            if learner['revision']!=body['expected_learning_revision']:fail('答题状态已变化，请只读刷新后继续','revision_conflict',409)
            old=self.repo.decision_at(student,learner['revision']);decision=self.learning.next_action(student)
            link=self.db.execute('SELECT * FROM teaching_decisions WHERE decision_id=?',(decision.decision_id,)).fetchone()
            if link and link['session_id']!=key:fail('当前有其他学习会话的未完成分配，请恢复该会话','pending_other_session',409)
            if not link:
                self.db.execute('INSERT INTO teaching_decisions VALUES (?,?,?,?,?,?,?)',(decision.decision_id,key,student,release['id'] if not old else None,
                    'allocated_in_session' if not old else 'legacy_unbound',encode(decision.question),now()))
            self.db.execute('UPDATE teaching_sessions SET stage=?,updated_at=? WHERE id=?',('verification' if session['stage']=='explanation' else 'diagnosis',now(),key))
            return dict(session_id=key,decision=asdict(decision),allocation_origin='legacy_unbound' if old and not link else link['origin'] if link else 'allocated_in_session')
        return self.releases.operation(student,body,'allocate:'+key,apply)

    def submit(self,student,key,body):
        def apply():
            session=self.session_row(student,key);release=self.releases.row(student,session['release_id'])
            if json.loads(release['snapshot_json'])['configuration']!=self.releases.configuration():fail('评分配置已变化，不能按当前配置覆盖原分配','release_unavailable',409)
            link=self.db.execute('SELECT * FROM teaching_decisions WHERE decision_id=? AND session_id=? AND student_id=?',(body['decision_id'],key,student)).fetchone()
            if not link:fail('请先明确开始本学习会话的诊断或复测','decision_not_in_session',409)
            if self.repo.attempt(body['request_id']):fail('该事件已有旧记录，不能补认课程版本','event_already_recorded',409)
            result=self.learning.submit(student,body['decision_id'],body['answer'],body['request_id'])
            question=self.learning.catalog.questions[result.question_id]
            self.db.execute('INSERT INTO teaching_events VALUES (?,?,?,?,?,?,?)',(result.event_id,key,student,release['id'],link['origin'],encode(asdict(question)),now()))
            self.db.execute("UPDATE teaching_sessions SET stage='analysis',updated_at=? WHERE id=?",(now(),key))
            return dict(session_id=key,result=asdict(result),release_id=release['id'])
        return self.releases.operation(student,body,'answer:'+key,apply)

    def history(self,student):
        # Composition is safe inside an existing consistent snapshot/savepoint.
        with self.repo.transaction():
            result=self.learning.history(student)
            for event in result['items']:
                row=self.db.execute('SELECT session_id,release_id,allocation_origin,question_snapshot_json FROM teaching_events WHERE event_id=? AND student_id=?',(event['event_id'],student)).fetchone()
                event['course_provenance']=dict(session_id=row['session_id'],release_id=row['release_id'],allocation_origin=row['allocation_origin'],question_snapshot=json.loads(row['question_snapshot_json'])) if row else dict(session_id=None,release_id=None,allocation_origin='legacy_unbound')
            return result

    def explain(self,student,key,body):
        uuid_text(body['request_id']);checksum=digest([key,body])
        with self.repo.transaction():
            session=self.session_row(student,key)
            old=self.db.execute('SELECT * FROM teaching_explanations WHERE request_id=?',(body['request_id'],)).fetchone()
            if old:
                if old['student_id']!=student or old['session_id']!=key or old['request_hash']!=checksum:fail('讲解请求编号冲突','request_id_conflict',409)
                try:result=self.workbench_factory(self.learning).get(student,body['request_id'])
                except ValueError:return dict(request_id=body['request_id'],status='uncertain',reason='execution_unconfirmed',lesson_context=json.loads(old['context_json']))
                return self.explanation_view(student,result,json.loads(old['context_json']))
            release=self._check(student,session);snapshot=json.loads(release['snapshot_json']);allowed={(r['source_type'],r['source_id'],r['source_version']) for r in snapshot['retrieval_scope']}
            if not body['sources']:fail('请选择本轮资料，空集合不会检索全库')
            for source in body['sources']:
                if source['source_type']!='personal_note' and tuple(source[k] for k in ('source_type','source_id','source_version')) not in allowed:fail('课程来源不在本会话发布版本允许范围内','source_not_in_release',409)
            state=self._state(student,session);focus=state['next_task'];context=dict(session_id=key,release_id=release['id'],release_version=release['release_version'],
                learning_revision=state['guidance']['learning_revision'],assessment_revision=state['guidance']['assessment_revision'],
                goals=state['guidance']['goal_names'],focus_knowledge_id=focus['knowledge_id'],next_action=focus['action'],next_reason=focus['reason'],
                objective_summary=[dict(name=i['name'],attempts=i['objective']['attempts'],probability=i['objective']['probability'],last_correct=i['objective']['last_correct']) for i in state['guidance']['items'] if i['in_goal_path']])
            # Only reserve here; the model/network must not hold a DB transaction.
            self.db.execute('INSERT INTO teaching_explanations VALUES (?,?,?,?,?,?,?,?)',(body['request_id'],student,key,checksum,encode(body),encode(context),'running',now()))
        workbench=self.workbench_factory(self.learning);workbench.lesson_context=context
        def guard():
            from eduagent.services.knowledge import SourceChanged
            current=self.releases.row(student,context['release_id'])
            if not self.releases.validity(current)['usable'] or GuidanceService(self.learning)._snapshot(student)['assessment_revision']!=context['assessment_revision']:
                raise SourceChanged('课程或自评状态已变化，本轮不能继续模型调用')
        workbench.lesson_guard=guard
        try:result=workbench.ask(student,body)
        except Exception:
            with self.repo.transaction():self.db.execute("UPDATE teaching_explanations SET status='uncertain' WHERE request_id=?",(body['request_id'],))
            raise
        with self.repo.transaction():
            self.db.execute("UPDATE teaching_explanations SET status=? WHERE request_id=?",('uncertain' if result['status']=='uncertain' else 'complete',body['request_id']))
            if self.learning._student(student)['revision']==context['learning_revision']:
                self.db.execute("UPDATE teaching_sessions SET stage='explanation',updated_at=? WHERE id=?",(now(),key))
        return self.explanation_view(student,result,context)

    def explanation_view(self,student,result,context):
        state=GuidanceService(self.learning).snapshot(student)
        release=self.releases.row(student,context['release_id'])
        stale=(state['learning_revision']!=context['learning_revision'] or state['assessment_revision']!=context['assessment_revision'] or not self.releases.validity(release)['usable'])
        return dict(result,lesson_context=context,lesson_stale=stale)

    def explanation_contexts(self,student):
        with self.repo.transaction():
            snapshot=GuidanceService(self.learning)._snapshot(student);items=[]
            for row in self.db.execute('SELECT * FROM teaching_explanations WHERE student_id=? ORDER BY created_at DESC,request_id LIMIT 100',(student,)):
                context=json.loads(row['context_json']);release=self.releases.row(student,context['release_id'])
                stale=(context['learning_revision']!=snapshot['learning_revision'] or context['assessment_revision']!=snapshot['assessment_revision'] or not self.releases.validity(release)['usable'])
                items.append(dict(request_id=row['request_id'],context=context,lesson_stale=stale,status=row['status']))
            return dict(items=items)
