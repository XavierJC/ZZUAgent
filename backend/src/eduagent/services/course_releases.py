"""Local content maintenance and immutable manifests; no formal bank mutation."""
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
from uuid import uuid4,uuid5,NAMESPACE_URL
from eduagent.domain.personal_bank import fail
from eduagent.documents.models import uuid_text
from eduagent.services.resources import ResourcesService,COURSE
from eduagent.services.learning import now
from eduagent.storage.sqlite import encode

def digest(value):return sha256(encode(value).encode()).hexdigest()

class CourseReleases:
    def __init__(self,learning,data_dir):
        self.learning,self.repo=learning,learning.repository;self.db=self.repo.connection
        self.data_dir=Path(data_dir);self.resources=ResourcesService(learning,self.data_dir/'materials')
        from eduagent.services.teaching_sources import TeachingSources
        self.teachers=TeachingSources(self.repo)

    def operation(self,student,body,name,callback):
        uuid_text(body['request_id']);checksum=digest([name,body])
        with self.repo.transaction():
            self.learning._student(student)
            old=self.db.execute('SELECT * FROM course_workflow_operations WHERE student_id=? AND request_id=?',(student,body['request_id'])).fetchone()
            if old:
                if old['request_hash']!=checksum:fail('请求编号已用于不同内容','request_id_conflict',409)
                return dict(json.loads(old['result_json']),replayed=True)
            result=callback()
            self.db.execute('INSERT INTO course_workflow_operations VALUES (?,?,?,?,?)',(student,body['request_id'],checksum,encode(result),now()))
            return dict(result,replayed=False)

    def configuration(self):
        return dict(catalog_fingerprint=self.learning.catalog.fingerprint,bank_version=self.learning.catalog.bank_version,
            knowledge_version=self.learning.catalog.knowledge_version,parameters=asdict(self.learning.parameters),policy=asdict(self.learning.policy),scoring='exact-option-key-v1')

    def course_sources(self):
        root=(self.data_dir/'materials').resolve();manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'));out=[]
        for d in manifest['documents']:
            path=(root/d['file']).resolve()
            if not path.is_relative_to(root):fail('课程来源路径无效')
            checksum=sha256(path.read_text(encoding='utf-8').encode()).hexdigest()
            version=sha256(json.dumps({'document':d,'hash':checksum},sort_keys=True,ensure_ascii=False).encode()).hexdigest()
            out.append(dict(source_type='course_material',source_id=d['id'],source_version=version,content_hash=checksum,title=d['title'],rag_available=True))
        return out

    def _snapshot(self,student,payload):
        sources=[]
        available={r['source_id']:r for r in self.course_sources()}
        for ref in payload['sources']:
            if ref['source_type']=='course_material':
                source=available.get(ref['source_id'])
                if not source or source['source_version']!=ref['source_version']:fail('课程资料版本已变化','source_changed',409)
                sources.append(source)
            else:
                item=self.resources.row(student,ref['source_id'])
                teacher=None
                try:teacher=self.teachers.validate(student,ref)
                except ValueError:pass
                if teacher and any(r['architecture_id']!=payload.get('architecture_id') or r['architecture_version']!=payload.get('architecture_version') for r in teacher['links']):
                    fail('课件片段关联的已确认知识体系版本须与课程发布选择一致','source_changed',409)
                if item['original_source_type']!='document' or item['status']!='active' or (item['source_version']!=ref['source_version'] and teacher is None) or item['parse_status'] not in ('ready','partial','empty'):
                    fail('只能引用当前学习标识已保存的有效课件版本','source_changed',409)
                sources.append(dict(source_type='teaching_material',source_id=item['resource_id'],document_id=item['original_source_id'],source_version=ref['source_version'],document_version=item['source_version'],content_hash=item['content_hash'],parse_id=item['parse_id'],title=item['title'],rag_available=teacher is not None,segment_versions=[dict(id=r['id'],revision=r['revision'],architecture_id=r['architecture_id'],architecture_version=r['architecture_version']) for r in teacher['links']] if teacher else []))
        graph=None
        if payload.get('architecture_id'):
            row=self.db.execute('SELECT v.* FROM knowledge_versions v JOIN knowledge_architectures a ON a.id=v.architecture_id WHERE a.id=? AND a.student_id=? AND a.course_id=? AND v.version=?',(payload['architecture_id'],student,COURSE,payload['architecture_version'])).fetchone()
            if not row:fail('知识体系必须引用本标识已确认的发布版本','architecture_not_found',404)
            graph=dict(architecture_id=payload['architecture_id'],version=row['version'],content_hash=digest(json.loads(row['graph_json'])),graph=json.loads(row['graph_json']))
        return dict(course_id=COURSE,title=payload['title'],configuration=self.configuration(),
            knowledge=[asdict(k) for k in self.learning.catalog.knowledge.values()],questions=[asdict(q) for q in self.learning.catalog.questions.values()],
            sources=sources,retrieval_scope=[{k:s[k] for k in ('source_type','source_id','source_version')} for s in sources if s['rag_available']],
            architecture=graph,goals=list(self.learning.catalog.knowledge),reviewer=payload.get('reviewer',''),reviewed_question_ids=payload['reviewed_question_ids'],
            bkt_calibration='not_statistically_calibrated',formal_admission='existing_runtime_bank_only',teacher_rag='reviewed_segments_only' if any(s['source_type']=='teaching_material' and s['rag_available'] for s in sources) else 'not_implemented')

    def ensure_demo(self):
        with self.repo.transaction():
            row=self.db.execute("SELECT id FROM course_releases WHERE scope_key='*' AND course_id=?",(COURSE,)).fetchone()
            if row:return row[0]
            payload=dict(title='机器学习 · 工程演示课程',sources=[{k:s[k] for k in ('source_type','source_id','source_version')} for s in self.course_sources()],reviewer='',reviewed_question_ids=[])
            snapshot=self._snapshot(None,payload);snapshot['review_warning']='原5知识点/10演示题未完成人工内容审核，不能当作已审核正式课程。'
            key=str(uuid5(NAMESPACE_URL,'eduagent-initial-demo-release-v1'))
            self.db.execute('INSERT INTO course_releases VALUES (?,?,?,?,?,?,?,?,?,?,?)',(key,None,'*',COURSE,1,'demo',None,None,encode(snapshot),digest(snapshot),now()))
            return key

    def row(self,student,key):
        self.learning._student(student);uuid_text(key)
        row=self.db.execute('SELECT * FROM course_releases WHERE id=? AND course_id=? AND (owner_id=? OR scope_key=?)',(key,COURSE,student,'*')).fetchone()
        if not row:fail('当前学习标识下没有该课程发布','release_not_found',404)
        return dict(row)

    def validity(self,row):
        snapshot=json.loads(row['snapshot_json']);issues=[];states=[]
        if digest(snapshot)!=row['content_hash']:issues.append('release_snapshot_corrupt')
        if snapshot['configuration']!=self.configuration():issues.append('runtime_configuration_changed')
        try:current={s['source_id']:s for s in self.course_sources()}
        except (OSError,UnicodeError,ValueError):current={};issues.append('source_catalog_unavailable')
        for s in snapshot['sources']:
            status='current'
            if s['source_type']=='course_material':
                item=current.get(s['source_id']);status='missing' if not item else 'current' if item['source_version']==s['source_version'] else 'modified'
            else:
                try:
                    if s['rag_available']:
                        item=self.teachers.validate(row['owner_id'],s);status='current'
                    else:
                        item=self.resources.row(row['owner_id'],s['source_id']);status='deleted' if item['status']!='active' else 'modified' if item['source_version']!=s['source_version'] else 'current'
                except ValueError:status='missing'
            states.append(dict(source_type=s['source_type'],source_id=s['source_id'],title=s['title'],source_version=s['source_version'],current_status=status,rag_available=s['rag_available']))
            if status!='current':issues.append('source_'+status)
        if snapshot.get('architecture'):
            graph=snapshot['architecture'];r=self.db.execute('SELECT graph_json FROM knowledge_versions WHERE architecture_id=? AND version=?',(graph['architecture_id'],graph['version'])).fetchone()
            if not r or digest(json.loads(r[0]))!=graph['content_hash']:issues.append('architecture_unavailable')
        return dict(usable=not issues,issues=list(dict.fromkeys(issues)),source_statuses=states)

    def view(self,row,*,builder=False):
        snapshot=json.loads(row['snapshot_json']);validity=self.validity(row)
        out=dict(id=row['id'],course_id=COURSE,title=snapshot['title'],release_version=row['release_version'],kind=row['kind'],published_at=row['published_at'],content_hash=row['content_hash'],
            knowledge=snapshot['knowledge'],question_versions=[{k:q[k] for k in ('id','version','knowledge_id','difficulty')} for q in snapshot['questions']],
            sources=snapshot['sources'],retrieval_scope=snapshot['retrieval_scope'],architecture=snapshot['architecture'],
            review_warning=snapshot.get('review_warning','内容负责人已确认本版本答案；BKT参数未经过统计标定。'),configuration=snapshot['configuration'],**validity)
        if builder:out['review_questions']=snapshot['questions']
        return out

    def list(self,student):
        with self.repo.transaction():
            self.learning._student(student)
            return dict(items=[self.view(dict(r)) for r in self.db.execute('SELECT * FROM course_releases WHERE course_id=? AND (owner_id=? OR scope_key=?) ORDER BY published_at DESC,id',(COURSE,student,'*'))])

    def draft_row(self,student,key):
        uuid_text(key);self.learning._student(student)
        row=self.db.execute('SELECT * FROM course_release_drafts WHERE id=? AND student_id=? AND course_id=?',(key,student,COURSE)).fetchone()
        if not row:fail('当前学习标识下没有该课程草稿','release_draft_not_found',404)
        return dict(row)

    def payload(self,student,value):
        allowed={'title','architecture_id','architecture_version','sources','reviewer','reviewed_question_ids'}
        if not isinstance(value,dict) or set(value)-allowed:fail('课程草稿含未约定字段')
        from eduagent.domain.architecture import text
        refs=value.get('sources',[]);reviewed=value.get('reviewed_question_ids',[])
        if not isinstance(refs,list) or len(refs)>30 or not refs:fail('请明确选择1～30项课程来源')
        seen=set()
        for ref in refs:
            if not isinstance(ref,dict) or set(ref)!={'source_type','source_id','source_version'} or ref['source_type'] not in ('course_material','teaching_material'):fail('课程来源引用无效，不能自动发布个人笔记')
            if not all(isinstance(ref[k],str) and 0<len(ref[k])<=160 for k in ('source_id','source_version')):fail('来源ID/版本无效')
            pair=(ref['source_type'],ref['source_id'])
            if pair in seen:fail('课程来源重复')
            seen.add(pair)
        if not isinstance(reviewed,list) or any(not isinstance(q,str) for q in reviewed) or len(set(reviewed))!=len(reviewed) or any(q not in self.learning.catalog.questions for q in reviewed):fail('审核仅限原运行题库，不能启用候选题或个人题')
        architecture=value.get('architecture_id');version=value.get('architecture_version')
        if bool(architecture)!=bool(version):fail('必须同时指定知识体系及已确认版本')
        if architecture:uuid_text(architecture)
        if version is not None and (type(version)!=int or version<1):fail('知识体系版本无效')
        out=dict(title=text(value.get('title','机器学习'),'课程标题',120),sources=refs,architecture_id=architecture,architecture_version=version,
            reviewer=text(value.get('reviewer',''),'审核人说明',120,True),reviewed_question_ids=reviewed)
        self._snapshot(student,out)
        return out

    def save(self,student,body,key=None):
        def apply():
            payload=self.payload(student,body['payload']);stamp=now()
            if key:
                row=self.draft_row(student,key)
                if row['revision']!=body['expected_revision']:fail('草稿已有新版本','revision_conflict',409)
                revision=row['revision']+1
                self.db.execute('UPDATE course_release_drafts SET revision=?,payload_json=?,updated_at=? WHERE id=?',(revision,encode(payload),stamp,key))
                return dict(draft_id=key,revision=revision)
            if self.db.execute('SELECT count(*) FROM course_release_drafts WHERE student_id=?',(student,)).fetchone()[0]>=30:fail('本机标识最多保留30份课程草稿',status=413)
            qid=str(uuid4());self.db.execute('INSERT INTO course_release_drafts VALUES (?,?,?,?,?,?,?)',(qid,student,COURSE,1,encode(payload),stamp,stamp))
            return dict(draft_id=qid,revision=1)
        return self.operation(student,body,'course-draft:'+str(key),apply)

    def check(self,student,key):
        with self.repo.transaction():
            row=self.draft_row(student,key);payload=json.loads(row['payload_json']);snapshot=self._snapshot(student,payload);blocked=[]
            if not snapshot['architecture']:blocked.append('缺少已确认的课程知识体系版本')
            missing=set(self.learning.catalog.questions)-set(payload['reviewed_question_ids'])
            if missing:blocked.append('尚未逐题确认原10道演示题的题干、答案和解析')
            if not payload['reviewer'].strip():blocked.append('缺少本机内容审核人说明')
            counts={k:sum(q['knowledge_id']==k for q in snapshot['questions']) for k in self.learning.catalog.knowledge}
            if any(n==0 for n in counts.values()):blocked.append('正式知识点缺少诊断题')
            return dict(draft_id=key,revision=row['revision'],payload=payload,snapshot_hash=digest(snapshot),formal_allowed=not blocked,
                formal_blockers=blocked,demo_allowed=True,question_coverage=counts,question_count=len(snapshot['questions']),reviewed_count=len(payload['reviewed_question_ids']),
                review_questions=snapshot['questions'],teacher_rag='not_implemented',bkt_calibration='not_statistically_calibrated')

    def publish(self,student,key,body):
        def apply():
            row=self.draft_row(student,key)
            if row['revision']!=body['expected_revision']:fail('发布前草稿已变化','revision_conflict',409)
            if not body['confirmed']:fail('请明确确认发布当前内容版本')
            checked=self.check(student,key)
            if checked['snapshot_hash']!=body['snapshot_hash']:fail('审核后资料或配置已变化，请重新审核','source_changed',409)
            if body['kind']=='reviewed' and not checked['formal_allowed']:fail('；'.join(checked['formal_blockers']),'course_review_incomplete',409)
            snapshot=self._snapshot(student,checked['payload'])
            if body['kind']=='demo':snapshot['review_warning']='本机内容未满足正式发布审核，明确作为工程演示版本；不能宣称人工审核或参数已标定。'
            key2=str(uuid4());version=self.db.execute('SELECT coalesce(max(release_version),0)+1 FROM course_releases WHERE scope_key=? AND course_id=?',('student:'+student,COURSE)).fetchone()[0]
            previous=self.db.execute('SELECT id FROM course_releases WHERE draft_id=? AND draft_revision=?',(key,row['revision'])).fetchone()
            if previous:fail('该草稿版本已经发布，请查看原发布版本','draft_already_published',409)
            self.db.execute('INSERT INTO course_releases VALUES (?,?,?,?,?,?,?,?,?,?,?)',(key2,student,'student:'+student,COURSE,version,body['kind'],key,row['revision'],encode(snapshot),digest(snapshot),now()))
            return dict(release_id=key2,release_version=version,kind=body['kind'])
        return self.operation(student,body,'publish:'+key,apply)

    def builder(self,student):
        with self.repo.transaction():
            self.learning._student(student)
            documents=[r for r in self.resources.items(student) if r['original_source_type']=='document' and r['status']=='active']
            for d in documents:
                try:
                    s=self.teachers.source(student,d['resource_id']);d['rag_source_version']=s['source_version'] if s['index_status']=='ready' else None
                    d['rag_available']=s['index_status']=='ready'
                except ValueError:d['rag_source_version']=None
            candidates_path=self.data_dir/'candidates/questions-v2.json';candidates=json.loads(candidates_path.read_text(encoding='utf-8'))['questions'] if candidates_path.exists() else []
            shared=set(self.learning.catalog.questions)&{q['id'] for q in candidates}
            return dict(drafts=[dict(id=r['id'],revision=r['revision'],payload=json.loads(r['payload_json']),updated_at=r['updated_at']) for r in self.db.execute('SELECT * FROM course_release_drafts WHERE student_id=? ORDER BY updated_at DESC,id',(student,))],
                releases=self.list(student)['items'],course_sources=self.course_sources(),architectures=self.resources.concepts(student),
                documents=documents,
                formal_questions=[asdict(q) for q in self.learning.catalog.questions.values()],candidate_count=len(candidates),shared_formal_count=len(shared),additional_candidate_count=len(candidates)-len(shared))
