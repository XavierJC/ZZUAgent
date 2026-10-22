import { afterEach, describe, expect, it, vi } from 'vitest'
import { effectScope, reactive, ref, defineComponent } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { usePersonalBank } from '../usePersonalBank.js'
import { usePageRoute } from '../usePageRoute.js'
import QuestionFields from '../features/questions/QuestionFields.vue'
import PersonalBankWorkspace from '../components/PersonalBankWorkspace.vue'
import { emptyQuestion } from '../features/questions/types.js'

const scopes=[],wrappers=[]
afterEach(()=>{scopes.splice(0).forEach(s=>s.stop());wrappers.splice(0).forEach(w=>w.unmount())})
function setup() {
  const resource={resource_id:'r1',source_version:'v1',title:'自建资料',status:'active',original_source_type:'text',original_source_id:'raw',resource_type:'exercise_material',format:'txt',links:[],revision:1}
  let task=null,draft={revision:0,response_text:'',needs_review:false}
  const session=()=>({id:'s1',question_id:'q1',question_revision:1,question:{...emptyQuestion(),stem:'解释过拟合'},source:{},source_status:'manual',result:null,draft:{...draft}})
  const api={bank:vi.fn(async (_,path,method='GET',body)=>{
    if(path==='course-resources')return{items:[resource],knowledge:[]}
    if(path==='course-resources/r1')return{resource,units:[{text:'1. 解释过拟合',location:{}}],run_id:null}
    if(path.startsWith('personal-bank/questions?'))return{items:[]}
    if(path==='personal-bank/practice' && method==='GET')return{items:[session()]}
    if(path==='personal-bank/practice' && method==='POST')return{session_id:'s1'}
    if(path==='personal-bank/practice/s1')return session()
    if(path==='personal-bank/practice/s1/draft'){draft={revision:1,response_text:body.response_text,needs_review:body.needs_review};return{session_id:'s1',revision:1}}
    if(path==='personal-bank/extraction-capabilities')return{enabled:true,model:'deepseek-flash'}
    if(path==='personal-bank/extraction-tasks' && method==='GET')return{items:task?[task]:[]}
    if(path==='personal-bank/extraction-tasks' && method==='POST'){task={request_id:body.request_id,status:'running',model_calls:0,source:resource,result:{}};return task}
    if(path.startsWith('personal-bank/extraction-tasks/'))return task
    throw Error('Unexpected '+path)
  }),documentPreview:vi.fn()}
  const scope=effectScope();scopes.push(scope);const storage={map:new Map(),getItem(k){return this.map.get(k)||null},setItem(k,v){this.map.set(k,v)}}
  const student=ref('a'),w=scope.run(()=>reactive(usePersonalBank(api,student,storage)))
  return{w,api,storage,student}
}
describe('approved extraction and navigation flow',()=>{
  it('does not transmit selected source before independent consent, resets consent after one task',async()=>{
    const {w,api}=setup();await w.load();await w.selectResource(w.resources[0]);await w.extractResource()
    expect(api.bank.mock.calls.filter(c=>c[2]==='POST')).toHaveLength(0)
    w.extractionConsent=true;await w.extractResource();expect(w.extractionConsent).toBe(false)
    expect(w.tasks).toHaveLength(1);expect(w.section).toBe('bank')
    expect(api.bank.mock.calls.filter(c=>c[2]==='POST')).toHaveLength(1)
    await w.loadTasks();await w.loadTasks();expect(api.bank.mock.calls.filter(c=>c[2]==='POST')).toHaveLength(1)
  })
  it('restores a lost task receipt using GET without resending a model request',async()=>{
    const {w,api}=setup();await w.load();await w.selectResource(w.resources[0]);w.extractionConsent=true;await w.extractResource()
    w.pending={request_id:w.tasks[0].request_id,path:'personal-bank/extraction-tasks'};w.persist();await w.load()
    expect(w.pending).toBe(null);expect(api.bank.mock.calls.filter(c=>c[2]==='POST')).toHaveLength(1)
  })
  it('saves and restores text responses without allocating another practice session',async()=>{
    const {w,api}=setup();await w.load();await w.start('q1');w.selected='我的解答 $x^2$';w.needsReview=true;await w.saveResponseDraft()
    expect(w.session.draft.response_text).toBe('我的解答 $x^2$')
    const allocations=api.bank.mock.calls.filter(c=>c[2]==='POST').length
    await w.viewSession(w.sessions[0]);expect(w.selected).toBe('我的解答 $x^2$');expect(w.needsReview).toBe(true)
    expect(api.bank.mock.calls.filter(c=>c[2]==='POST')).toHaveLength(allocations)
  })
  it('renders a textarea rather than choice controls for subjective practice and safely previews math',async()=>{
    const {w}=setup();await w.load();await w.start('q1')
    const wrapper=mount(PersonalBankWorkspace,{props:{workspace:w,mode:'bank'}});wrappers.push(wrapper);await flushPromises()
    w.section='practice';await flushPromises();expect(wrapper.find('#pb-response').exists()).toBe(true)
    expect(wrapper.find('input[type=radio]').exists()).toBe(false)
    await wrapper.get('#pb-response').setValue('公式 $x^2$');expect(w.selected).toBe('公式 $x^2$')
  })
  it('edits independent text answers and subquestions without making A/B steps into choices',async()=>{
    const value=reactive({...emptyQuestion(),stem:'A. 说明现象\nB. 说明原因'})
    const wrapper=mount(QuestionFields,{props:{value}});wrappers.push(wrapper)
    expect(wrapper.find('#pb-answer').exists()).toBe(false)
    await wrapper.get('#pb-answer-text').setValue('保留原文答案')
    await wrapper.findAll('button').find(b=>b.text()==='增加子问').trigger('click')
    await wrapper.get('#pb-sub-0-stem').setValue('第二小问')
    expect(value.subquestions[0].stem).toBe('第二小问');expect(value.options).toEqual([]);expect(value.answer_text).toBe('保留原文答案')
  })
  it('supports ID deep links, guarded navigation and back state without model actions',async()=>{
    history.replaceState(null,'','/#/bank?question=q1')
    let r;const before=vi.fn(()=>true)
    const Harness=defineComponent({setup(){r=usePageRoute(before);return{}},template:'<div />'})
    wrappers.push(mount(Harness));expect(r.route.value).toEqual({page:'bank',params:{question:'q1'}})
    r.go('materials',{resource:'r1'});expect(location.hash).toContain('resource=r1')
    history.replaceState(null,'','/#/bank?question=q1');window.dispatchEvent(new PopStateEvent('popstate'))
    expect(r.route.value.page).toBe('bank');before.mockReturnValue(false);expect(r.go('notes')).toBe(false)
    expect(r.route.value.params.question).toBe('q1')
  })
})
