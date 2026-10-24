"""Create disposable browser acceptance data; never seed the production database."""
import json
import shutil
import sys
from pathlib import Path
from uuid import uuid4
from eduagent.domain.catalog import Catalog
from eduagent.storage.sqlite import SQLiteRepository
from eduagent.services.learning import LearningService
from eduagent.services.documents import DocumentsService
from eduagent.services.personal_bank import PersonalBankService
from eduagent.services.question_intake import auto_entry


def main():
    sys.path.insert(0,str(Path('backend/tests').resolve()))
    from test_documents import upload,tick
    from document_fixtures import pdf_bytes
    folder=Path('data/local').resolve()/('experience-browser-'+uuid4().hex[:8]);folder.mkdir()
    shutil.copytree('data',folder/'data',ignore=shutil.ignore_patterns('local','evaluation'))
    with SQLiteRepository(folder/'http.sqlite3') as repo:
        learning=LearningService(Catalog.load(folder/'data'),repo)
        learning.register('experience-browser',('gradient_descent',))
        docs=DocumentsService(repo,folder/'http.documents')
        doc,_=upload(docs,pdf_bytes(('Gradient descent follows negative gradients to reduce a differentiable loss.','','The learning rate controls the size of parameter updates.')),
                     name='gradient-example.pdf',student='experience-browser')
        tick(docs)
        bank=PersonalBankService(learning,folder/'data/materials')
        first=dict(question_type='single_choice',stem='梯度下降通常沿哪个方向更新参数？',options=[dict(key='A',text='负梯度方向'),dict(key='B',text='正梯度方向')],answer='A')
        second=dict(question_type='short_answer',stem='解释学习率 $\\eta$ 对更新步长的影响。',answer_text='学习率控制每一步的大小；过大可能振荡，过小可能缓慢。')
        for value in (first,second):auto_entry(bank,'experience-browser',value,{},None,'source_provided')
    result=dict(folder=str(folder),student='experience-browser',document_id=doc['id'],synthetic=True,model_enabled=False,production_writes=0)
    Path('data/local/learning-experience-browser.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result))


if __name__=='__main__':main()
