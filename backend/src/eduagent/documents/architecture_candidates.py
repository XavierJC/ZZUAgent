"""Reproducible heading/explicit-term candidates; no LLM or prerequisite inference."""
import re
from uuid import UUID, uuid5
from eduagent.domain.architecture import reject

RULE_VERSION='heading-and-explicit-concept-v1'
# Full heading matches only, not substring classification of every paragraph.
TERMS={'线性回归','损失函数','梯度下降','逻辑回归','过拟合','正则化','模型评估','主成分分析','PCA',
       '支持向量机','SVM','决策树','随机森林','朴素贝叶斯','K均值聚类','交叉验证','偏差与方差','神经网络'}


def extract(batch_id, documents):
    graph=dict(name='候选结构',description='',chapters=[],concepts=[],relations=[])
    evidence={}; unclassified=[]
    def key(seed): return str(uuid5(UUID(batch_id),seed))
    for doc,version,run,units in documents:
        stack=[]; seen_locations=set()
        for u in units:
            location=u['location']; raw=u['text']; headings=[]
            if location.get('hidden'):
                unclassified.append(dict(document_id=doc['id'],unit_id=u['id'],location=location,reason='hidden_slide')); continue
            if u['kind']=='pptx_slide' and not re.fullmatch(r'第\d+张幻灯片',u['title']):
                pos=raw.find(u['title'])
                if pos>=0: headings.append((1,u['title'].strip(),pos,pos+len(u['title'])))
            offset=0; protected=False; math=False
            for line in raw.splitlines(keepends=True):
                stripped=line.strip()
                if stripped.startswith(('```','~~~')): protected=not protected
                if stripped.startswith('$$'): math=not math if stripped=='$$' else math
                if not protected and not math:
                    md=re.match(r'^(#{1,4})\s+(.+?)\s*#*$',stripped)
                    # A plain "1. sentence" is often a list item, not a chapter.
                    numbered=re.match(r'^(?:第[一二三四五六七八九十百\d]+[章节]\s*|\d+(?:\.\d+){1,3}\s+)([^。？！；]{2,60})$',stripped)
                    if md:
                        title=md[2].strip(); start=offset+line.find(title); headings.append((len(md[1]),title,start,start+len(title)))
                    elif numbered:
                        headings.append((min(4,stripped.split()[0].count('.')+1),stripped,offset,offset+len(line.rstrip())))
                offset+=len(line)
            def origin(item_id,start,end,method):
                end=min(end,start+500)
                evidence[item_id]=dict(item_id=item_id,document_id=doc['id'],document_revision=doc['revision'],source_title=doc['title'],
                    version_id=version['id'],file_revision=version['file_revision'],content_hash=version['content_hash'],run_id=run['id'],
                    parser_version=run['parser_version'],unit_id=u['id'],unit_hash=u['content_hash'],location=location,
                    start_offset=start,end_offset=end,raw_text=raw[start:end],method=method,review_status='candidate')
                return [dict(batch_id=batch_id,item_id=item_id)]
            chapter=None
            for level,title,start,end in headings:
                if not 2<=len(title)<=120 or (u['id'],start,'heading') in seen_locations: continue
                seen_locations.add((u['id'],start,'heading'))
                while stack and stack[-1][0]>=level: stack.pop()
                chapter=key(u['id']+':chapter:'+str(start))
                graph['chapters'].append(dict(id=chapter,title=title,summary='',parent_id=stack[-1][1] if stack else None,
                    order=len(graph['chapters']),review_status='candidate',origins=origin(chapter,start,end,'explicit_heading')))
                stack.append((level,chapter))
                if title in TERMS:
                    concept=key(u['id']+':term:'+str(start))
                    graph['concepts'].append(dict(id=concept,name=title,summary='',chapter_ids=[chapter],formal_knowledge_ids=[],
                        review_status='candidate',origins=origin(concept,start,end,'full_heading_term')))
            for match in re.finditer(r'(?m)^\s*(?:概念|定义|关键词)\s*[:：]\s*([^\n。；]{2,80})',raw):
                title=match[1].strip(); cid=key(u['id']+':explicit:'+str(match.start(1)))
                graph['concepts'].append(dict(id=cid,name=title,summary='',chapter_ids=[chapter] if chapter else [],formal_knowledge_ids=[],
                    review_status='candidate',origins=origin(cid,match.start(1),match.end(1),'explicit_concept_marker')))
            if not headings and not any(e['unit_id']==u['id'] for e in evidence.values()):
                unclassified.append(dict(document_id=doc['id'],unit_id=u['id'],location=location,reason='no_reliable_heading_or_term'))
            if len(graph['chapters'])>100 or len(graph['concepts'])>150: reject('候选内容超过限额，请减少选中资料，不会静默截断')
    return dict(graph=graph,evidence=list(evidence.values()),unclassified=unclassified,rule_version=RULE_VERSION)
