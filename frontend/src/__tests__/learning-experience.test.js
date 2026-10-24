import { afterEach, describe, expect, it, vi } from 'vitest'
import { effectScope, reactive, ref } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import StudyWorkbench from '../components/StudyWorkbench.vue'
import SourceDrawer from '../components/SourceDrawer.vue'
import PracticeHub from '../views/PracticeHub.vue'
import LearningInsights from '../views/LearningInsights.vue'
import { useStudyWorkbench } from '../useStudyWorkbench.js'
import { practiceCandidates } from '../features/learning/journey.js'
import { guidance } from './study-guidance-fixtures.js'

const scopes=[],wrappers=[]
afterEach(()=>{wrappers.splice(0).forEach(w=>w.unmount());scopes.splice(0).forEach(s=>s.stop())})
const source={source_type:'uploaded_document',source_id:'doc1',source_version:'v1',title:'合成课件',index_status:'ready',readable_units:1,total_units:2}
function setup(){
  const data=new Map(),store={getItem:k=>data.get(k)||null,setItem:(k,v)=>data.set(k,v)}
  const api={knowledgeSources:vi.fn(async()=>({items:[source]})),workbenchRuns:vi.fn(async()=>[]),workbenchCapabilities:vi.fn(async()=>({model_enabled:false})),workbenchAsk:vi.fn(),openSource:vi.fn(async(_,body)=>({...source,document_id:'doc1',version_id:'file-v1',file_format:'pdf',page_number:body.page,raw_md:'原文快照',pages:[{ordinal:1,readable:true,warnings:[]},{ordinal:2,readable:false,warnings:['image_not_extracted']}]}))}
  const scope=effectScope();scopes.push(scope);const owner=ref('a'),w=scope.run(()=>reactive(useStudyWorkbench(api,owner,store)))
  return{api,owner,w}
}
function render(component,props){const v=mount(component,{props,attachTo:document.body});wrappers.push(v);return v}
const question=(id='q1',resource='r1',concept='c1')=>({id,status:'practice',source_status:'current',source:{resource_id:resource,title:'原题文件'},review:{automation:{}},payload:{stem:'公式 $w^2$ 的含义',question_type:'short_answer',concepts:[{architecture_id:'g1',concept_id:concept}]}})
const knowledge=[{architecture_id:'g1',concepts:[{id:'c1',name:'同名概念',formal_knowledge_ids:['gradient_descent']},{id:'c2',name:'同名概念',formal_knowledge_ids:[]}]}]

describe('integrated learning experience',()=>{
  it('opens original pages beside chat without selecting sources or invoking models',async()=>{
    const {w,api}=setup();await w.load();const v=render(StudyWorkbench,{workspace:w});await flushPromises()
    expect(v.get('.wb-grid').attributes('data-inspector')).toBe('closed')
    const selected=JSON.stringify(w.selected)
    await v.get('[aria-label="打开资料：合成课件"]').trigger('click');await flushPromises()
    expect(v.get('.wb-grid').attributes('data-inspector')).toBe('open')
    expect(v.get('.source-inline [role=region]').text()).toContain('原文快照')
    await v.get('#source-preview-page').setValue('2');await flushPromises()
    expect(api.openSource.mock.calls[1][1]).toEqual({...Object.fromEntries(Object.entries(source).filter(([k])=>['source_type','source_id','source_version'].includes(k))),page:2})
    expect(v.text()).toContain('本页尚无足够可检索正文');expect(JSON.stringify(w.selected)).toBe(selected)
    expect(api.workbenchAsk).not.toHaveBeenCalled()
  })
  it('does not overwrite a question draft when navigating from a learning suggestion',async()=>{
    const {w,api}=setup();await w.load();w.query='我还没发送的问题';w.prepare('解释梯度下降')
    expect(w.query).toBe('我还没发送的问题');expect(w.suggestion).toBe('解释梯度下降')
    const v=render(StudyWorkbench,{workspace:w});await flushPromises()
    await v.findAll('button').find(b=>b.text()==='保留原草稿').trigger('click')
    expect(w.query).toBe('我还没发送的问题');expect(w.suggestion).toBe('');expect(api.workbenchAsk).not.toHaveBeenCalled()
  })
  it('returns to the source tab and opener after closing a narrow-screen original',async()=>{
    const {w}=setup();await w.load();const v=render(StudyWorkbench,{workspace:w});await flushPromises()
    w.panel='sources';const opener=v.get('[aria-label="打开资料：合成课件"]');opener.element.focus()
    await opener.trigger('click');await flushPromises();expect(w.panel).toBe('studio')
    await v.get('[aria-label="关闭原文抽屉"]').trigger('keydown',{key:'Escape'});await flushPromises()
    expect(w.panel).toBe('sources');expect(document.activeElement).toBe(opener.element)
  })
  it('discards late preview responses when the source is closed or student changes',async()=>{
    const {w,api,owner}=setup();await w.load();let resolve
    api.openSource.mockImplementation(()=>new Promise(r=>{resolve=r}))
    const pending=w.open(source);w.closePreview();resolve({...source,raw_md:'late'});await pending
    expect(w.drawer).toBe(null)
    const next=w.open(source);owner.value='b';resolve({...source,raw_md:'private'});await next
    expect(w.drawer).toBe(null);expect(w.opening).toBe(false)
  })
  it('a citation cannot be replaced by an earlier slow source preview',async()=>{
    const {w,api}=setup();await w.load();let resolve
    api.openSource.mockImplementation(()=>new Promise(r=>{resolve=r}));const pending=w.open(source)
    w.current={source_statuses:[]};w.citation({...source,citation_id:'snap',raw_md:'历史快照'})
    resolve({...source,raw_md:'current'});await pending;expect(w.drawer.raw_md).toBe('历史快照')
  })
  it('keyboard submission honors empty selection and never auto-requests on suggested questions',async()=>{
    const {w,api}=setup();await w.load();const v=render(StudyWorkbench,{workspace:w});await flushPromises()
    await v.findAll('.wb-starters button')[0].trigger('click');expect(w.query).toBeTruthy();expect(api.workbenchAsk).not.toHaveBeenCalled()
    w.toggle(source,false);await v.get('#wb-question').trigger('keydown',{key:'Enter',ctrlKey:true})
    expect(api.workbenchAsk).not.toHaveBeenCalled()
  })
  it('matches practice using stable confirmed associations, not identical concept names',()=>{
    const rows=[question(),question('q2','r2','c2'),{...question('q3'),source_status:'modified'}]
    expect(practiceCandidates(rows,knowledge,{topic:'gradient_descent'}).map(q=>q.id)).toEqual(['q1'])
    expect(practiceCandidates(rows,knowledge,{resource:'r2'}).map(q=>q.id)).toEqual(['q2'])
    expect(practiceCandidates(rows,knowledge,{topic:'missing'})).toEqual([])
  })
  it('an unknown document scope does not fall back to all questions or allocate a session',async()=>{
    const w=reactive({owner:'a',filter:{},questions:[question()],resources:[],knowledge,busy:'',pending:null,session:{question_id:'q1'},load:vi.fn(),start:vi.fn()})
    const v=render(PracticeHub,{workspace:w,context:{document:'unknown'}});await flushPromises()
    expect(v.text()).toContain('当前范围没有可用练习');expect(v.findAll('.practice-question')).toHaveLength(0)
    expect(v.text()).not.toContain('继续上次练习')
    expect(w.start).not.toHaveBeenCalled()
  })
  it('shows no BKT probability without evidence and prepares real learning links without writes',async()=>{
    const overview=guidance(),s=reactive({overview,load:vi.fn(),error:'',draft:{},history:[]}),g={load:vi.fn(),runs:[],selected:[],mode:'rules'}
    const v=render(LearningInsights,{selfWorkspace:s,guideWorkspace:g,goals:'逻辑回归'})
    expect(v.get('.progress-topics').text()).toContain('待诊断');expect(v.get('.progress-topics').text()).not.toContain('20.0%')
    await v.get('.learning-next .button.primary').trigger('click')
    expect(v.emitted('navigate')[0]).toEqual(['study',expect.objectContaining({knowledge:'linear_regression_loss',question:expect.stringContaining('线性回归')})])
    expect(s.load).toHaveBeenCalledTimes(1);expect(g.load).toHaveBeenCalledTimes(1)
  })
  it('standalone guide citations retain a modal focus trap and safe Markdown',async()=>{
    const v=render(SourceDrawer,{source:{...source,current_status:'current',raw_md:'<script>bad()</script>安全原文',preview:false}})
    await flushPromises();expect(v.get('[role=dialog]').attributes('aria-modal')).toBe('true');expect(v.find('script').exists()).toBe(false)
    await v.get('[role=dialog]').trigger('keydown',{key:'Escape'});expect(v.emitted('close')).toHaveLength(1)
  })
})
