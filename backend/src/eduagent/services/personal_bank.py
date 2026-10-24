"""Reviewable originals and ordinary practice. Never call LearningService.next/submit."""
from copy import deepcopy
from hashlib import sha256
import json,re
from uuid import uuid4
from eduagent.domain.personal_bank import fail,question,practice_ready,grading_mode
from eduagent.documents.models import uuid_text
from eduagent.documents.question_extraction import extract,RULE_VERSION
from eduagent.services.resources import ResourcesService,COURSE,TYPES,resource_id
from eduagent.services.learning import now
from eduagent.storage.sqlite import encode


class PersonalBankService:
    def __init__(self,learning,materials):
        self.learning,self.repo=learning,learning.repository;self.db=self.repo.connection
        self.resources=ResourcesService(learning,materials)

    def _write(self,student,body,operation,callback):
        uuid_text(body['request_id']); checksum=sha256(encode([operation,body]).encode()).hexdigest()
        with self.repo.transaction():
            self.learning._student(student)
            old=self.db.execute('SELECT * FROM personal_bank_operations WHERE student_id=? AND course_id=? AND request_id=?',(student,COURSE,body['request_id'])).fetchone()
            if old:
                if old['request_hash']!=checksum:fail('请求编号已用于不同内容','request_id_conflict',409)
                return dict(json.loads(old['result_json']),replayed=True)
            result=callback()
            self.db.execute('INSERT INTO personal_bank_operations VALUES (?,?,?,?,?,?)',(student,COURSE,body['request_id'],checksum,encode(result),now()))
            return dict(result,replayed=False)

    def receipt(self,student,key):
        self.learning._student(student);uuid_text(key)
        row=self.db.execute('SELECT result_json FROM personal_bank_operations WHERE student_id=? AND course_id=? AND request_id=?',(student,COURSE,key)).fetchone()
        if not row:fail('当前学习标识下没有该请求','bank_request_not_found',404)
        return json.loads(row[0])

    def catalogue(self,student):
        with self.repo.transaction():return dict(items=self.resources.items(student),knowledge=self.resources.concepts(student))

    def resource(self,student,key):
        with self.repo.transaction():
            item=self.resources.row(student,key)
            if item['status']!='active':fail('原资源已删除','source_changed',409)
            units,run=self.resources.units(student,item)
            return dict(resource=item,units=units,run_id=run)

    def tag_resource(self,student,key,body):
        def apply():
            item=self.resources.row(student,key)
            if item['revision']!=body['expected_revision']:fail('资源元数据版本冲突','revision_conflict',409)
            if item['status']!='active':fail('资源已删除','source_changed',409)
            self.resources.validate_links(student,body['links'])
            if body['resource_type'] not in TYPES:fail('资源类型无效')
            self.resources.register(student,item)
            self.db.execute('UPDATE course_resources SET resource_type=?,links_json=?,revision=?,updated_at=? WHERE id=? AND student_id=?',
                (body['resource_type'],encode(body['links']),item['revision']+1,now(),key,student))
            return dict(resource_id=key,revision=item['revision']+1)
        return self._write(student,body,'tag:'+key,apply)

    def _insert_question(self,student,payload,source=None,batch=None,origin='unknown',status='draft',review=None):
        count=self.db.execute('SELECT count(*) FROM personal_questions WHERE student_id=?',(student,)).fetchone()[0]
        if count>=1000:fail('每个学习标识最多保留1000题（含归档）',status=413)
        key=str(uuid4());stamp=now();source=source or {}
        self.db.execute('INSERT INTO personal_questions VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
            (key,student,COURSE,batch,source.get('resource_id'),source.get('source_version'),encode(source),encode(payload),1,status,stamp,stamp))
        review=dict(review or {},answer_origin=origin,original_answer_origin=origin)
        self.db.execute('INSERT INTO personal_question_revisions VALUES (?,?,?,?,?,?,?,?)',(key,1,student,COURSE,encode(payload),status,encode(review),stamp))
        return key

    def extract(self,student,body):
        if not body.get('auto_import'):
            body={k:v for k,v in body.items() if k!='auto_import'}
        def apply():
            key=body.get('resource_id')
            if key:
                item=self.resources.row(student,key)
                if item['source_version']!=body['source_version']:fail('资源版本已变化，请重新选择','source_changed',409)
                units,run=self.resources.units(student,item,body.get('run_id'),body.get('ordinals'))
                if len(units)>30:fail('每轮最多提取30个解析单位，请在选页中缩小范围',status=413)
                self.resources.register(student,item)
            else:
                raw=body.get('text','')
                if not raw.strip():fail('请选择资源或粘贴原题')
                source_id=str(uuid4());key=resource_id(student,'text',source_id);stamp=now()
                self.db.execute('INSERT INTO course_resources VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                    (key,student,COURSE,'text',source_id,'exercise_material',body.get('title') or '粘贴习题',1,'[]',raw,stamp,stamp))
                item=self.resources.row(student,key);units,run=self.resources.units(student,item)
            items,warnings=extract(units)
            if not items:
                # A scanned/image original is still reviewable. No OCR or answer is invented.
                items=[dict(payload=question(dict(stem='[原图内容待转录，请对照左侧原件手工填写]',question_type='other')),
                    evidence=[dict(unit_id=u.get('id'),location=u.get('location',{}),raw_md=u['text'],origin=u.get('origin','local_extraction'),warnings=u.get('warnings',[])) for u in units],
                    warnings=['no_text_manual_transcription_required'],answer_origin='unknown')]
            source=dict(resource_id=key,title=item['title'],original_source_type=item['original_source_type'],original_source_id=item['original_source_id'],
                source_version=item['source_version'],content_hash=item['content_hash'],run_id=run,origin_mode='local')
            if run:
                source['origin_mode']=self.db.execute('SELECT mode FROM document_parse_runs WHERE id=?',(run,)).fetchone()[0]
            batch=str(uuid4());stamp=now()
            self.db.execute('INSERT INTO question_extractions VALUES (?,?,?,?,?,?,?,?,?)',(batch,student,COURSE,key,item['source_version'],encode(source),encode(warnings),RULE_VERSION,stamp))
            ids=[]; knowledge=self.resources.concepts(student);intake=dict(ready=0,needs_attention=0,duplicate=0)
            for entry in items:
                evidence=dict(source,evidence=entry['evidence'],warnings=entry['warnings'],original_answer_text=entry.get('original_answer_text'))
                candidates=[dict(architecture_id=g['architecture_id'],concept_id=c['id'],name=c['name'],review_status='candidate',method='literal_name_v1')
                    for g in knowledge for c in g['concepts'] if len(c['name'])>=2 and c['name'] in entry['payload']['stem']][:12]
                evidence['candidate_concepts']=candidates
                if body.get('auto_import'):
                    from eduagent.services.question_intake import auto_entry
                    qid,state=auto_entry(self,student,entry['payload'],evidence,batch,entry['answer_origin'],entry['warnings']);intake[state]+=1;ids.append(qid)
                else:ids.append(self._insert_question(student,entry['payload'],evidence,batch,entry['answer_origin']))
            return dict(extraction_id=batch,resource_id=key,question_ids=list(dict.fromkeys(ids)),warnings=warnings,intake=intake)
        return self._write(student,body,'extract',apply)

    def row(self,student,key):
        self.learning._student(student);uuid_text(key)
        r=self.db.execute('SELECT * FROM personal_questions WHERE id=? AND student_id=? AND course_id=?',(key,student,COURSE)).fetchone()
        if not r:fail('当前学习标识下没有该题目','personal_question_not_found',404)
        return dict(r)

    def view(self,student,row):
        value=json.loads(row['payload_json']);source=json.loads(row['source_json'])
        review=self.db.execute('SELECT review_json FROM personal_question_revisions WHERE question_id=? AND revision=? AND student_id=?',(row['id'],row['revision'],student)).fetchone()
        review=json.loads(review[0]); provenance='human_confirmed' if review.get('answer_confirmed') else review.get('answer_origin','unknown')
        return dict(id=row['id'],course_id=COURSE,revision=row['revision'],status=row['status'],payload=value,source=source,
            source_status=self.resources.source_status(student,source),answer_provenance=provenance,review=review,
            extraction_id=row['extraction_id'],created_at=row['created_at'],updated_at=row['updated_at'])

    def get(self,student,key):
        with self.repo.transaction():return self.view(student,self.row(student,key))

    def listing(self,student,**filters):
        with self.repo.transaction():
            self.learning._student(student)
            rows=[self.view(student,dict(r)) for r in self.db.execute('SELECT * FROM personal_questions WHERE student_id=? AND course_id=? ORDER BY updated_at DESC,id',(student,COURSE))]
            for name,value in filters.items():
                if not value:continue
                if name=='q': rows=[r for r in rows if value.casefold() in r['payload']['stem'].casefold()]
                if name=='status':rows=[r for r in rows if r['status']==value]
                if name=='question_type':rows=[r for r in rows if r['payload']['question_type']==value]
                if name=='resource_id':rows=[r for r in rows if r['source'].get('resource_id')==value]
                if name=='concept_id':rows=[r for r in rows if any(c['concept_id']==value for c in r['payload']['concepts'])]
                if name=='chapter_id':
                    ids={c['id'] for g in self.resources.concepts(student) for c in g['concepts'] if value in c['chapter_ids']}
                    rows=[r for r in rows if any(c['concept_id'] in ids for c in r['payload']['concepts'])]
            fingerprints={}
            for row in rows:
                normalized=re.sub(r'\s+','',row['payload']['stem']).casefold();fingerprints.setdefault(normalized,[]).append(row['id'])
            for row in rows:row['duplicate_ids']=[k for k in fingerprints[re.sub(r'\s+','',row['payload']['stem']).casefold()] if k!=row['id']]
            return dict(items=rows,total=len(rows))

    def _save_revision(self,student,row,payload,status,review):
        revision=row['revision']+1;stamp=now()
        review=dict(review,source_snapshot=review.get('source_snapshot',json.loads(row['source_json'])))
        self.db.execute('UPDATE personal_questions SET payload_json=?,revision=?,status=?,updated_at=? WHERE id=? AND student_id=?',
            (encode(payload),revision,status,stamp,row['id'],student))
        self.db.execute('INSERT INTO personal_question_revisions VALUES (?,?,?,?,?,?,?,?)',
            (row['id'],revision,student,COURSE,encode(payload),status,encode(review),stamp))
        return revision

    def save(self,student,body,key=None):
        def apply():
            payload=question(body['payload']);self.resources.validate_concepts(student,payload['concepts'])
            status=body.get('status','draft'); confirmed=body.get('reviewed') is True
            if status not in ('draft','practice'):fail('请使用归档操作；不支持正式诊断状态')
            if status=='practice':
                if not confirmed:fail('进入普通练习前必须人工确认题目')
                practice_ready(payload)
            if body.get('confirm_answer') and (not confirmed or not (payload['answer'] is not None or payload.get('answer_text') or payload.get('answer_keys'))):fail('确认答案前请填入答案并明确审阅')
            review=dict(reviewed=confirmed,answer_confirmed=bool(body.get('confirm_answer')),reviewed_at=now() if confirmed else None,
                reviewer_scope=student if confirmed else None,answer_origin='unknown')
            if key:
                row=self.row(student,key)
                if row['revision']!=body['expected_revision']:fail('题目已有新版本，保留草稿后刷新','revision_conflict',409)
                old=json.loads(self.db.execute('SELECT review_json FROM personal_question_revisions WHERE question_id=? AND revision=?',(key,row['revision'])).fetchone()[0])
                review['original_answer_origin']=old.get('original_answer_origin',old.get('answer_origin','unknown'))
                previous_payload=json.loads(row['payload_json'])
                review['answer_origin']=old.get('answer_origin','unknown') if all(payload.get(k)==previous_payload.get(k) for k in ('answer','answer_text','answer_keys','explanation')) else 'unknown'
                if status=='practice' and self.resources.source_status(student,json.loads(row['source_json'])) not in ('current','manual') and not body.get('acknowledge_source_change'):
                    fail('原来源已变化，请对照快照并明确重新核对','source_changed',409)
                review['source_change_acknowledged']=bool(body.get('acknowledge_source_change'))
                rev=self._save_revision(student,row,payload,status,review)
            else:
                if body.get('expected_revision') is not None:fail('新题不接受旧版本')
                key2=self._insert_question(student,payload,status=status,review=review)
                return dict(question_id=key2,revision=1)
            return dict(question_id=key,revision=rev)
        return self._write(student,body,'save:'+str(key),apply)

    def archive(self,student,key,body):
        def apply():
            row=self.row(student,key)
            if row['revision']!=body['expected_revision']:fail('题目版本冲突','revision_conflict',409)
            review=json.loads(self.db.execute('SELECT review_json FROM personal_question_revisions WHERE question_id=? AND revision=?',(key,row['revision'])).fetchone()[0])
            return dict(question_id=key,revision=self._save_revision(student,row,json.loads(row['payload_json']),'archived',dict(review,archived_at=now())))
        return self._write(student,body,'archive:'+key,apply)

    def accept_proposal(self,student,key,body):
        def apply():
            target=self.row(student,key);proposal=self.row(student,body['proposal_id'])
            source=json.loads(proposal['source_json']);ref=source.get('proposal_for') or {}
            if target['status']=='archived' or proposal['status']=='archived':fail('已归档题目不能接受修正')
            if ref.get('question_id')!=key:fail('修正稿不属于这道原题')
            if target['revision']!=body['expected_revision'] or target['revision']!=ref.get('revision') or proposal['revision']!=body['proposal_revision']:
                fail('原题或修正稿已有新版本，请重新对照','revision_conflict',409)
            if self.resources.source_status(student,source)!='current':fail('修正稿来源已失效','source_changed',409)
            payload=json.loads(proposal['payload_json'])
            previous_review=json.loads(self.db.execute('SELECT review_json FROM personal_question_revisions WHERE question_id=? AND revision=?',(key,target['revision'])).fetchone()[0])
            replacement=dict(source,accepted_proposal_id=proposal['id'])
            self.db.execute('UPDATE personal_questions SET source_json=? WHERE id=? AND student_id=?',(encode(dict(source,accepted_proposal_id=proposal['id'])),key,student))
            revision=self._save_revision(student,target,payload,'draft',dict(answer_origin='model_inferred' if payload.get('answer') or payload.get('answer_text') or payload.get('answer_keys') else 'unknown',
                original_answer_origin=previous_review.get('original_answer_origin',previous_review.get('answer_origin','unknown')),
                source_snapshot=replacement,previous_source_snapshot=json.loads(target['source_json']),previous_revision=target['revision'],
                accepted_proposal_id=proposal['id'],answer_confirmed=False,reviewed=False))
            return dict(question_id=key,revision=revision)
        return self._write(student,body,'accept-proposal:'+key,apply)

    def restructure(self,student,body):
        def apply():
            refs=body['originals']; parts=body['questions']
            if len(refs)==1 and len(parts)<2 or len(refs)>1 and len(parts)!=1:fail('拆分需要一题变多题；合并需要多题变一题')
            if len({r['question_id'] for r in refs})!=len(refs):fail('不能重复合并同一题')
            originals=[self.row(student,r['question_id']) for r in refs]
            for row,ref in zip(originals,refs):
                if row['revision']!=ref['expected_revision']:fail('原题版本变化，整次操作取消','revision_conflict',409)
                if row['status']=='archived':fail('不能合并或拆分已归档题')
            ids=[]
            for part in parts:
                payload=question(part);self.resources.validate_concepts(student,payload['concepts'])
                source=json.loads(originals[0]['source_json'])
                source['restructured_from']=[dict(question_id=r['id'],revision=r['revision'],resource_id=r['resource_id'],source_version=r['source_version']) for r in originals]
                related={};evidence=[]
                for r in originals:
                    s=json.loads(r['source_json'])
                    for ref in [s,*s.get('related_sources',[])]:
                        if ref.get('resource_id'):
                            slim={k:ref[k] for k in ('resource_id','source_version','title','original_source_type','original_source_id','run_id','origin_mode') if k in ref}
                            related[(slim['resource_id'],slim['source_version'])]=slim
                    evidence.extend(dict(e,resource_id=s.get('resource_id'),source_version=s.get('source_version'),original_source_id=s.get('original_source_id')) for e in s.get('evidence',[]))
                if len(related)>12 or sum(len(e['raw_md']) for e in evidence)>120000:fail('合并来源或快照超过限额，请减少合并数量',status=413)
                source['related_sources']=list(related.values());source['evidence']=evidence
                ids.append(self._insert_question(student,payload,source))
            for row in originals:self._save_revision(student,row,json.loads(row['payload_json']),'archived',dict(restructured_into=ids,answer_origin='unknown'))
            return dict(question_ids=ids)
        return self._write(student,body,'restructure',apply)

    def revisions(self,student,key):
        with self.repo.transaction():
            self.row(student,key)
            return dict(items=[dict(revision=r['revision'],payload=json.loads(r['payload_json']),status=r['status'],review=json.loads(r['review_json']),created_at=r['created_at'])
                for r in self.db.execute('SELECT * FROM personal_question_revisions WHERE question_id=? AND student_id=? ORDER BY revision DESC',(key,student))])

    def start(self,student,body):
        def apply():
            key=body.get('question_id')
            if not key:
                rows=self.db.execute("SELECT * FROM personal_questions WHERE student_id=? AND course_id=? AND status='practice' ORDER BY updated_at,id",(student,COURSE)).fetchall()
                candidates=[dict(r) for r in rows if (not body.get('concept_id') or any(c['concept_id']==body['concept_id'] for c in json.loads(r['payload_json']).get('concepts',[]))) and (body.get('acknowledge_source_change') or self.resources.source_status(student,json.loads(r['source_json'])) in ('current','manual'))]
                if not candidates:fail('所选范围暂时没有可练习的当前题目，请导入习题或处理待整理项','no_personal_practice',409)
                graphs=self.resources.concepts(student);states=self.learning.status(student)
                def priority(r):
                    stats=self.db.execute('SELECT count(*),sum(a.correct=0) FROM personal_practice_sessions s LEFT JOIN personal_practice_attempts a ON a.session_id=s.id WHERE s.question_id=? AND s.student_id=?',(r['id'],student)).fetchone()
                    # Existing confirmed concept links may read objective evidence;
                    # new unclassified concepts never acquire invented BKT values.
                    refs=json.loads(r['payload_json']).get('concepts',[]); related=set()
                    for g in graphs:
                        for c in g['concepts']:
                            if any(v['architecture_id']==g['architecture_id'] and v['concept_id']==c['id'] for v in refs): related.update(c.get('formal_knowledge_ids',[]))
                    weak=min((states[k].probability for k in related if k in states and states[k].attempts),default=1.)
                    return (weak,-(stats[1] or 0),stats[0],r['id'])
                row=min(candidates,key=priority)
            else:row=self.row(student,key)
            if row['status']!='practice':fail('该题尚未进入普通练习','question_not_reviewed',409)
            value=self.view(student,row)
            if value['source_status'] not in ('current','manual') and not body.get('acknowledge_source_change'):
                fail('来源变化，需明确选择使用已审核题目快照','source_changed',409)
            session=str(uuid4())
            snapshot=dict(value['payload'],answer_confirmed=value['review'].get('answer_confirmed',False),answer_provenance=value['answer_provenance'],automation=value['review'].get('automation'))
            self.db.execute('INSERT INTO personal_practice_sessions VALUES (?,?,?,?,?,?,?,?,?)',
                (session,student,COURSE,row['id'],row['revision'],encode(snapshot),row['source_json'],'open',now()))
            return dict(session_id=session)
        return self._write(student,body,'practice-start',apply)

    def session_row(self,student,key):
        self.learning._student(student);uuid_text(key)
        row=self.db.execute('SELECT * FROM personal_practice_sessions WHERE id=? AND student_id=? AND course_id=?',(key,student,COURSE)).fetchone()
        if not row:fail('当前学习标识下没有该普通练习','personal_session_not_found',404)
        return dict(row)

    def session_view(self,student,row):
        value=json.loads(row['snapshot_json']);source=json.loads(row['source_json'])
        result=self.db.execute('SELECT result_json FROM personal_practice_attempts WHERE session_id=? AND student_id=?',(row['id'],student)).fetchone()
        if not result:
            value.pop('answer',None);value.pop('explanation',None);value.pop('answer_text',None);value.pop('answer_keys',None)
            for child in value.get('subquestions',[]):
                for field in ('answer','answer_text','answer_keys','explanation'):child.pop(field,None)
        return dict(id=row['id'],question_id=row['question_id'],question_revision=row['question_revision'],question=value,status=row['status'],
                    grading_mode=grading_mode(value),draft=self.practice_draft(student,row['id']),source=source,source_status=self.resources.source_status(student,source),result=json.loads(result[0]) if result else None,created_at=row['created_at'])

    def session(self,student,key):
        with self.repo.transaction():return self.session_view(student,self.session_row(student,key))

    def sessions(self,student,wrong_only=False):
        with self.repo.transaction():
            self.learning._student(student)
            rows=self.db.execute('SELECT s.* FROM personal_practice_sessions s LEFT JOIN personal_practice_attempts a ON a.session_id=s.id WHERE s.student_id=? AND s.course_id=? AND (?=0 OR a.correct=0) ORDER BY s.created_at DESC,s.id LIMIT 100',(student,COURSE,int(wrong_only))).fetchall()
            return dict(items=[self.session_view(student,dict(r)) for r in rows])

    def submit(self,student,key,body):
        def apply():
            row=self.session_row(student,key)
            if row['status']!='open':fail('本轮已作答，请查看保存结果或开始新的重复练习','personal_attempt_exists',409)
            value=json.loads(row['snapshot_json']);answer=body['selected_answer']
            if grading_mode(value)=='objective' and answer not in {o['key'] for o in value['options']}:fail('请选择本轮有效选项')
            if not isinstance(answer,str) or not answer.strip() or len(answer)>16000:fail('作答不能为空或超过16000字符')
            gradable=grading_mode(value)=='objective' and value.get('answer_confirmed') and value.get('answer') is not None
            correct=answer==value['answer'] if gradable else None
            result=dict(selected_answer=answer,correct=correct,score=int(correct) if correct is not None else None,
                correct_answer=value.get('answer') if gradable else None,reference_answer=value.get('answer_text') or value.get('answer_keys') or value.get('answer'),needs_review=bool(body.get('needs_review',False)),
                grading_basis='human_confirmed_snapshot' if gradable else 'ungraded_text_response' if grading_mode(value)!='objective' else 'ungraded_no_confirmed_answer',
                explanation=value.get('explanation',''),question_revision=row['question_revision'],bkt_updated=False,created_at=now())
            if value.get('automation') and not gradable:
                result.update(reference_match=answer==value['answer'] if grading_mode(value)=='objective' and value.get('answer') else None,
                              reference_origin=value.get('answer_provenance','unknown'),content_verified=False)
            self.db.execute('INSERT INTO personal_practice_attempts VALUES (?,?,?,?,?,?,?)',(key,student,COURSE,answer,None if correct is None else int(correct),encode(result),now()))
            self.db.execute("UPDATE personal_practice_sessions SET status='answered' WHERE id=? AND student_id=?",(key,student))
            return dict(session_id=key,result=result)
        return self._write(student,body,'practice-submit:'+key,apply)

    def practice_draft(self,student,key):
        row=self.db.execute('SELECT * FROM personal_practice_drafts WHERE session_id=? AND student_id=?',(key,student)).fetchone()
        return dict(revision=row['revision'],response_text=row['response_text'],needs_review=bool(row['needs_review'])) if row else dict(revision=0,response_text='',needs_review=False)

    def save_practice_draft(self,student,key,body):
        def apply():
            row=self.session_row(student,key)
            if row['status']!='open':fail('已提交作答不能修改草稿','personal_attempt_exists',409)
            old=self.practice_draft(student,key)
            if old['revision']!=body['expected_revision']:fail('作答草稿版本已变化','revision_conflict',409)
            revision=old['revision']+1
            self.db.execute('INSERT INTO personal_practice_drafts VALUES (?,?,?,?,?,?,?) ON CONFLICT(session_id) DO UPDATE SET revision=excluded.revision,response_text=excluded.response_text,needs_review=excluded.needs_review,updated_at=excluded.updated_at',
                (key,student,COURSE,revision,body['response_text'],int(body['needs_review']),now()))
            return dict(session_id=key,revision=revision)
        return self._write(student,body,'practice-draft:'+key,apply)
