"""Explicit authorized real DeepSeek smoke on self-created data only."""
import argparse,json,time,sqlite3,sys
from pathlib import Path
from datetime import datetime,timezone
from uuid import uuid4
from eduagent.api.settings import APISettings
from eduagent.domain.catalog import Catalog
from eduagent.services.learning import LearningService
from eduagent.services.personal_bank import PersonalBankService
from eduagent.services.question_extraction import QuestionExtractionService
from eduagent.storage.sqlite import SQLiteRepository
from eduagent.documents.question_extraction import extract

def score(entries,samples):
    rows=[];seen={}
    for entry in entries:
        p=entry['payload'];seen.setdefault(p.get('number',''),[]).append(p)
    for s in samples:
        key=str(int(s['id'][1:]));matches=seen.get(key,[]);p=matches[0] if len(matches)==1 else None;r=s['reference']
        rendered=json.dumps(p,ensure_ascii=False) if p else ''
        normalize=lambda t:''.join(c for c in t.casefold() if c.isalnum())
        actual=(p.get('answer') or p.get('answer_keys') or p.get('answer_text') or None) if p else None
        if p and p['question_type']=='true_false':actual={'错误':'false','错':'false','正确':'true','对':'true'}.get(actual,actual)
        rows.append(dict(id=s['id'],boundary=len(matches)==1,type=bool(p and p['question_type']==r['question_type']),
          required_content=bool(p and all(normalize(a) in normalize(rendered) for a in r['essential'])),
          options=bool(p and (len(p['options'])==r['options'] or p['question_type']=='true_false' and r['options']==0)),answer=bool(p and actual==r['answer']),
          subquestions=bool(p and len(p.get('subquestions',[]))>=r['subquestions']),
          dependency=bool(p and (not r['dependencies'] or p.get('dependencies'))),
          expected_type=r['question_type'],actual_type=p['question_type'] if p else None))
    return dict(denominator=len(samples),returned=len(entries),criteria={k:sum(r[k] for r in rows) for k in ('boundary','type','required_content','options','answer','subquestions','dependency')},cases=rows)

def verify(output,limit=4,visual=False):
    samples=json.loads(Path('data/evaluation/question-extraction-samples-v2.json').read_text(encoding='utf-8'))['samples']
    settings=APISettings.from_environment();assert settings.agent.enabled
    folder=Path('data/local')/('extraction-v2-model-'+uuid4().hex[:8]);folder.mkdir()
    calls=0;batches=[];all_entries=[]
    with SQLiteRepository(folder/'synthetic.sqlite3') as repo:
        learning=LearningService(Catalog.load(settings.data_dir),repo);learning.register('synthetic-quality')
        bank=PersonalBankService(learning,settings.data_dir/'materials');s=QuestionExtractionService(bank,settings.agent)
        for part in (samples[:12],samples[12:]):
            if calls+2>limit:break
            raw='\n\n'.join(v['raw'] for v in part)
            task=s.create('synthetic-quality',dict(request_id=str(uuid4()),text=raw,consent=True,title='自建识别验收样本'))
            start=time.monotonic();s.execute(s.claim());result=s.get('synthetic-quality',task['request_id']);calls+=result['model_calls']
            entries=[bank.get('synthetic-quality',key) for key in result['result'].get('question_ids',[])]
            all_entries.extend(entries)
            batches.append(dict(status=result['status'],model_calls=result['model_calls'],seconds=round(time.monotonic()-start,2),result=result['result'],quality=score(entries,part)))
    # Retain the old code and evaluate both versions over the exact same inputs.
    from zipfile import ZipFile
    pointer=json.loads(Path('data/local/extraction-v2-current.json').read_text())
    with ZipFile(Path(pointer['folder'])/'code-before.zip') as z:code=z.read('backend/src/eduagent/documents/question_extraction.py').decode('utf-8')
    module={};exec(compile(code,'legacy_extraction_v1','exec'),module)
    raw='\n\n'.join(v['raw'] for v in samples);old,_=module['extract']([dict(text=raw)]);local,_=extract([dict(text=raw)])
    report=dict(verified_at=datetime.now(timezone.utc).isoformat(),real_model_calls=calls,call_limit=limit,model=settings.agent.model,
        sent_real_personal_or_teacher_content=False,source='self-created engineering reference; not independently user-reviewed',
        legacy=score(old,samples),local_v2=score(local,samples),semantic=score(all_entries,samples),batches=batches,
        teaching_effectiveness_evaluated=False,raw_model_output_logged=False,folder=str(folder))
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(report=str(output),calls=calls,statuses=[b['status'] for b in batches],semantic=report['semantic']['criteria'],denominator=24)))
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=Path('data/evaluation/extraction-v2-model-v1.json'));p.add_argument('--limit',type=int,default=4);a=p.parse_args();verify(a.output,a.limit)
