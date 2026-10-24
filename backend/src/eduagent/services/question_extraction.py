"""Durable paid extraction: reserve, leave transaction, infer, revalidate, publish."""
from hashlib import sha256
import json
from uuid import uuid4
from eduagent.agent import question_extractor as semantic
from eduagent.agent.deepseek import ModelError
from eduagent.domain.personal_bank import fail
from eduagent.documents.models import uuid_text
from eduagent.services.learning import now
from eduagent.services.resources import COURSE,resource_id
from eduagent.storage.sqlite import encode

class QuestionExtractionService:
    def __init__(self,bank,agent,documents=None,client_factory=None):
        self.bank,self.repo,self.db=bank,bank.repo,bank.db
        self.agent,self.documents,self.client_factory=agent,documents,client_factory or semantic.client_for

    def capabilities(self):
        return dict(enabled=bool(self.agent and self.agent.enabled),provider='DeepSeek',model=self.agent.model,
                    max_units=3,max_characters=18000,max_questions=20,max_calls=semantic.MAX_CALLS,max_output_tokens=10000)

    def row(self,student,key):
        self.bank.learning._student(student);uuid_text(key)
        r=self.db.execute('SELECT * FROM question_extraction_tasks WHERE request_id=? AND student_id=? AND course_id=?',(key,student,COURSE)).fetchone()
        if not r:fail('当前学习标识下没有该提取任务','extraction_not_found',404)
        return dict(r)

    def view(self,row):
        context=json.loads(row['context_json']);source=context['source']
        return dict(request_id=row['request_id'],status=row['status'],model_calls=row['model_calls'],created_at=row['created_at'],updated_at=row['updated_at'],
            source=source,source_status=self.bank.resources.source_status(row['student_id'],source),target=context.get('target'),
            result={k:v for k,v in json.loads(row['result_json']).items() if k!='claimed'},max_calls=semantic.MAX_CALLS)

    def get(self,student,key):
        with self.repo.transaction():return self.view(self.row(student,key))

    def list(self,student):
        with self.repo.transaction():
            self.bank.learning._student(student)
            return dict(items=[self.view(dict(r)) for r in self.db.execute('SELECT * FROM question_extraction_tasks WHERE student_id=? AND course_id=? ORDER BY created_at DESC,request_id LIMIT 50',(student,COURSE))])

    def create(self,student,body):
        if not body.get('auto_import'):
            body={k:v for k,v in body.items() if k!='auto_import'}
        uuid_text(body['request_id']);checksum=sha256(encode(body).encode()).hexdigest()
        with self.repo.transaction():
            self.bank.learning._student(student)
            old=self.db.execute('SELECT * FROM question_extraction_tasks WHERE request_id=?',(body['request_id'],)).fetchone()
            if old:
                if old['student_id']!=student:fail('请求编号不可用','request_id_conflict',409)
                if old['request_hash']!=checksum:fail('请求编号已用于不同内容','request_id_conflict',409)
                return self.view(dict(old))
            if not body.get('consent'):fail('请明确同意本轮将选定原文/原页发送至DeepSeek','extraction_consent_required',422)
            if not self.capabilities()['enabled']:fail('模型未启用，可使用本地规则或手工录入','model_disabled',409)
            if self.db.execute('SELECT count(*) FROM question_extraction_tasks WHERE student_id=?',(student,)).fetchone()[0]>=200:fail('当前演示标识最多保留200个提取任务',status=413)
            if self.db.execute("SELECT 1 FROM question_extraction_tasks WHERE status='running' AND student_id=?",(student,)).fetchone():fail('请等待当前提取任务完成','extraction_busy',409)
            target=None
            if body.get('target_question_id'):
                q=self.bank.row(student,body['target_question_id'])
                if q['revision']!=body.get('target_revision'):fail('题目版本已变化','revision_conflict',409)
                target=dict(question_id=q['id'],revision=q['revision'])
            if body.get('resource_id'):
                item=self.bank.resources.row(student,body['resource_id'])
                if item['source_version']!=body['source_version']:fail('来源版本已变化','source_changed',409)
                units,run=self.bank.resources.units(student,item,body.get('run_id'),body.get('ordinals'))
                self.bank.resources.register(student,item)
            else:
                raw=body.get('text','')
                if not raw.strip():fail('请选择来源或输入原题')
                key=str(uuid4());rid=resource_id(student,'text',key);stamp=now()
                self.db.execute('INSERT INTO course_resources VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',(rid,student,COURSE,'text',key,'exercise_material',body.get('title') or '粘贴习题',1,'[]',raw,stamp,stamp))
                item=self.bank.resources.row(student,rid);units,run=self.bank.resources.units(student,item)
            if not 1<=len(units)<=3 or sum(len(u['text']) for u in units)>18000:fail('每轮最多3个相邻单位/18000字符；请缩小选页范围',status=413)
            ordinals=[u.get('ordinal',i+1) for i,u in enumerate(units)]
            if len(ordinals)>1 and ordinals!=list(range(ordinals[0],ordinals[0]+len(ordinals))):fail('请选择相邻页，避免跨页上下文丢失')
            visual=body.get('include_images',False)
            if visual and (item['original_source_type']!='document' or item['format'] not in ('pdf','png','jpg','jpeg','webp')):fail('原页图仅支持PDF和图片')
            source={k:item[k] for k in ('resource_id','title','original_source_type','original_source_id','source_version','content_hash')}
            source.update(run_id=run,origin_mode='local')
            if run:source['origin_mode']=self.db.execute('SELECT mode FROM document_parse_runs WHERE id=?',(run,)).fetchone()[0]
            context=dict(source=source,units=units,include_images=visual,target=target,provider='DeepSeek',model=self.agent.model,consent=True)
            stamp=now()
            self.db.execute('INSERT INTO question_extraction_tasks VALUES (?,?,?,?,?,?,?,?,?,?,?)',(body['request_id'],student,COURSE,checksum,encode(body),encode(context),'running',0,encode(dict(claimed=False)),stamp,stamp))
            return self.view(self.row(student,body['request_id']))

    def recover(self):
        # No interrupted paid request is automatically resent, even if it might
        # have stopped between recording intent and reaching the model server.
        with self.repo.transaction():
            self.db.execute("UPDATE question_extraction_tasks SET status='uncertain',result_json=?,updated_at=? WHERE status='running'",(encode(dict(error_code='execution_unconfirmed',message='服务曾中断；不会自动重新发送，请核对后明确建立新任务。')),now()))

    def claim(self):
        with self.repo.transaction():
            for row in self.db.execute("SELECT * FROM question_extraction_tasks WHERE status='running' ORDER BY created_at,request_id"):
                if not json.loads(row['result_json']).get('claimed'):
                    self.db.execute('UPDATE question_extraction_tasks SET result_json=? WHERE request_id=?',(encode(dict(claimed=True)),row['request_id']))
                    return dict(row)

    def _valid(self,row,context):
        current=self.row(row['student_id'],row['request_id'])
        if current['status']!='running':fail('任务已结束','extraction_ended',409)
        if self.bank.resources.source_status(row['student_id'],context['source'])!='current':fail('原来源已变化','source_changed',409)
        if context.get('target'):
            q=self.bank.row(row['student_id'],context['target']['question_id'])
            if q['revision']!=context['target']['revision']:fail('重识别期间题目已编辑','revision_conflict',409)

    def execute(self,row,cancel=None):
        context=json.loads(row['context_json']);student=row['student_id'];key=row['request_id']
        def before():
            with self.repo.transaction():
                self._valid(row,context)
                if cancel and cancel.is_set():raise ModelError('execution_unconfirmed')
                count=self.row(student,key)['model_calls']
                if count>=semantic.MAX_CALLS:fail('已达到提取调用上限','model_call_limit',409)
                self.db.execute('UPDATE question_extraction_tasks SET model_calls=model_calls+1,updated_at=? WHERE request_id=?',(now(),key))
        try:
            images=[]
            if context['include_images']:
                if not self.documents:fail('页面预览不可用')
                for i,u in enumerate(context['units']):
                    with self.repo.transaction():self._valid(row,context)
                    page=u.get('location',{}).get('page_number',u.get('ordinal',1))
                    images.append((i+1,self.documents.preview(student,context['source']['original_source_id'],context['source']['source_version'],page)))
            # All rendering and network activity is outside any write transaction.
            output=semantic.run(self.client_factory(self.agent),context['units'],images,before,cancel)
            if output.get('error'):raise ValueError(output['error'])
            with self.repo.transaction():
                self._valid(row,context)
                batch=str(uuid4());stamp=now();source=context['source']
                self.db.execute('INSERT INTO question_extractions VALUES (?,?,?,?,?,?,?,?,?)',(batch,student,COURSE,source['resource_id'],source['source_version'],encode(source),encode(output['warnings']),semantic.VERSION,stamp))
                ids=[];intake=dict(ready=0,needs_attention=0,duplicate=0)
                for entry in output['entries']:
                    evidence=dict(source,evidence=entry['evidence'],warnings=entry['warnings'],model_quotes=entry['quotes'],extraction_request_id=key,proposal_for=context.get('target'))
                    if json.loads(row['request_json']).get('auto_import') and not context.get('target'):
                        from eduagent.services.question_intake import auto_entry
                        origin='source_extracted_by_ai' if entry['answer_origin']!='unknown' else 'unknown'
                        qid,state=auto_entry(self.bank,student,entry['payload'],evidence,batch,origin,[*entry['warnings'],*output['warnings']])
                        intake[state]+=1;ids.append(qid)
                    else:ids.append(self.bank._insert_question(student,entry['payload'],evidence,batch,entry['answer_origin']))
                result=dict(question_ids=list(dict.fromkeys(ids)),extraction_id=batch,warnings=output['warnings'],usage=output['usage'],intake=intake,
                            message='识别完整的题已进入普通练习；异常保留待处理。未人工核验，不更新BKT。' if any(intake.values()) else '仅保存新的待审核草稿；没有覆盖原题。')
                self.db.execute("UPDATE question_extraction_tasks SET status='complete',result_json=?,updated_at=? WHERE request_id=?",(encode(result),stamp,key))
        except Exception as e:
            code=getattr(e,'code',None) or (str(e) if isinstance(e,ValueError) and len(str(e))<100 else 'extraction_failed')
            status='stale' if code in ('source_changed','revision_conflict','extraction_ended') else 'uncertain' if code in ('model_timeout','network_error','upstream_error','execution_unconfirmed') else 'failed'
            # Only enumerated diagnostics leave this layer, never raw upstream text.
            safe={'source_changed','revision_conflict','extraction_ended','model_timeout','network_error','upstream_error','execution_unconfirmed','model_output_truncated','authentication_failed','insufficient_balance','rate_limited','model_disabled','tool_scope_rejected','quote_not_in_selected_original','stem_not_in_original','option_not_in_original','answer_not_in_original','answer_key_not_in_original','invalid_top_fields','invalid_structure','batch_too_large_select_fewer_pages'}
            if code not in safe and code not in ('invalid_question_payload','ambiguous_answer_keys','invalid_question_count','invalid_question_fields','invalid_quotes','invalid_warnings','source_scope_rejected'):code='extraction_validation_failed'
            with self.repo.transaction():
                self.db.execute("UPDATE question_extraction_tasks SET status=?,result_json=?,updated_at=? WHERE request_id=? AND status='running'",(status,encode(dict(error_code=code,message='未发布题目；原文已保留。请缩小范围、对照原页后明确重试，不会自动重发付费请求。')),now(),key))

