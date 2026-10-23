"""Small reviewed PDF page corpus. No model, grading, global cache or private-file enumeration."""
from hashlib import sha256
import json
from pathlib import Path
from uuid import uuid4

from eduagent.domain.personal_bank import fail
from eduagent.documents.models import uuid_text
from eduagent.services.learning import now
from eduagent.services.resources import resource_id
from eduagent.storage.sqlite import encode
from eduagent.retrieval.personal import search_personal

COURSE='machine_learning'
def digest(value):return sha256(encode(value).encode()).hexdigest()

class TeachingSources:
    def __init__(self,repository):
        self.repo,self.db=repository,repository.connection
        path=self.db.execute('PRAGMA database_list').fetchone()[2]
        self.directory=getattr(repository,'document_root',None) or (Path(path).with_suffix('.documents') if path else None)

    def student(self,student):
        if not self.repo.student(student):fail('学习标识不存在','student_not_found',404)

    def document(self,student,key):
        self.student(student)
        row=self.db.execute('SELECT d.*,v.content_hash,v.storage_key,r.status AS parse_status FROM course_documents d JOIN document_versions v ON v.id=d.current_version_id LEFT JOIN document_parse_runs r ON r.id=d.current_parse_id WHERE d.student_id=? AND d.course_id=? AND d.id=?',(student,COURSE,key)).fetchone()
        if not row or row['deleted_at']:fail('当前学习标识下没有有效资料','source_not_found',404)
        return dict(row)

    def concept(self,student,architecture,concept,version=None):
        row=self.db.execute('SELECT * FROM knowledge_architectures WHERE id=? AND student_id=? AND course_id=?',(architecture,student,COURSE)).fetchone()
        if not row:fail('当前标识下无该知识体系','concept_not_found',404)
        if version is None:
            g=self.db.execute('SELECT graph_json FROM knowledge_drafts WHERE architecture_id=?',(architecture,)).fetchone()
        else:
            g=self.db.execute('SELECT graph_json FROM knowledge_versions WHERE architecture_id=? AND version=? AND student_id=?',(architecture,version,student)).fetchone()
        if not g:fail('知识体系版本尚未确认','concept_not_confirmed',409)
        item=next((c for c in json.loads(g[0])['concepts'] if c['id']==concept),None)
        if not item or version is not None and item['review_status']!='confirmed':fail('知识概念不存在或尚未确认','concept_not_confirmed',409)
        return item

    def unit(self,student,doc,run,ordinal):
        row=self.db.execute('SELECT u.*,r.status AS run_status FROM document_units u JOIN document_parse_runs r ON r.id=u.run_id WHERE u.student_id=? AND u.document_id=? AND u.version_id=? AND u.run_id=? AND u.ordinal=?',(student,doc['id'],doc['current_version_id'],run,ordinal)).fetchone()
        if not row or row['run_status'] not in ('ready','partial'):fail('所选当前版本页面尚不可用','source_changed',409)
        return dict(row)

    def current(self,row):
        try:
            doc=self.document(row['student_id'],row['document_id'])
            if doc['current_version_id']!=row['version_id'] or doc['current_parse_id']!=row['parse_head_id']:return False
            if self.directory:
                root=Path(self.directory).resolve();path=(root/doc['storage_key']).resolve()
                if not path.is_relative_to(root) or not path.is_file() or sha256(path.read_bytes()).hexdigest()!=doc['content_hash']:return False
            u=self.unit(row['student_id'],doc,row['run_id'],self.db.execute('SELECT ordinal FROM document_units WHERE id=?',(row['unit_id'],)).fetchone()[0])
            if u['content_hash']!=row['unit_hash'] or u['content_md'][row['start_offset']:row['end_offset']]!=row['original_text']:return False
            self.concept(row['student_id'],row['architecture_id'],row['concept_id'],row['architecture_version'])
            return True
        except (ValueError,TypeError,IndexError,OSError):return False

    def row(self,student,key):
        self.student(student);uuid_text(key)
        r=self.db.execute('SELECT * FROM teaching_material_links WHERE id=? AND student_id=? AND course_id=?',(key,student,COURSE)).fetchone()
        if not r:fail('当前标识下没有该课件关联','teaching_link_not_found',404)
        return dict(r)

    def view(self,row):
        u=self.db.execute('SELECT ordinal,location_json,warnings_json FROM document_units WHERE id=?',(row['unit_id'],)).fetchone()
        return dict(row,current=self.current(row),page_number=json.loads(u['location_json']).get('page_number',u['ordinal']),warnings=json.loads(u['warnings_json']))

    def listing(self,student):
        self.student(student)
        return dict(items=[self.view(dict(r)) for r in self.db.execute('SELECT * FROM teaching_material_links WHERE student_id=? ORDER BY created_at,id',(student,))])

    def operation(self,student,body,action,callback):
        self.student(student);uuid_text(body['request_id']);checksum=digest([action,body])
        with self.repo.transaction():
            row=self.db.execute('SELECT * FROM teaching_material_operations WHERE student_id=? AND request_id=?',(student,body['request_id'])).fetchone()
            if row:
                if row['request_hash']!=checksum:fail('请求编号已用于其他内容','request_id_conflict',409)
                return dict(json.loads(row['result_json']),replayed=True)
            result=callback();self.db.execute('INSERT INTO teaching_material_operations VALUES (?,?,?,?,?)',(student,body['request_id'],checksum,encode(result),now()))
            return dict(result,replayed=False)

    def create(self,student,body):
        def apply():
            doc=self.document(student,body['document_id']);u=self.unit(student,doc,body['run_id'],body['ordinal'])
            if self.db.execute('SELECT count(*) FROM teaching_material_links WHERE student_id=?',(student,)).fetchone()[0]>=200:fail('试点每个学习标识最多200个关联',status=413)
            self.concept(student,body['architecture_id'],body['concept_id'])
            start,end=body['start_offset'],body['end_offset']
            if not 0<=start<end<=len(u['content_md']) or end-start>12000:fail('片段原文范围无效')
            original=u['content_md'][start:end];excerpt=body.get('excerpt_md') or original
            if not excerpt.strip() or len(excerpt)>12000:fail('转录片段须1～12000字符')
            key=str(uuid4());stamp=now()
            self.db.execute('INSERT INTO teaching_material_links VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(key,student,COURSE,doc['id'],doc['current_version_id'],u['run_id'],doc['current_parse_id'],u['id'],u['content_hash'],body['architecture_id'],body['concept_id'],None,start,end,original,excerpt,'extracted' if excerpt==original else 'corrected_transcription','candidate',1,'',stamp,stamp))
            return dict(id=key,revision=1,status='candidate')
        return self.operation(student,body,'create-link',apply)

    def review(self,student,key,body):
        def apply():
            row=self.row(student,key)
            if row['revision']!=body['expected_revision']:fail('关联版本已变化','revision_conflict',409)
            status='confirmed' if body['confirmed'] else 'rejected'
            version=body.get('architecture_version')
            if status=='confirmed':
                if not body.get('reviewer','').strip() or version is None:fail('确认前须核对原页、转录及已发布概念，并填写审核说明')
                row['architecture_version']=version
                if not self.current(row):fail('资料或概念版本已变化/未确认','source_changed',409)
            self.db.execute('UPDATE teaching_material_links SET status=?,architecture_version=?,revision=revision+1,reviewer=?,updated_at=? WHERE id=?',(status,version,body.get('reviewer','').strip(),now(),key))
            return dict(id=key,revision=row['revision']+1,status=status)
        return self.operation(student,body,'review-link:'+key,apply)

    def source(self,student,source_id):
        self.student(student)
        # UUID projection is checked only against documents in this one scope.
        docs=self.db.execute('SELECT id FROM course_documents WHERE student_id=? AND course_id=? AND deleted_at IS NULL',(student,COURSE)).fetchall()
        key=next((r['id'] for r in docs if resource_id(student,'document',r['id'])==source_id),None)
        if not key:fail('当前标识下没有该课件来源','source_not_found',404)
        doc=self.document(student,key)
        links=[dict(r) for r in self.db.execute("SELECT * FROM teaching_material_links WHERE student_id=? AND document_id=? AND status='confirmed' ORDER BY id",(student,key))]
        if not links:fail('课件尚无已确认检索片段','index_unavailable',409)
        ready=doc['parse_status'] in ('ready','partial') and all(self.current(r) for r in links)
        version=digest([doc['revision'],doc['current_version_id'],doc['current_parse_id'],[(r['id'],r['revision'],r['excerpt_md'],r['architecture_version']) for r in links]])
        formal=sorted({k for r in links for k in self.concept(student,r['architecture_id'],r['concept_id'],r['architecture_version'])['formal_knowledge_ids']}) if ready else []
        return dict(source_type='teaching_material',source_id=source_id,source_version=version,source_revision=doc['revision'],content_hash=doc['content_hash'],title=doc['title'],knowledge_point_ids=formal,review_status='human_verified',index_status='ready' if ready else 'pending',error_code=None if ready else 'source_changed',document_id=key,version_id=doc['current_version_id'],run_id=doc['current_parse_id'],links=links)

    def sources(self,student):
        out=[]
        for r in self.db.execute("SELECT DISTINCT document_id FROM teaching_material_links WHERE student_id=? AND status='confirmed'",(student,)):
            try:out.append(self.source(student,resource_id(student,'document',r[0])))
            except ValueError:pass
        return [{k:v for k,v in s.items() if k!='links'} for s in out]

    def validate(self,student,ref):
        from eduagent.services.knowledge import SourceChanged,IndexUnavailable
        from eduagent.domain.notes import NoteNotFound
        try:s=self.source(student,ref['source_id'])
        except ValueError:raise NoteNotFound('当前标识下没有可检索课件来源') from None
        if s['source_version']!=ref['source_version']:raise SourceChanged('课件来源版本已变化，请重新核对')
        if s['index_status']!='ready':raise IndexUnavailable('课件确认片段已失效，请重新审核')
        return s

    def search(self,student,refs,query,knowledge_id=None):
        chunks=[]
        for ref in refs:
            source=self.validate(student,ref)
            for r in source['links']:
                point=self.concept(student,r['architecture_id'],r['concept_id'],r['architecture_version'])
                if knowledge_id and knowledge_id not in point['formal_knowledge_ids']:continue
                u=self.db.execute('SELECT ordinal,location_json FROM document_units WHERE id=?',(r['unit_id'],)).fetchone();page=json.loads(u['location_json']).get('page_number',u['ordinal'])
                chunks.append(dict(source_type='teaching_material',source_id=source['source_id'],source_version=source['source_version'],source_revision=source['source_revision'],content_hash=source['content_hash'],chunk_hash=digest(r['excerpt_md']),chunk_id=r['id'],citation_id='teacher_'+r['id'].replace('-','')+':'+str(r['revision']),title=source['title'],section=point['name']+' · 第'+str(page)+'页',knowledge_point_ids=point['formal_knowledge_ids'],review_status='human_verified',raw_md=r['excerpt_md'],content_text=r['excerpt_md'],start_offset=r['start_offset'],end_offset=r['end_offset'],start_line=1,end_line=max(1,r['original_text'].count('\n')+1),retrieval_score=0.,fusion_score=None,document_id=source['document_id'],version_id=r['version_id'],page_number=page,concept_id=r['concept_id'],architecture_id=r['architecture_id'],architecture_version=r['architecture_version'],excerpt_origin='reviewed_visual_transcription' if self.db.execute('SELECT origin FROM document_units WHERE id=?',(r['unit_id'],)).fetchone()[0]=='deepseek_vision' else r['excerpt_origin'],original_text_snapshot=r['original_text']))
        # Derived index is deliberately rebuilt per selected request; there is
        # no persisted/global index which could leak old or foreign chunks.
        return search_personal(chunks,query,5)
