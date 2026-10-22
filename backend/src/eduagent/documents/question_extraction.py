"""Original-question segmentation only; never synthesize absent answers."""
import re
from collections import Counter
from eduagent.domain.personal_bank import question,fail

RULE_VERSION='original-question-rules-v2'
START=re.compile(r'^\s*(?:第\s*(\d{1,4})\s*题\s*[.．、:：]?|[（(](\d{1,4})[）)]|\s*(\d{1,4})\s*[.．、)）])\s*(\S.*)$')
OPTION=re.compile(r'(?m)^\s*([A-H])[.．、:：)）]\s*')
ANSWER=re.compile(r'(?m)^\s*(?:参考答案|标准答案|答案|正确答案)\s*[:：]\s*([^\n]+)')
EXPLANATION=re.compile(r'(?m)^\s*(?:解析|解答|解释)\s*[:：]\s*')


def extract(units):
    # Joining keeps cross-page continuation. Every span still maps back to exact
    # per-unit offsets; page boundaries are not inferred question boundaries.
    pieces=[]; bounds=[]; cursor=0
    for u in units:
        raw=u.get('text',''); pieces.append(raw+'\n')
        bounds.append((cursor,cursor+len(raw),u));cursor+=len(raw)+1
    text=''.join(pieces)
    if len(text)>120000: fail('每轮提取最多12万字符，请缩小所选页面',status=413)
    starts=[]; offset=0; fenced=False; math=False
    for line in text.splitlines(keepends=True):
        stripped=line.strip()
        if stripped.startswith(('```','~~~')): fenced=not fenced
        if stripped=='$$': math=not math
        match=START.match(line) if not fenced and not math else None
        if match and not (match.group(2) and starts): starts.append((offset, next(x for x in match.groups()[:3] if x is not None)))
        offset+=len(line)
    warnings=[]
    if not starts:
        starts=[(0,'')]; warnings.append('question_boundaries_uncertain_manual_review')
    if len(starts)>80: fail('每批最多80题，请缩小资料范围',status=413)
    counts=Counter(n for _,n in starts if n)
    preamble=text[:starts[0][0]].strip()
    output=[]
    for i,(start,number) in enumerate(starts):
        end=starts[i+1][0] if i+1<len(starts) else len(text)
        raw=text[start:end].strip(); local=[]
        if counts[number]>1: local.append('duplicate_question_number')
        if not raw: continue
        body=START.sub(lambda m:m.group(4),raw,count=1)
        # Normalize inline A. / B. option separators, leaving raw evidence intact.
        body=re.sub(r'(?<=\S)[ \t]+(?=[A-H][.．、)）]\s)', '\n',body)
        am=ANSWER.search(body); em=EXPLANATION.search(body)
        cut=min([m.start() for m in (am,em) if m]+[len(body)])
        main=body[:cut].strip(); matches=list(OPTION.finditer(main))
        options=[]
        for j,m in enumerate(matches):
            val=main[m.end():matches[j+1].start() if j+1<len(matches) else len(main)].strip()
            if val: options.append(dict(key=m.group(1),text=val))
        stem=main[:matches[0].start()].strip() if matches else main
        if preamble:
            stem=preamble+'\n\n'+stem
            local.append('shared_context_requires_review')
        # A/B labels alone also denote tasks or cases. Require an actual choice
        # instruction; otherwise preserve the labelled text as part of the stem.
        choice=bool(am and re.fullmatch(r'[A-H][。.]?',am.group(1).strip())) or bool(re.search(r'单选|多选|选择题|选出|下列.*(?:哪|正确|错误)|以下.*(?:哪|正确|错误)|[（(]\s*[）)]',stem))
        if len(options)>=2 and choice:kind='multiple_choice' if re.search(r'多选|哪些|所有正确',stem) else 'single_choice'
        else:
            if matches:stem=(preamble+'\n\n' if preamble else '')+main;options=[]
            kind='true_false' if re.search(r'判断|对错|正确.*错误',stem) else 'proof' if re.search(r'证明|证实',stem) else 'calculation' if re.search(r'计算|求解|求梯度|推导',stem) else 'fill_blank' if re.search(r'填空|_{3,}',stem) else 'short_answer' if re.search(r'简答|说明|解释|为什么|描述|什么|比较',stem) else 'unknown'

        if kind=='unknown':local.append('question_type_uncertain')
        answer=None
        if am:
            token=am.group(1).strip()
            if kind=='single_choice' and re.fullmatch(r'[A-H][。.]?',token): answer=token[0]
            if kind=='true_false':
                if token in ('对','正确','√','True','true'):answer='true'
                if token in ('错','错误','×','False','false'):answer='false'
            if answer is None and kind in ('single_choice','true_false'):local.append('source_answer_not_normalized')
        if not am:local.append('answer_missing')
        if re.search(r'见图|下图|如图|\|.+\|',raw):local.append('visual_or_table_requires_review')
        if raw.count('$$')%2 or raw.count('```')%2:local.append('formula_or_code_boundary_uncertain')
        if len(stem)>16000 or any(len(o['text'])>4000 for o in options):
            fail('单题超过编辑限额，请减少选页或手动分段',status=413)
        if len({o['key'] for o in options})!=len(options):
            local.append('duplicate_options_manual_review');options=[];kind='other';stem=main;answer=None
        if answer and answer not in {o['key'] for o in options} and kind!='true_false':
            local.append('source_answer_not_in_options');answer=None
        evidence=[]
        for left,right,u in bounds:
            if preamble:
                a=max(0,left);b=min(starts[0][0],right)
                if a<b:evidence.append(dict(unit_id=u.get('id'),location=u.get('location',{}),origin=u.get('origin','local_extraction'),
                    start_offset=a-left,end_offset=b-left,raw_md=u['text'][a-left:b-left],warnings=['shared_context_requires_review',*u.get('warnings',[])]))
            a=max(start,left);b=min(end,right)
            if a<b:
                evidence.append(dict(unit_id=u.get('id'),location=u.get('location',{}),origin=u.get('origin','local_extraction'),
                    start_offset=a-left,end_offset=b-left,raw_md=u['text'][a-left:b-left],warnings=u.get('warnings',[])))
        model_origin=any(e['origin']=='deepseek_vision' for e in evidence)
        if model_origin:local.append('model_transcription_unverified')
        payload=question(dict(number=number,stem=stem or raw[:16000],question_type=kind,options=options,answer=answer,
                              explanation=body[em.end():].strip() if em else '',concepts=[],shared_context=preamble,answer_text=am.group(1).strip() if am and kind not in ('single_choice','true_false') else '',dependencies=['原图或表格'] if 'visual_or_table_requires_review' in local else []))
        output.append(dict(payload=payload,evidence=evidence,warnings=local,answer_origin=('model_inferred' if model_origin else 'source_provided') if answer or payload.get('answer_text') else 'unknown',
                           original_answer_text=am.group(1) if am else None))
    return output,warnings
