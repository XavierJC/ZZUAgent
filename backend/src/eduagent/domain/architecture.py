"""Bounded course graph rules, independent of BKT and the formal prerequisite DAG."""
from copy import deepcopy
import json
from eduagent.documents.models import uuid_text


class ArchitectureError(ValueError):
    def __init__(self, code, message, status=422):
        self.code,self.status=code,status
        super().__init__(message)


def reject(message, code='invalid_architecture', status=422):
    raise ArchitectureError(code,message,status)


def fields(value, allowed):
    if not isinstance(value,dict) or set(value)-set(allowed): reject('知识结构含无效字段')


def text(value, label, size=120, empty=False):
    if not isinstance(value,str) or len(value)>size or (not empty and not value.strip()) or any(ord(c)<32 and c not in '\n\r\t' for c in value):
        reject(label+'无效或超过长度限制')
    return value.strip() if not empty else value


def acyclic(nodes, edges, label, max_depth=None):
    children={node:[] for node in nodes}; incoming={node:0 for node in nodes}
    for source,target in edges:
        children[source].append(target); incoming[target]+=1
    ready=[n for n in nodes if not incoming[n]]; depths={n:1 for n in ready}; count=0
    while ready:
        current=ready.pop(); count+=1
        if max_depth and depths[current]>max_depth: reject(label+'最多10层')
        for target in children[current]:
            depths[target]=max(depths.get(target,1),depths[current]+1); incoming[target]-=1
            if not incoming[target]: ready.append(target)
    if count!=len(nodes): reject(label+'不能形成环','architecture_cycle')


def graph(value, formal_ids):
    fields(value,('name','description','chapters','concepts','relations'))
    output=dict(name=text(value.get('name'),'体系名称'), description=text(value.get('description',''),'简介',2000,True))
    seen=set()
    for group,limit,allowed in (
        ('chapters',100,('id','title','summary','parent_id','order','origins','review_status')),
        ('concepts',150,('id','name','summary','chapter_ids','formal_knowledge_ids','origins','review_status')),
        ('relations',300,('id','source_id','target_id','kind','description'))):
        items=value.get(group,[])
        if not isinstance(items,list) or len(items)>limit: reject(group+'数量超过限额')
        output[group]=[]
        for raw in items:
            fields(raw,allowed); item=deepcopy(raw); key=uuid_text(item.get('id'))
            if key in seen: reject('节点或关系ID重复')
            seen.add(key)
            if group=='relations':
                item=dict(id=key,source_id=uuid_text(item.get('source_id')),target_id=uuid_text(item.get('target_id')),
                    kind=item.get('kind'),description=text(item.get('description',''),'关系说明',500,True))
                if item['kind'] not in ('contains','related_to','prerequisite_candidate'): reject('关系类型无效')
                if item['source_id']==item['target_id']: reject('概念关系不能指向自身')
                if item['kind']=='related_to' and item['source_id']>item['target_id']:
                    item['source_id'],item['target_id']=item['target_id'],item['source_id']
            else:
                label='title' if group=='chapters' else 'name'
                item[label]=text(item.get(label),'节点名称'); item['summary']=text(item.get('summary',''),'节点简介',2000,True)
                item['review_status']=item.get('review_status','candidate')
                if item['review_status'] not in ('candidate','confirmed'): reject('节点审核状态无效')
                item['origins']=item.get('origins',[])
                if not isinstance(item['origins'],list) or len(item['origins'])>8: reject('节点来源最多8个')
                refs=set()
                for ref in item['origins']:
                    fields(ref,('batch_id','item_id')); pair=(uuid_text(ref.get('batch_id')),uuid_text(ref.get('item_id')))
                    if pair in refs: reject('节点来源重复')
                    refs.add(pair)
                if group=='chapters':
                    item['parent_id']=uuid_text(item['parent_id']) if item.get('parent_id') is not None else None
                    order=item.get('order',0)
                    if type(order) is not int or not 0<=order<=10000: reject('章节顺序须为0～10000整数')
                    item['order']=order
                else:
                    for field in ('chapter_ids','formal_knowledge_ids'):
                        values=item.get(field,[])
                        if not isinstance(values,list) or len(values)>100 or any(not isinstance(x,str) for x in values) or len(set(values))!=len(values): reject('概念关联列表无效')
                        item[field]=values
                    if set(item['formal_knowledge_ids'])-set(formal_ids): reject('只能关联已有正式知识点')
            output[group].append(item)
    chapters={x['id'] for x in output['chapters']}; concepts={x['id'] for x in output['concepts']}
    chapter_edges=[]
    for item in output['chapters']:
        if item['parent_id'] is not None:
            if item['parent_id'] not in chapters: reject('章节父节点不存在；删除前请解除引用')
            chapter_edges.append((item['parent_id'],item['id']))
    acyclic(chapters,chapter_edges,'章节结构',10)
    for item in output['concepts']:
        if set(item['chapter_ids'])-chapters: reject('概念所属章节不存在；删除前请解除引用')
    relation_keys=set()
    for edge in output['relations']:
        if edge['source_id'] not in concepts or edge['target_id'] not in concepts: reject('关系引用了不存在的概念；删除前请解除引用')
        key=(edge['kind'],edge['source_id'],edge['target_id'])
        if key in relation_keys: reject('概念关系重复')
        relation_keys.add(key)
    for kind in ('contains','prerequisite_candidate'):
        acyclic(concepts,[(r['source_id'],r['target_id']) for r in output['relations'] if r['kind']==kind],kind)
    if len(json.dumps(output,ensure_ascii=False).encode())>512*1024: reject('知识体系超过512KiB限额')
    return output
