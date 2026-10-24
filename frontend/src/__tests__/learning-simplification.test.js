import { afterEach, describe, expect, it, vi } from 'vitest'
import { effectScope, reactive, ref } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import App from '../App.vue'
import StudyWorkbench from '../components/StudyWorkbench.vue'
import QuestionImportPanel from '../components/QuestionImportPanel.vue'
import PracticeHub from '../views/PracticeHub.vue'
import MarkdownRenderer from '../components/MarkdownRenderer.vue'
import DocumentPageRecognition from '../components/DocumentPageRecognition.vue'
import {useStudyWorkbench} from '../useStudyWorkbench.js'
import {usePersonalBank} from '../usePersonalBank.js'
import {client as learningClient,memoryStore,state} from './fixtures.js'

const scopes=[],wrappers=[]
afterEach(()=>{wrappers.splice(0).forEach(w=>w.unmount());scopes.splice(0).forEach(s=>s.stop())})
const storage=()=>{const data=new Map();return{getItem:k=>data.get(k)||null,setItem:(k,v)=>data.set(k,v)}}
const course={source_type:'course_material',source_id:'gradient',source_version:'c1',title:'课程资料',index_status:'ready'}
const doc={source_type:'uploaded_document',source_id:'doc-a',source_version:'d1',title:'上传的教师课件',index_status:'ready',readable_units:1,total_units:3}
function readingApi(){return{...learningClient(),knowledgeSources:vi.fn(async()=>({items:[course,doc,{...doc,source_type:'personal_note',source_id:'private',title:'个人笔记'}]})),
  workbenchRuns:vi.fn(async()=>[]),workbenchCapabilities:vi.fn(async()=>({model_enabled:true,provider:'DeepSeek',model:'synthetic'})),
  workbenchAsk:vi.fn(async(_,body)=>({request_id:body.request_id,status:'local'})),workbenchRun:vi.fn(),teachingExplain:vi.fn(async()=>({request_id:'bound',status:'local'}))}}
function setupReading(api=readingApi(),lesson=null){const scope=effectScope();scopes.push(scope);const owner=ref('a');return{api,owner,w:scope.run(()=>reactive(useStudyWorkbench(api,owner,storage(),lesson)))}}
function bankApi(){
  const resource={resource_id:'resource-1',original_source_type:'document',original_source_id:'doc-a',source_version:'v1',status:'active',title:'合成试卷',format:'pdf'}
  const row={id:'q1',revision:1,payload:{stem:'说明梯度下降的更新方向。',question_type:'short_answer',options:[],concepts:[]},status:'practice',source:{},source_status:'current',review:{automation:{admitted:true}},duplicate_ids:[]}
  let tasks=[]
  return{bank:vi.fn(async(_,path,method='GET',body)=>{
    if(path==='course-resources')return{items:[resource],knowledge:[]}
    if(path==='course-resources/resource-1')return{resource,units:[1,2,3].map(ordinal=>({id:'u'+ordinal,ordinal,text:'原文',location:{page_number:ordinal}})),run_id:'run-1'}
    if(path.startsWith('documents/'))return[]
    if(path.startsWith('personal-bank/questions?'))return{items:[row]}
    if(path==='personal-bank/questions/q1')return row
    if(path==='personal-bank/practice')return{items:[]}
    if(path==='personal-bank/extraction-capabilities')return{enabled:true}
    if(path==='personal-bank/extraction-tasks' && method==='POST'){tasks=[{request_id:body.request_id,status:'running',source:{title:'合成试卷'},result:{}}];return tasks[0]}
    if(path==='personal-bank/extraction-tasks')return{items:tasks}
    if(path==='personal-bank/extractions')return{question_ids:['q1'],intake:{ready:1,needs_attention:0,duplicate:0}}
    if(path==='personal-bank/organize')return{processed:1,ready:1,needs_attention:0}
    throw Error(method+' '+path)
  })}
}
function setupBank(){const scope=effectScope();scopes.push(scope);const api=bankApi(),owner=ref('a');return{api,owner,w:scope.run(()=>reactive(usePersonalBank(api,owner,storage())))}}

describe('simplified learning flows',()=>{
  it('has three primary entries and starts in source learning without automatic allocation',async()=>{
    const api=readingApi();const v=mount(App,{props:{client:api,store:memoryStore({student_id:'learner-test'})}});wrappers.push(v);await flushPromises()
    expect(v.findAll('nav[aria-label="学习导航"] button').map(b=>b.text())).toEqual(['资料学习','练习','学习进度'])
    expect(v.find('.study-workbench').exists()).toBe(true)
    expect(v.get('.workspace-management').attributes('open')).toBeUndefined()
    expect(v.get('.more-tools').attributes('open')).toBeUndefined()
    expect(api.next).not.toHaveBeenCalled();expect(api.submit).not.toHaveBeenCalled();expect(api.workbenchAsk).not.toHaveBeenCalled()
  })
  it('onboarding into source learning does not silently allocate a formal question',async()=>{
    const api=readingApi();const v=mount(App,{props:{client:api,store:memoryStore()}});wrappers.push(v);await flushPromises()
    await v.get('#learner-id').setValue('learner-test');await v.get('.start-form').trigger('submit');await flushPromises()
    expect(api.start).toHaveBeenCalled();expect(api.next).not.toHaveBeenCalled();expect(v.find('.study-workbench').exists()).toBe(true)
  })
  it('includes parsed uploads independently of releases and excludes default personal notes',async()=>{
    const {w}=setupReading(undefined,{scope:()=>[course],session:()=>({id:'session'})});await w.load()
    expect(w.sources).toHaveLength(3);expect(w.chosen.map(s=>s.source_type)).toEqual(['course_material','uploaded_document'])
    expect(w.teachers).toHaveLength(1)
  })
  it('sends upload questions through the independent endpoint, with per-round permission',async()=>{
    const {w,api}=setupReading(undefined,{scope:()=>[course],session:()=>({id:'session'})});await w.load();w.query='解释梯度下降';w.teacherConsent=true;await w.ask()
    expect(api.workbenchAsk).toHaveBeenCalledTimes(1);expect(api.teachingExplain).not.toHaveBeenCalled()
    expect(api.workbenchAsk.mock.calls[0][1].allow_teacher_external).toBe(true);expect(w.teacherConsent).toBe(false)
    await w.ask();expect(api.workbenchAsk.mock.calls[1][1].allow_teacher_external).toBe(false)
  })
  it('retains the release bound teaching endpoint for its exact permitted sources',async()=>{
    const {w,api}=setupReading(undefined,{scope:()=>[course],session:()=>({id:'session'})});await w.load();w.toggle(doc,false);w.query='解释梯度下降';await w.ask()
    expect(api.teachingExplain).toHaveBeenCalledTimes(1);expect(api.workbenchAsk).not.toHaveBeenCalled()
  })
  it('shows parsed coverage, a compact Studio, source search and numbered citations',async()=>{
    const {w,api}=setupReading();await w.load()
    const v=mount(StudyWorkbench,{props:{workspace:w,snapshot:state(),goalNames:'机器学习'}});wrappers.push(v);await flushPromises()
    expect(v.text()).toContain('可问 1 / 3');expect(v.find('.self-panel').exists()).toBe(false);expect(v.find('.study-guide-panel').exists()).toBe(false)
    expect(v.get('.answer-settings').attributes('open')).toBeUndefined()
    await v.get('#wb-source-search').setValue('上传的');expect(v.findAll('.wb-source-list li')).toHaveLength(1)
    api.openSource=vi.fn(async()=>({...doc,document_id:'doc-a',version_id:'v1',raw_md:'已保存原文'}));await w.open(doc)
    expect(w.drawer.original_file_url).toContain('/documents/doc-a/original?version_id=v1')
    const md=mount(MarkdownRenderer,{props:{source:'原文 [doc_abc:1]',citationIds:['doc_abc:1'],numberCitations:true}});wrappers.push(md)
    expect(md.get('a').text()).toBe('[1]');await md.get('a').trigger('click');expect(md.emitted('citation')[0]).toEqual(['doc_abc:1'])
  })
  it('imports pasted questions only on explicit consent and uses automatic ordinary admission',async()=>{
    const {w,api}=setupBank();const v=mount(QuestionImportPanel,{props:{workspace:w,documents:{supported:false}}});wrappers.push(v);await flushPromises()
    await v.get('textarea').setValue('1. 简答：说明梯度下降。')
    await v.get('form').trigger('submit');expect(api.bank.mock.calls.filter(c=>c[2]==='POST')).toHaveLength(0)
    await v.get('input[type=checkbox]').setValue(true);await v.get('form').trigger('submit');await flushPromises()
    const sent=api.bank.mock.calls.find(c=>c[2]==='POST');expect(sent[1]).toBe('personal-bank/extraction-tasks')
    expect(sent[3]).toMatchObject({auto_import:true,consent:true,include_images:false,text:'1. 简答：说明梯度下降。'})
    await w.loadTasks();await w.loadTasks();expect(api.bank.mock.calls.filter(c=>c[2]==='POST')).toHaveLength(1)
  })
  it('uploads then identifies only the selected pages and consumes consent once',async()=>{
    const {w,api}=setupBank()
    const documents=reactive({supported:true,rights:false,file:null,title:'',load:vi.fn(),current:null,upload:vi.fn(async()=>{documents.current={id:'doc-a',version:{id:'v1'},parse:{status:'ready'}};return true})})
    const v=mount(QuestionImportPanel,{props:{workspace:w,documents}});wrappers.push(v);await flushPromises()
    const input=v.get('input[type=file]');Object.defineProperty(input.element,'files',{value:[new File(['synthetic'],'试卷.pdf')],configurable:true});await input.trigger('change')
    const checks=v.findAll('input[type=checkbox]');await checks[0].setValue(true)
    await v.findAll('input:not([type])')[0].setValue('2,3')
    await checks.at(-1).setValue(true)
    await v.get('form').trigger('submit');await flushPromises()
    expect(documents.upload).toHaveBeenCalledTimes(1)
    const sent=api.bank.mock.calls.find(c=>c[2]==='POST');expect(sent[3]).toMatchObject({auto_import:true,resource_id:'resource-1',source_version:'v1',ordinals:[2,3],include_images:true})
    expect(checks.at(-1).element.checked).toBe(false)
  })
  it('refuses nonadjacent or oversized page selections before sending any content',async()=>{
    const {w,api}=setupBank();const v=mount(QuestionImportPanel,{props:{workspace:w,documents:{supported:false}}});wrappers.push(v);await flushPromises()
    await v.get('select').setValue('existing');await v.findAll('select')[1].setValue('resource-1');await v.findAll('input:not([type])')[0].setValue('1,3')
    await v.findAll('input[type=checkbox]').at(-1).setValue(true);await v.get('form').trigger('submit');await flushPromises()
    expect(v.get('[role=alert]').text()).toContain('相邻页');expect(api.bank.mock.calls.filter(c=>c[2]==='POST')).toHaveLength(0)
  })
  it('local extraction can auto-admit without any external consent',async()=>{
    const {w,api}=setupBank();await w.load();w.extractionMode='local';w.autoImport=true;w.paste='1. 简答：说明梯度下降。';await w.extractText()
    expect(api.bank.mock.calls.find(c=>c[2]==='POST')[3].auto_import).toBe(true)
    expect(api.bank.mock.calls.some(c=>c[1]==='personal-bank/extraction-tasks')).toBe(false)
  })
  it('offers ready questions and isolates exceptions from the main practice action',async()=>{
    const {w}=setupBank();w.filter.status='draft';w.filter.q='管理端筛选';const v=mount(PracticeHub,{props:{workspace:w}});wrappers.push(v);await flushPromises()
    expect(w.filter.status).toBe('');expect(w.filter.q).toBe('')
    expect(v.text()).toContain('1 道可练习题');expect(v.findAll('details').map(d=>d.attributes('open'))).toEqual([undefined,undefined])
    expect(v.text()).toContain('自动整理 · 未人工核验')
  })
  it('page recognition is explicit, independent and never starts on opening',async()=>{
    const workspace=reactive({pages:'11,12',consent:true,busy:'',current:{id:'doc-a',version:{id:'v1'},revision:1},runs:[],run:{id:'vision-1'},capabilities:{vision_enabled:true},select:vi.fn(),vision:vi.fn(async()=>true)})
    const v=mount(DocumentPageRecognition,{props:{workspace,source:{...doc,version_id:'v1',source_revision:1}}});wrappers.push(v);await flushPromises()
    expect(workspace.consent).toBe(false);expect(workspace.pages).toBe('');expect(workspace.vision).not.toHaveBeenCalled()
    await v.get('input:not([type])').setValue('11,12');await v.get('input[type=checkbox]').setValue(true)
    await v.findAll('button').find(b=>b.text()==='识别选定页面').trigger('click');await flushPromises()
    expect(workspace.vision).toHaveBeenCalledTimes(1)
  })
  it('refuses recognition when the displayed source version no longer matches the file',async()=>{
    const workspace=reactive({pages:'',consent:false,busy:'',current:{id:'doc-a',version:{id:'new-file'},revision:2},runs:[],capabilities:{vision_enabled:true},select:vi.fn(),vision:vi.fn()})
    const v=mount(DocumentPageRecognition,{props:{workspace,source:{...doc,version_id:'old-file',source_revision:1}}});wrappers.push(v);await flushPromises()
    await v.get('input:not([type])').setValue('1');await v.get('input[type=checkbox]').setValue(true)
    await v.findAll('button').find(b=>b.text()==='识别选定页面').trigger('click');await flushPromises()
    expect(workspace.vision).not.toHaveBeenCalled();expect(v.get('[role=alert]').text()).toContain('版本已经变化')
  })
})
