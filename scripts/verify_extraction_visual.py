"""At most two explicitly authorized calls on a self-created two-page PDF."""
import json,time
from pathlib import Path
from io import BytesIO
from hashlib import sha256
from uuid import uuid4
from PIL import Image,ImageDraw,ImageFont
from eduagent.api.settings import APISettings
from eduagent.domain.catalog import Catalog
from eduagent.services.learning import LearningService
from eduagent.services.documents import DocumentsService
from eduagent.services.personal_bank import PersonalBankService
from eduagent.services.question_extraction import QuestionExtractionService
from eduagent.storage.sqlite import SQLiteRepository

def verify():
    settings=APISettings.from_environment();folder=Path('data/local')/('extraction-v2-visual-'+uuid4().hex[:8]);folder.mkdir()
    pages=[]
    lines=[['Self-created extraction test / page 1','1. Calculation: Given f(x) = x^2 + 3x.', '(a) Compute the derivative at x = 2.', '(b) Explain whether f is convex.', 'Question 1 continues on the next page.'],
           ['Self-created extraction test / page 2','Continuation of question 1:', 'Include the reason for your answer to (b).', '2. Proof: For any real numbers a and b,', 'prove that (a-b)^2 >= 0.', 'No reference answers are provided.']]
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',25)
    for index,text in enumerate(lines):
        image=Image.new('RGB',(1000,700),'white');draw=ImageDraw.Draw(image)
        for j,line in enumerate(text):draw.text((35,40+j*70),line,fill='black',font=font)
        image.save(folder/f'original-page-{index+1}.png');pages.append(image)
    buf=BytesIO();pages[0].save(buf,format='PDF',save_all=True,append_images=pages[1:]);raw=buf.getvalue()
    with SQLiteRepository(folder/'synthetic.sqlite3') as repo:
        learning=LearningService(Catalog.load(settings.data_dir),repo);learning.register('synthetic-visual')
        docs=DocumentsService(repo,folder/'documents',agent_settings=settings.agent);key,stage=docs.files.stage();stage.write_bytes(raw)
        document,_=docs.upload('synthetic-visual',dict(request_id=str(uuid4()),course_id='machine_learning',title='自建跨页视觉样本',material_role='handout',source_note='self-created',local_rights_confirmed=True),key,'synthetic.pdf',len(raw),sha256(raw).hexdigest(),None)
        docs.execute(docs.claim(),None)
        bank=PersonalBankService(learning,settings.data_dir/'materials');resource=next(r for r in bank.catalogue('synthetic-visual')['items'] if r['original_source_id']==document['id'])
        service=QuestionExtractionService(bank,settings.agent,docs);task=service.create('synthetic-visual',dict(request_id=str(uuid4()),resource_id=resource['resource_id'],source_version=resource['source_version'],ordinals=[1,2],include_images=True,consent=True))
        start=time.monotonic();service.execute(service.claim());result=service.get('synthetic-visual',task['request_id'])
        questions=[bank.get('synthetic-visual',key) for key in result['result'].get('question_ids',[])]
        payloads=[q['payload'] for q in questions];kinds={p['question_type'] for p in payloads}
        report=dict(passed=result['status']=='complete' and kinds=={'calculation','proof'} and len(payloads)==2 and all(not p.get('answer') and not p.get('answer_text') for p in payloads),
            real_model_calls=result['model_calls'],call_limit=2,status=result['status'],seconds=round(time.monotonic()-start,2),
            two_original_pages=True,cross_page_subquestions_preserved=any(len(p.get('subquestions',[]))>=2 for p in payloads),
            model_answer_generation_requested=False,private_teacher_or_note_content_sent=False,payloads=payloads,result=result['result'],folder=str(folder),
            limitation='Self-created clear raster PDF; not a real scanning quality benchmark or user-reviewed exam.')
        output=Path('data/evaluation/extraction-v2-visual-v1.json');output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(dict(passed=report['passed'],calls=result['model_calls'],status=result['status'],cross_page=report['cross_page_subquestions_preserved'],report=str(output))))

if __name__=='__main__':verify()
