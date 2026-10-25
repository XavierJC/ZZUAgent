import { afterEach, describe, expect, it, vi } from 'vitest'
import { effectScope, reactive, ref } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { courseSpaceKey } from '../app/courseSpace.js'
import AppSidebar from '../app/AppSidebar.vue'
import CourseWelcome from '../app/CourseWelcome.vue'
import FormalLearningPage from '../features/learning/FormalLearningPage.vue'
import NotebookPage from '../features/notebooks/NotebookPage.vue'
import NotebooksPage from '../features/notebooks/NotebooksPage.vue'
import QuickDocumentUpload from '../components/QuickDocumentUpload.vue'
import { useNotebooks } from '../features/notebooks/useNotebooks.js'
import { useWorkspace } from '../features/learning/useWorkspace.js'
import { assignment, client, memoryStore, points, state } from './fixtures.js'

const cleanup=[]
afterEach(()=>{cleanup.splice(0).reverse().forEach(fn=>fn());localStorage.clear()})
const copy=value=>JSON.parse(JSON.stringify(value))
function render(component,space,props={}){
  const ui=mount(component,{props,global:{provide:{[courseSpaceKey]:space}}})
  cleanup.push(()=>ui.unmount());return ui
}
function formalSpace(){
  const w=reactive({student:'learner-test',snapshot:state(),knowledge:points,decision:null,feedback:null,pending:null,
    selected:'',busy:'',error:'',activeTopic:'线性回归与损失函数',topicName:id=>points.find(p=>p.id===id)?.name || id,submit:vi.fn()})
  const flow=reactive({enabled:true,session:null,busy:'',pending:null,error:'',notice:'',selectedRelease:'demo',
    releases:[{id:'demo',title:'机器学习',release_version:1,usable:true}],data:{next_task:{action:'diagnose',reason:'先回答一道题。'},assessment_bank:{question_count:40,shared_count:40,personal_count:0}},
    load:vi.fn(async()=>{}),begin:vi.fn(async()=>{flow.session={id:'s1'};return true}),allocate:vi.fn(async()=>{w.decision=assignment();return true}),submit:vi.fn(),retryPending:vi.fn(),releasePending:vi.fn()})
  return reactive({modern:true,w,flow,goalsText:'逻辑回归',features:{review:{enabled:false,active:false}},navigate:vi.fn(),explainNext:vi.fn()})
}

const course={source_type:'course_material',source_id:'course',source_version:'v1',title:'课程资料',index_status:'ready',current_status:'current'}
const uploaded={...course,source_type:'uploaded_document',source_id:'uploaded',title:'新上传资料'}
const privateNote={...course,source_type:'personal_note',source_id:'private',title:'自己的笔记'}
function notebookSetup(){
  const sourceList=[course,uploaded,privateNote],owner=ref('learner-test')
  const book=id=>({id,title:id,description:'',revision:1,archived:0,sources:[],item_count:0,conversation_count:0,updated_at:'2026-10-25T00:00:00Z'})
  const data=new Map([['book-a',book('book-a')],['book-b',book('book-b')]])
  const api={notebooks:vi.fn(async()=>({items:[...data.values()].map(copy)})),notebook:vi.fn(async(_s,id)=>copy(data.get(id))),
    notebookReceipt:vi.fn(),createNotebook:vi.fn(async(_s,body)=>{data.set(body.id,{...book(body.id),title:body.title});return{id:body.id,revision:1}}),
    notebookSources:vi.fn(async(_s,id,body)=>{const entry=data.get(id);entry.sources=body.sources.map(ref=>({...sourceList.find(s=>s.source_type===ref.source_type && s.source_id===ref.source_id),...ref}));entry.revision++;return{id,revision:entry.revision}}),
    knowledgeSources:vi.fn(async()=>({items:copy(sourceList)})),workbenchCapabilities:vi.fn(async()=>({model_enabled:true,provider:'mock'})),notebookRuns:vi.fn(async()=>[]),notebookAsk:vi.fn(),bank:vi.fn(async()=>({items:[],knowledge:[]}))}
  const scope=effectScope();cleanup.push(()=>scope.stop())
  const books=scope.run(()=>reactive(useNotebooks(api,owner)))
  const space=reactive({modern:true,features:{notebooks:books,documents:{supported:false}},route:{params:{book:'book-a'}},w:{student:'learner-test',knowledge:points},client:api,registry:{peek:()=>null},navigate:vi.fn(),replaceRoute:vi.fn()})
  return{owner,api,books,space,data}
}

describe('human learning workflow',()=>{
  it('has three everyday destinations and puts diagnosis inside practice',()=>{
    const space={tab:'learn',isBuilder:false,w:{active:true}}
    const ui=mount(AppSidebar,{props:{space}});cleanup.push(()=>ui.unmount())
    expect(ui.findAll('nav[aria-label="学习导航"] button').map(b=>b.text())).toEqual(['学习','练习','进度'])
    expect(ui.get('nav[aria-label="学习导航"] [aria-current=page]').text()).toBe('练习')
    expect(ui.get('.product-management').attributes('open')).toBeUndefined()
  })
  it('lets a new learner start with a generated nickname and no mandatory settings',async()=>{
    const space=reactive({modern:true,tab:'notebooks',formMode:'new',learnerId:'learner-generated',goals:[],w:{knowledge:points,health:{},busy:''},start:vi.fn()})
    const ui=mount(CourseWelcome,{props:{space}});cleanup.push(()=>ui.unmount())
    expect(ui.get('.welcome-options').attributes('open')).toBeUndefined()
    await ui.get('form').trigger('submit');expect(space.start).toHaveBeenCalledOnce()
    expect(space.learnerId).toBe('learner-generated')
  })
  it('reads diagnosis on mount and binds plus allocates only after one explicit click',async()=>{
    const space=formalSpace(),ui=render(FormalLearningPage,space);await flushPromises()
    expect(space.flow.begin).not.toHaveBeenCalled();expect(space.flow.allocate).not.toHaveBeenCalled()
    await ui.get('.diagnosis-start .product-primary').trigger('click');await flushPromises()
    expect(space.flow.begin).toHaveBeenCalledOnce();expect(space.flow.allocate).toHaveBeenCalledOnce()
    expect(ui.find('.question-panel input[value="B"]').exists()).toBe(true)
  })
  it('does not allocate after the learner changes during session creation',async()=>{
    const space=formalSpace();let release
    space.flow.begin=vi.fn(()=>new Promise(resolve=>{release=resolve}))
    const ui=render(FormalLearningPage,space);await flushPromises()
    await ui.get('.diagnosis-start .product-primary').trigger('click')
    space.w.student='someone-else';release(true);await flushPromises()
    expect(space.flow.allocate).not.toHaveBeenCalled()
  })
  it('does not allocate if the learner leaves while the session is being created',async()=>{
    const space=formalSpace();let release
    space.flow.begin=vi.fn(()=>new Promise(resolve=>{release=resolve}))
    const ui=render(FormalLearningPage,space);await flushPromises()
    await ui.get('.diagnosis-start .product-primary').trigger('click');ui.unmount();release(true);await flushPromises()
    expect(space.flow.allocate).not.toHaveBeenCalled()
  })
  it('keeps retry available for an uncertain legacy answer',async()=>{
    const space=formalSpace();space.w.decision=assignment();space.w.pending={decision_id:'decision-0',answer:'B'}
    const ui=render(FormalLearningPage,space);await flushPromises()
    expect(ui.get('.question-actions button').attributes('disabled')).toBeUndefined()
    await ui.get('.question-panel form').trigger('submit');expect(space.w.submit).toHaveBeenCalledOnce()
    expect(space.flow.allocate).not.toHaveBeenCalled()
  })
  it('creates a theme without requiring a name or description',async()=>{
    const{space,api}=notebookSetup();space.route.params={}
    const ui=render(NotebooksPage,space);await flushPromises()
    await ui.findAll('button').find(b=>b.text()==='新建笔记本').trigger('click')
    await ui.get('.product-dialog form').trigger('submit');await flushPromises()
    expect(api.createNotebook).toHaveBeenCalledWith('learner-test',expect.objectContaining({title:'新的学习主题',description:''}))
    expect(api.notebookAsk).not.toHaveBeenCalled()
  })
  it('offers a single clear first-theme action instead of repeated empty create panels',async()=>{
    const{space,data}=notebookSetup();data.clear();space.route.params={}
    const ui=render(NotebooksPage,space);await flushPromises()
    expect(ui.findAll('button').filter(b=>b.text()==='开始我的第一个主题')).toHaveLength(1)
    expect(ui.findAll('button').filter(b=>b.text()==='新建笔记本')).toHaveLength(0)
    expect(ui.find('.notebook-create-card').exists()).toBe(false)
  })
  it('adds one selected source immediately without a second save or broader selection',async()=>{
    const{space,api,data,books}=notebookSetup(),ui=render(NotebookPage,space);await flushPromises()
    await ui.get('[aria-label="管理笔记本资料"]').trigger('click');await flushPromises()
    const row=ui.findAll('.notebook-picker-row').find(r=>r.text().includes('新上传资料'))
    await row.get('button').trigger('click');await flushPromises()
    expect(api.notebookSources).toHaveBeenCalledTimes(1)
    expect(data.get('book-a').sources.map(s=>s.source_id)).toEqual(['uploaded'])
    expect(books.current.chat.chosen.map(s=>s.source_id)).toEqual(['uploaded'])
    expect(books.current.chat.teacherConsent).toBe(false)
    expect(ui.find('[role=dialog]').exists()).toBe(false)
    expect(data.get('book-b').sources).toHaveLength(0)
    expect(api.notebookAsk).not.toHaveBeenCalled()
  })
  it('adds a successful upload to its current theme automatically, without sending a question',async()=>{
    const{space,api,data,books}=notebookSetup()
    const docs=reactive({supported:true,busy:'',pending:null,activeJobs:false,file:null,title:'',rights:false,items:[],current:null,load:vi.fn(async()=>{}),upload:vi.fn(async()=>{docs.current={id:'uploaded'};docs.items=[{id:'uploaded',parse:{status:'ready'}}];return true})})
    space.features.documents=docs
    const ui=render(NotebookPage,space);await flushPromises()
    await ui.get('[aria-label="管理笔记本资料"]').trigger('click');await flushPromises()
    const file=ui.get('input[type=file]');Object.defineProperty(file.element,'files',{value:[new File(['synthetic'],'课件.txt')],configurable:true});await file.trigger('change')
    await ui.get('.quick-upload input[type=checkbox]').setValue(true)
    await ui.get('.quick-upload form').trigger('submit');await flushPromises()
    expect(docs.upload).toHaveBeenCalledOnce();expect(api.notebookSources).toHaveBeenCalledTimes(1)
    expect(data.get('book-a').sources.map(s=>s.source_id)).toEqual(['uploaded'])
    expect(books.current.chat.chosen.map(s=>s.source_id)).toEqual(['uploaded'])
    expect(books.current.chat.teacherConsent).toBe(false)
    expect(ui.find('[role=dialog]').exists()).toBe(false)
    expect(api.notebookAsk).not.toHaveBeenCalled()
  })
  it('keeps an added personal note unchecked and does not grant external permission',async()=>{
    const{space,books}=notebookSetup(),ui=render(NotebookPage,space);await flushPromises()
    await ui.get('[aria-label="管理笔记本资料"]').trigger('click');await flushPromises()
    await ui.findAll('.notebook-picker-row').find(r=>r.text().includes('自己的笔记')).get('button').trigger('click');await flushPromises()
    expect(books.current.detail.sources.map(s=>s.source_id)).toEqual(['private'])
    expect(books.current.chat.chosen).toHaveLength(0)
    expect(books.current.chat.consent).toBe(false)
  })
  it('does not attach a file that failed parsing',async()=>{
    const docs=reactive({busy:'',pending:null,activeJobs:false,file:null,title:'',rights:true,items:[],current:null,load:vi.fn(async()=>{}),upload:vi.fn(async()=>{docs.current={id:'bad'};docs.items=[{id:'bad',parse:{status:'failed'}}];return true})})
    const ui=mount(QuickDocumentUpload,{props:{workspace:docs}});cleanup.push(()=>ui.unmount());await flushPromises()
    await ui.get('button').trigger('click');docs.file=new File(['x'],'bad.pdf');await ui.get('form').trigger('submit');await flushPromises()
    expect(ui.emitted('ready')).toBeUndefined();expect(docs.notice).toContain('暂时没有可用正文')
  })
  it('deletes a failed upload in the picker and reloads the catalog without asking or re-parsing',async()=>{
    const{space,api}=notebookSetup()
    const failed={...uploaded,index_status:'failed',source_revision:4}
    let deleted=false
    api.knowledgeSources.mockImplementation(async()=>({items:deleted?[course]:[course,failed]}))
    const docs=reactive({supported:false,busy:'',pending:null,error:'',removeById:vi.fn(async(id,revision)=>{expect(id).toBe('uploaded');expect(revision).toBe(4);deleted=true;return true})})
    space.features.documents=docs
    const ui=render(NotebookPage,space);await flushPromises()
    await ui.get('[aria-label="管理笔记本资料"]').trigger('click');await flushPromises()
    await ui.get('[aria-label="删除资料：新上传资料"]').trigger('click')
    expect(docs.removeById).not.toHaveBeenCalled()
    await ui.get('[aria-label="确认删除资料：新上传资料"]').trigger('click');await flushPromises()
    expect(docs.removeById).toHaveBeenCalledOnce();expect(ui.text()).not.toContain('新上传资料')
    expect(api.notebookSources).not.toHaveBeenCalled();expect(api.notebookAsk).not.toHaveBeenCalled()
  })
  it('does not pull a reader back when an attachment finishes in the previous theme',async()=>{
    const{books,api}=notebookSetup();await books.open('book-a')
    const original=api.notebookSources.getMockImplementation();let release
    const gate=new Promise(resolve=>{release=resolve})
    api.notebookSources.mockImplementation(async(...args)=>{await gate;return original(...args)})
    const saving=books.attach(uploaded)
    await books.open('book-b');release();await saving
    expect(books.current.detail.id).toBe('book-b')
    expect(api.notebookAsk).not.toHaveBeenCalled()
  })
  it('keeps an unsent diagnostic choice on read-only refresh, and clears it for a different question',async()=>{
    const api=client(),scope=effectScope();cleanup.push(()=>scope.stop())
    const w=scope.run(()=>reactive(useWorkspace(api,memoryStore({student_id:'learner-test'}))))
    await w.boot();w.selected='B';await w.refresh();expect(w.selected).toBe('B')
    api.currentDecision.mockResolvedValue(assignment(1));await w.refresh();expect(w.selected).toBe('')
    expect(api.next).not.toHaveBeenCalled();expect(api.submit).not.toHaveBeenCalled()
  })
})
