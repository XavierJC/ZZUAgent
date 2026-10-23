"""Projected catalogue: original stores remain authoritative; GET never sync-writes."""
from hashlib import sha256
import json
from pathlib import Path
from uuid import uuid5,NAMESPACE_URL
from eduagent.domain.personal_bank import fail
from eduagent.services.learning import now
from eduagent.storage.sqlite import encode

COURSE='machine_learning'
TYPES={'teaching_material','reference','personal_note','exercise_material'}


def resource_id(student,kind,key):
    return str(uuid5(NAMESPACE_URL,encode(['eduagent-resource-v1',student,COURSE,kind,key])))


class ResourcesService:
    def __init__(self,learning,materials):
        self.learning,self.repo=learning,learning.repository
        self.db=self.repo.connection;self.materials=Path(materials).resolve()

    def items(self,student):
        self.learning._student(student)
        output=[]
        for r in self.db.execute('SELECT d.*,v.content_hash,v.format,r.status AS parse_status FROM course_documents d JOIN document_versions v ON v.id=d.current_version_id LEFT JOIN document_parse_runs r ON r.id=d.current_parse_id WHERE d.student_id=? AND d.course_id=?',(student,COURSE)):
            output.append(dict(original_source_type='document',original_source_id=r['id'],title=r['title'],
                resource_type='reference' if r['material_role'] in ('textbook','framework') else 'teaching_material',
                source_version=r['current_version_id'],content_hash=r['content_hash'],parse_id=r['current_parse_id'],
                parse_status=r['parse_status'],format=r['format'],status='deleted' if r['deleted_at'] else 'active',
                created_at=r['created_at'],updated_at=r['updated_at'],rag_available=False))
        for r in self.db.execute('SELECT n.*,i.status AS index_status FROM notes n LEFT JOIN note_index_state i ON i.note_id=n.id WHERE n.student_id=? AND n.course_id=?',(student,COURSE)):
            output.append(dict(original_source_type='personal_note',original_source_id=r['id'],title=r['title'],resource_type='personal_note',
                source_version=f"r{r['revision']}-{r['content_hash']}",content_hash=r['content_hash'],parse_id=None,
                parse_status='ready',format='md',status='deleted' if r['deleted_at'] else 'active',
                created_at=r['created_at'],updated_at=r['updated_at'],rag_available=r['index_status']=='ready'))
        manifest=json.loads((self.materials/'manifest.json').read_text(encoding='utf-8'))
        for d in manifest['documents']:
            path=(self.materials/d['file']).resolve()
            if not path.is_relative_to(self.materials):fail('课程来源无效')
            checksum=sha256(path.read_text(encoding='utf-8').encode()).hexdigest()
            version=sha256(json.dumps({'document':d,'hash':checksum},sort_keys=True,ensure_ascii=False).encode()).hexdigest()
            output.append(dict(original_source_type='course_material',original_source_id=d['id'],title=d['title'],resource_type='reference',
                source_version=version,content_hash=checksum,parse_id=None,parse_status='ready',format='md',status='active',
                created_at=None,updated_at=None,rag_available=True,file=d['file']))
        overrides={r['id']:dict(r) for r in self.db.execute('SELECT * FROM course_resources WHERE student_id=? AND course_id=?',(student,COURSE))}
        for r in overrides.values():
            if r['source_type']=='text':
                checksum=sha256(r['content_md'].encode()).hexdigest()
                output.append(dict(original_source_type='text',original_source_id=r['source_id'],title=r['title'],resource_type=r['resource_type'],
                    source_version=checksum,content_hash=checksum,parse_id=None,parse_status='ready',format='txt',status='active',
                    created_at=r['created_at'],updated_at=r['updated_at'],rag_available=False))
        for item in output:
            key=resource_id(student,item['original_source_type'],item['original_source_id']); meta=overrides.get(key)
            item.update(resource_id=key,course_id=COURSE,revision=meta['revision'] if meta else 0,links=json.loads(meta['links_json']) if meta else [])
            if meta:item['resource_type']=meta['resource_type']
            if item['original_source_type']=='document':
                from eduagent.services.teaching_sources import TeachingSources
                try:item['rag_available']=TeachingSources(self.repo).source(student,key)['index_status']=='ready'
                except ValueError:pass
        return output

    def row(self,student,key):
        found=next((r for r in self.items(student) if r['resource_id']==key),None)
        if found is None:fail('当前学习标识下没有该资源','resource_not_found',404)
        return found

    def register(self,student,item):
        timestamp=now()
        self.db.execute('INSERT OR IGNORE INTO course_resources VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
            (item['resource_id'],student,COURSE,item['original_source_type'],item['original_source_id'],item['resource_type'],item['title'],1,'[]',None,timestamp,timestamp))

    def concepts(self,student):
        self.learning._student(student);output=[]
        for r in self.db.execute('SELECT a.id,v.version,v.graph_json FROM knowledge_architectures a JOIN knowledge_versions v ON v.architecture_id=a.id AND v.version=a.published_version WHERE a.student_id=? AND a.course_id=?',(student,COURSE)):
            g=json.loads(r['graph_json'])
            output.append(dict(architecture_id=r['id'],version=r['version'],chapters=g['chapters'],concepts=g['concepts'],name=g['name']))
        return output

    def validate_links(self,student,links):
        if not isinstance(links,list) or len(links)>24:fail('最多24个知识关联')
        graphs={g['architecture_id']:g for g in self.concepts(student)}; seen=set()
        for ref in links:
            if not isinstance(ref,dict) or set(ref)!={'architecture_id','node_id','kind','review_status'}:fail('知识关联字段无效')
            g=graphs.get(ref['architecture_id']);kind=ref['kind'];key=(ref['architecture_id'],ref['node_id'],kind)
            if kind not in ('chapter','concept') or ref['review_status'] not in ('candidate','confirmed') or key in seen:fail('知识关联无效或重复')
            if not g or not any(n['id']==ref['node_id'] for n in g['chapters' if kind=='chapter' else 'concepts']):
                fail('只能关联当前学习标识已发布的知识节点','concept_not_found',404)
            seen.add(key)

    def validate_concepts(self,student,refs):
        self.validate_links(student,[dict(architecture_id=r['architecture_id'],node_id=r['concept_id'],kind='concept',review_status='confirmed') for r in refs])

    def units(self,student,item,run_id=None,ordinals=None):
        if item['status']!='active':fail('原资源已删除，不能重新提取','source_changed',409)
        kind=item['original_source_type']; key=item['original_source_id']
        if kind=='document':
            run=self.db.execute('SELECT * FROM document_parse_runs WHERE id=? AND document_id=? AND version_id=? AND student_id=? AND course_id=?',
                (run_id or item['parse_id'],key,item['source_version'],student,COURSE)).fetchone()
            if not run or run['status'] not in ('ready','partial','empty'):fail('所选解析未就绪或已失效','parse_not_ready',409)
            rows=self.db.execute('SELECT * FROM document_units WHERE run_id=? AND student_id=? ORDER BY ordinal',(run['id'],student)).fetchall()
            if ordinals and not set(ordinals)<={r['ordinal'] for r in rows}:fail('选页不在已保存解析范围内')
            result=[dict(id=r['id'],text=r['text'],ordinal=r['ordinal'],location=json.loads(r['location_json']),origin=r['origin'],warnings=json.loads(r['warnings_json'])) for r in rows if not ordinals or r['ordinal'] in ordinals]
            return result,run['id']
        if run_id or ordinals:fail('非文件资源不接受解析任务或页码')
        if kind=='personal_note':text=self.db.execute('SELECT content_md FROM notes WHERE id=? AND student_id=?',(key,student)).fetchone()[0]
        elif kind=='text':text=self.db.execute('SELECT content_md FROM course_resources WHERE id=? AND student_id=?',(item['resource_id'],student)).fetchone()[0]
        else:text=(self.materials/item['file']).read_text(encoding='utf-8')
        return [dict(text=text,location=dict(start_line=1,end_line=text.count('\n')+1))],None

    def source_status(self,student,source):
        if not source:return 'manual'
        for related in source.get('related_sources',[]):
            status=self.source_status(student,related)
            if status not in ('current','manual'):return status
        if not source.get('resource_id'):return 'manual'
        try:item=self.row(student,source['resource_id'])
        except ValueError:return 'unavailable'
        if item['status']!='active':return 'deleted'
        if item['source_version']!=source['source_version']:return 'modified'
        if source.get('run_id'):
            r=self.db.execute('SELECT status FROM document_parse_runs WHERE id=? AND student_id=?',(source['run_id'],student)).fetchone()
            if not r or r[0] not in ('ready','partial','empty'):return 'unavailable'
            if source.get('origin_mode')=='local' and item['parse_id']!=source['run_id']:return 'reparsed'
        return 'current'
