"""Small fixed real-course coverage audit, separate from the original course eval.

Local only. Uses a database copy and reads existing authorized original files.
It reports misses; it does not tune retrieval to these questions.
"""
import json,sqlite3
from pathlib import Path
from datetime import datetime,timezone
from uuid import uuid4
from eduagent.api.settings import APISettings
from eduagent.domain.catalog import Catalog
from eduagent.services.learning import LearningService
from eduagent.services.knowledge import KnowledgeService
from eduagent.storage.sqlite import SQLiteRepository

CASES=[('偏差和方差有什么区别',[20]),('训练误差低而验证误差高说明什么',[20]),
       ('增加训练数据主要降低偏差还是方差',[20]),('正则化对偏差和方差有什么影响',[20]),
       ('解释泛化误差的偏差方差分解',[20]),('什么是查准率和查全率',[11,12]),
       ('暗物质的宇宙学证据有哪些',[]),('今天北京的天气怎么样',[])]

def main():
    settings=APISettings.from_environment();folder=Path('data/local')/('real-reading-'+uuid4().hex[:8]);folder.mkdir();target=folder/'audit.sqlite3'
    with sqlite3.connect(settings.db_path) as a,sqlite3.connect(target) as b:a.backup(b)
    with SQLiteRepository(target) as repo:
        repo.document_root=settings.document_dir
        learning=LearningService(Catalog.load(settings.data_dir),repo)
        row=repo.connection.execute("SELECT id,title FROM course_documents WHERE student_id=? AND title LIKE ? AND deleted_at IS NULL ORDER BY created_at LIMIT 1",('pilot-model-evaluation','%第2讲%')).fetchone()
        if not row:raise ValueError('本机没有此前试点教师资料，不能冒称完成真实内容评估')
        service=KnowledgeService(learning.catalog,repo);source=service.documents.source('pilot-model-evaluation',row['id'])
        ref={k:source[k] for k in ('source_type','source_id','source_version')};cases=[]
        for query,expected in CASES:
            result=service.search('pilot-model-evaluation',query,[ref])
            pages=sorted(set(p['page_number'] for p in result['items']))
            success=bool(set(pages)&set(expected)) if expected else not pages
            cases.append(dict(query=query,expected_pages=expected,returned_pages=pages,passed=success,model_calls=0))
        positives=[c for c in cases if c['expected_pages']];outside=[c for c in cases if not c['expected_pages']]
        report=dict(verified_at=datetime.now(timezone.utc).isoformat(),course_document_title=row['title'],
                    source_type='uploaded_document',review_status='document_unverified',readable_units=source['readable_units'],total_units=source['total_units'],
                    cases=cases,positive_hits=sum(c['passed'] for c in positives),positive_total=len(positives),
                    outside_false_positives=sum(not c['passed'] for c in outside),outside_total=len(outside),
                    real_model_calls=0,production_writes=0,method='fixed local lexical retrieval/coverage audit; no teaching-effect claim',
                    original_course_55_and_outside_15='unchanged; reported separately',directory=str(folder))
    Path('data/evaluation/uploaded-real-course-reading-v1.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('readable_units','total_units','positive_hits','positive_total','outside_false_positives','outside_total','real_model_calls')}))

if __name__=='__main__':main()
