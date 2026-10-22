"""Versioned knowledge structures. All learning state access is read-only."""
from copy import deepcopy
from hashlib import sha256
import json
from uuid import uuid4

from eduagent.domain.architecture import graph, reject
from eduagent.documents.models import uuid_text
from eduagent.documents.architecture_candidates import extract, RULE_VERSION
from eduagent.storage.sqlite import encode
from eduagent.storage.documents import DocumentRepository
from eduagent.services.guidance import GuidanceService
from eduagent.services.learning import now


class ArchitectureService:
    def __init__(self, learning):
        self.learning,self.repo=learning,learning.repository
        self.db=self.repo.connection

    def student(self,student): self.learning._student(student)

    def row(self,student,key):
        self.student(student); uuid_text(key)
        row=self.db.execute('SELECT * FROM knowledge_architectures WHERE id=? AND student_id=? AND course_id=?',(key,student,'machine_learning')).fetchone()
        if row is None: reject('当前学习标识下没有该知识体系','architecture_not_found',404)
        return dict(row)

    def draft_row(self,row):
        return dict(self.db.execute('SELECT * FROM knowledge_drafts WHERE architecture_id=? AND student_id=?',(row['id'],row['student_id'])).fetchone())

    def batch_row(self,row,key):
        uuid_text(key)
        found=self.db.execute('SELECT * FROM knowledge_candidate_batches WHERE id=? AND architecture_id=? AND student_id=? AND course_id=?',(key,row['id'],row['student_id'],row['course_id'])).fetchone()
        if found is None: reject('当前体系下没有该候选依据','candidate_not_found',404)
        return dict(found)

    def source_status(self,source,student):
        row=self.db.execute('SELECT d.*,r.status AS parse_status FROM course_documents d LEFT JOIN document_parse_runs r ON r.id=d.current_parse_id WHERE d.id=? AND d.student_id=? AND d.course_id=?',
                            (source['document_id'],student,'machine_learning')).fetchone()
        if not row or row['deleted_at']: return 'deleted'
        if row['current_version_id']!=source['version_id']: return 'modified'
        if row['current_parse_id']!=source['run_id']: return 'reparsed'
        if row['parse_status'] not in ('ready','partial','empty'): return 'unavailable'
        if row['revision']!=source['document_revision']: return 'metadata_modified'
        return 'current'

    def sources(self,row,value):
        output=[]; seen=set(); batches={}
        for node in value['chapters']+value['concepts']:
            for ref in node['origins']:
                pair=(ref['batch_id'],ref['item_id'])
                if pair in seen: continue
                seen.add(pair)
                if pair[0] not in batches:
                    batches[pair[0]]={e['item_id']:e for e in json.loads(self.batch_row(row,pair[0])['evidence_json'])}
                evidence=batches[pair[0]].get(pair[1])
                if evidence is None: reject('来源依据不存在','candidate_not_found',404)
                output.append(dict(evidence,batch_id=pair[0],current_status=self.source_status(evidence,row['student_id'])))
        return output

    def view(self,row):
        draft=self.draft_row(row); value=json.loads(draft['graph_json'])
        return dict(id=row['id'],course_id=row['course_id'],title=row['title'],revision=row['revision'],published_version=row['published_version'],
            created_at=row['created_at'],updated_at=row['updated_at'],draft=dict(status=draft['status'],base_version=draft['base_version'],graph=value,sources=self.sources(row,value)),
            versions=[dict(v) for v in self.db.execute('SELECT version,graph_hash,published_at FROM knowledge_versions WHERE architecture_id=? AND student_id=? ORDER BY version DESC',(row['id'],row['student_id']))])

    def listing(self,student):
        with self.repo.transaction():
            self.student(student)
            return dict(items=[dict(r) for r in self.db.execute('SELECT a.id,a.title,a.revision,a.published_version,d.status AS draft_status,a.updated_at FROM knowledge_architectures a JOIN knowledge_drafts d ON d.architecture_id=a.id WHERE a.student_id=? AND a.course_id=? ORDER BY a.updated_at DESC,a.id',(student,'machine_learning'))])

    def get(self,student,key):
        with self.repo.transaction(): return self.view(self.row(student,key))

    def published(self,student,key,version=None):
        with self.repo.transaction():
            row=self.row(student,key)
            version=row['published_version'] if version is None else version
            found=self.db.execute('SELECT * FROM knowledge_versions WHERE architecture_id=? AND version=? AND student_id=?',(key,version,student)).fetchone()
            if found is None: reject('该体系还没有此已确认版本','version_not_found',404)
            value=json.loads(found['graph_json'])
            # Immutable snapshot content; only the separately reported status changes.
            sources=[dict(s,current_status=self.source_status(s,student)) for s in json.loads(found['sources_json'])]
            return dict(architecture_id=key,version=version,status='published',graph=value,sources=sources,
                        graph_hash=found['graph_hash'],published_at=found['published_at'])

    def receipt(self,student,request_id):
        self.student(student); uuid_text(request_id)
        found=self.db.execute('SELECT result_json FROM knowledge_operations WHERE student_id=? AND course_id=? AND request_id=?',(student,'machine_learning',request_id)).fetchone()
        if found is None: reject('当前学习标识下没有该请求回执','architecture_not_found',404)
        return json.loads(found['result_json'])

    def _write(self,student,request_id,operation,body,callback):
        uuid_text(request_id); checksum=sha256(encode(dict(operation=operation,body=body)).encode()).hexdigest()
        with self.repo.transaction():
            self.student(student)
            previous=self.db.execute('SELECT * FROM knowledge_operations WHERE student_id=? AND course_id=? AND request_id=?',(student,'machine_learning',request_id)).fetchone()
            if previous:
                if previous['request_hash']!=checksum: reject('请求编号已用于不同内容','request_id_conflict',409)
                return dict(json.loads(previous['result_json']),replayed=True)
            result=callback()
            self.db.execute('INSERT INTO knowledge_operations VALUES (?,?,?,?,?,?,?)',(student,'machine_learning',request_id,result['architecture_id'],checksum,encode(result),now()))
            return dict(result,replayed=False)

    def create(self,student,body):
        def apply():
            if self.db.execute('SELECT count(*) FROM knowledge_architectures WHERE student_id=?',(student,)).fetchone()[0]>=25: reject('每个学习标识最多25个体系')
            value=graph(dict(name=body['name'],description=body.get('description','')),self.learning.catalog.knowledge)
            key=str(uuid4()); timestamp=now()
            self.db.execute('INSERT INTO knowledge_architectures VALUES (?,?,?,?,?,?,?,?)',(key,student,'machine_learning',value['name'],1,0,timestamp,timestamp))
            self.db.execute('INSERT INTO knowledge_drafts VALUES (?,?,?,?,?,?,?)',(key,student,'machine_learning','editing',0,encode(value),timestamp))
            return dict(architecture_id=key,revision=1)
        return self._write(student,body['request_id'],'create',body,apply)

    def editable(self,student,key,expected):
        row=self.row(student,key)
        if type(expected) is not int or row['revision']!=expected: reject('体系版本已变化，请保留草稿并读取新版本','revision_conflict',409)
        return row

    def _bump(self,row,title=None):
        self.db.execute('UPDATE knowledge_architectures SET title=?,revision=revision+1,updated_at=? WHERE id=? AND student_id=?',(title or row['title'],now(),row['id'],row['student_id']))
        return row['revision']+1

    def save(self,student,key,body):
        def apply():
            row=self.editable(student,key,body['expected_revision'])
            if self.draft_row(row)['status']!='editing': reject('已发布草稿不可修改，请先创建新草稿','draft_locked',409)
            value=graph(body['graph'],self.learning.catalog.knowledge); sources=self.sources(row,value)
            if any(s['current_status']!='current' for s in sources): reject('候选来源已变化，请重新提取或明确解除旧来源','source_changed',409)
            for kind,items in (('chapter',value['chapters']),('concept',value['concepts'])):
                for item in items:
                    identity=self.db.execute('SELECT kind FROM knowledge_entities WHERE architecture_id=? AND id=?',(key,item['id'])).fetchone()
                    if identity and identity['kind']!=kind: reject('稳定ID不能改作其他节点类型')
                    self.db.execute('INSERT OR IGNORE INTO knowledge_entities VALUES (?,?,?,?,?,?)',(key,item['id'],student,'machine_learning',kind,now()))
            self.db.execute('UPDATE knowledge_drafts SET graph_json=?,updated_at=? WHERE architecture_id=? AND student_id=?',(encode(value),now(),key,student))
            return dict(architecture_id=key,revision=self._bump(row,value['name']))
        return self._write(student,body['request_id'],'save',dict(architecture_id=key,**body),apply)

    def fork(self,student,key,body):
        def apply():
            row=self.editable(student,key,body['expected_revision'])
            if self.draft_row(row)['status']=='editing': reject('已有未发布草稿，请先保存并处理，不会覆盖','draft_exists',409)
            version=body['version']
            previous=self.db.execute('SELECT graph_json FROM knowledge_versions WHERE architecture_id=? AND student_id=? AND version=?',(key,student,version)).fetchone()
            if previous is None: reject('已确认版本不存在','version_not_found',404)
            value=json.loads(previous['graph_json'])
            self.db.execute("UPDATE knowledge_drafts SET graph_json=?,status='editing',base_version=?,updated_at=? WHERE architecture_id=? AND student_id=?",(encode(value),version,now(),key,student))
            return dict(architecture_id=key,revision=self._bump(row,value['name']))
        return self._write(student,body['request_id'],'fork',dict(architecture_id=key,**body),apply)

    def publish(self,student,key,body):
        def apply():
            row=self.editable(student,key,body['expected_revision']); draft=self.draft_row(row)
            if body.get('confirmed') is not True: reject('请明确确认已审阅本次章节及概念')
            if draft['status']!='editing': reject('此草稿已发布','draft_locked',409)
            if row['published_version']>=50: reject('首版每体系最多50个发布版本')
            value=graph(json.loads(draft['graph_json']),self.learning.catalog.knowledge)
            if not value['chapters'] or not value['concepts']: reject('发布前至少需要一个章节和一个知识概念')
            sources=self.sources(row,value)
            if any(s['current_status']!='current' for s in sources): reject('来源已变化，旧候选不能作为当前内容发布','source_changed',409)
            for node in value['chapters']+value['concepts']: node['review_status']='confirmed'
            version=row['published_version']+1; timestamp=now(); raw=encode(value)
            self.db.execute('INSERT INTO knowledge_versions VALUES (?,?,?,?,?,?,?,?)',(key,version,student,'machine_learning',raw,sha256(raw.encode()).hexdigest(),encode(sources),timestamp))
            self.db.execute("UPDATE knowledge_drafts SET status='locked',graph_json=?,updated_at=? WHERE architecture_id=? AND student_id=?",(raw,timestamp,key,student))
            revision=self._bump(row)
            self.db.execute('UPDATE knowledge_architectures SET published_version=? WHERE id=? AND student_id=?',(version,key,student))
            return dict(architecture_id=key,revision=revision,version=version)
        return self._write(student,body['request_id'],'publish',dict(architecture_id=key,**body),apply)

    def candidates(self,student,key,body):
        def apply():
            row=self.editable(student,key,body['expected_revision'])
            if self.db.execute('SELECT count(*) FROM knowledge_candidate_batches WHERE architecture_id=?',(key,)).fetchone()[0]>=100: reject('候选批次已达100个限额')
            selections=body['documents']
            if not isinstance(selections,list) or not 1<=len(selections)<=3 or len({x['document_id'] for x in selections})!=len(selections): reject('请选择1～3份不同课件')
            store=DocumentRepository(self.repo); inputs=[]
            for ref in selections:
                doc=store.document(student,ref['document_id']); version=store.version(doc); run=store.run(doc)
                if version['id']!=ref['version_id'] or run['id']!=ref['run_id']: reject('课件版本或解析已变化','source_changed',409)
                if run['mode']!='local' or run['status'] not in ('ready','partial','empty'): reject('只使用已完成的当前本地解析','parse_not_ready',409)
                units=[]
                for u in self.db.execute('SELECT * FROM document_units WHERE run_id=? AND document_id=? AND student_id=? ORDER BY ordinal',(run['id'],doc['id'],student)):
                    item=dict(u); item['location']=json.loads(item['location_json']); units.append(item)
                inputs.append((doc,version,run,units))
            batch_id=str(uuid4()); values=extract(batch_id,inputs)
            self.db.execute('INSERT INTO knowledge_candidate_batches VALUES (?,?,?,?,?,?,?,?,?)',(batch_id,key,student,'machine_learning',RULE_VERSION,
                encode(values['graph']),encode(values['evidence']),encode(values['unclassified']),now()))
            # Candidate extraction does not edit/publish the draft or learning facts.
            return dict(architecture_id=key,revision=row['revision'],batch_id=batch_id)
        return self._write(student,body['request_id'],'candidates',dict(architecture_id=key,**body),apply)

    def batch(self,student,key,batch_id):
        with self.repo.transaction():
            row=self.row(student,key); batch=self.batch_row(row,batch_id)
            return dict(id=batch_id,graph=json.loads(batch['graph_json']),rule_version=batch['rule_version'],created_at=batch['created_at'],
                evidence=[dict(e,current_status=self.source_status(e,student)) for e in json.loads(batch['evidence_json'])],unclassified=json.loads(batch['unclassified_json']))

    def states(self,student,key,concept_id,version=None,draft=False):
        with self.repo.transaction():
            row=self.row(student,key); uuid_text(concept_id)
            if draft:
                value=json.loads(self.draft_row(row)['graph_json']); actual_version=None
            else:
                actual_version=version or row['published_version']
                found=self.db.execute('SELECT graph_json FROM knowledge_versions WHERE architecture_id=? AND student_id=? AND version=?',(key,student,actual_version)).fetchone()
                if found is None: reject('没有该已确认版本','version_not_found',404)
                value=json.loads(found['graph_json'])
            concept=next((c for c in value['concepts'] if c['id']==concept_id),None)
            if concept is None: reject('当前结构没有该概念','concept_not_found',404)
            snapshot=GuidanceService(self.learning)._snapshot(student)
            points=[dict(p,status='diagnosed' if p['objective']['has_evidence'] else 'pending_diagnosis') for p in snapshot['items'] if p['knowledge_id'] in concept['formal_knowledge_ids']]
            return dict(concept_id=concept_id,formal_association_only=True,version=actual_version,draft=draft,items=points,
                learning_revision=snapshot['learning_revision'],assessment_revision=snapshot['assessment_revision'],versions=snapshot['versions'])
