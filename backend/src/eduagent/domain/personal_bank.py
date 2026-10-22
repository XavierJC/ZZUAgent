"""Strict, deterministic personal-question validation. No formal grading imports."""
from copy import deepcopy
from eduagent.domain.architecture import ArchitectureError, text
from eduagent.documents.models import uuid_text

QUESTION_TYPES = ('single_choice', 'multiple_choice', 'true_false', 'fill_blank', 'short_answer', 'calculation', 'proof', 'unknown', 'other')
OBJECTIVE_TYPES = ('single_choice', 'true_false')


def fail(message, code='invalid_personal_bank', status=422):
    raise ArchitectureError(code,message,status)


def question(value, *, child=False):
    allowed={'number','question_type','stem','options','answer','explanation','concepts','shared_context','answer_text','answer_keys','subquestions','dependencies','issues'}
    if not isinstance(value,dict) or set(value)-allowed: fail('题目含未约定字段')
    kind=value.get('question_type','other')
    if kind not in QUESTION_TYPES: fail('不支持此题型')
    out=dict(number=text(value.get('number',''),'题号',40,True),question_type=kind,
             stem=text(value.get('stem',''),'题干',16000),explanation=text(value.get('explanation',''),'解析',16000,True))
    options=value.get('options',[])
    if not isinstance(options,list) or len(options)>12: fail('选项最多12项')
    seen=set(); out['options']=[]
    for option in options:
        if not isinstance(option,dict) or set(option)!={'key','text'}: fail('选项字段无效')
        key=text(option['key'],'选项标识',8)
        if key in seen: fail('选项标识重复')
        seen.add(key);out['options'].append(dict(key=key,text=text(option['text'],'选项',4000)))
    if kind=='true_false':
        out['options']=[dict(key='true',text='正确'),dict(key='false',text='错误')]; seen={'true','false'}
    answer=value.get('answer')
    if answer is not None and (not isinstance(answer,str) or answer not in seen): fail('答案必须是有效选项，未知答案请留空')
    out['answer']=answer
    for name,limit in (('shared_context',16000),('answer_text',16000)):
        if name in value:out[name]=text(value[name],name,limit,True)
    for name in ('answer_keys','dependencies','issues'):
        if name not in value:continue
        items=value[name]
        if not isinstance(items,list) or len(items)>30 or any(not isinstance(s,str) or len(s)>500 for s in items):fail(name+'字段无效')
        if name=='answer_keys' and (len(set(items))!=len(items) or any(s not in seen for s in items)):fail('多选答案必须属于选项')
        out[name]=list(items)
    if 'subquestions' in value:
        if child and value['subquestions']:fail('子问不能无限嵌套')
        if not isinstance(value['subquestions'],list) or len(value['subquestions'])>20:fail('子问最多20项')
        out['subquestions']=[question(v,child=True) for v in value['subquestions']]
    concepts=value.get('concepts',[])
    if not isinstance(concepts,list) or len(concepts)>12: fail('概念关联最多12项')
    out['concepts']=[]; seen=set()
    for ref in concepts:
        if not isinstance(ref,dict) or set(ref)!={'architecture_id','concept_id'}: fail('概念关联字段无效')
        pair=(uuid_text(ref['architecture_id']),uuid_text(ref['concept_id']))
        if pair in seen: fail('概念关联重复')
        seen.add(pair);out['concepts'].append(deepcopy(ref))
    return out


def practice_ready(value):
    if value['question_type'] in ('other','unknown'):fail('请先确认题型再进入普通练习')
    if value['question_type'] in ('single_choice','multiple_choice','true_false') and len(value['options'])<2: fail('选择题至少两个有效选项')


def grading_mode(value):
    return 'objective' if value['question_type'] in OBJECTIVE_TYPES else 'text_ungraded'

