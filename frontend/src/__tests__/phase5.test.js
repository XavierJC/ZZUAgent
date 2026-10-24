import { afterEach, describe, expect, it, vi } from 'vitest'
import { effectScope, reactive, ref } from 'vue'
import { mount } from '@vue/test-utils'
import { settleCoursePage as flushPromises } from './course-page-testing.js'
import App from '../App.vue'
import { useWorkspace } from '../useWorkspace.js'
import { useTeachingWorkspace } from '../useTeachingWorkspace.js'
import { useCourseBuilder } from '../useCourseBuilder.js'
import { client, state, assignment, receipt, memoryStore } from './fixtures.js'
import { ApiError } from '../api.js'

const scopes=[],wrappers=[]
afterEach(()=>{scopes.splice(0).forEach(s=>s.stop());wrappers.splice(0).forEach(w=>w.unmount())})
const store=()=>{const m=new Map();return{getItem:k=>m.get(k)||null,setItem:(k,v)=>m.set(k,v)}}
const release={id:'release-demo',title:'机器学习演示课程',release_version:1,question_versions:[],source_statuses:[],architecture:null,kind:'demo',usable:true,review_warning:'内容待审核',retrieval_scope:[]}
function fixture(){
  const api=client();let lesson={session:null},drafts=[],saved=null
  api.currentDecision.mockResolvedValue(null)
  api.publishedCourses=vi.fn(async()=>({items:[release]}));api.courseReleases=vi.fn(async()=>({items:[release]}))
  api.courseBuilder=vi.fn(async()=>({drafts,course_sources:[],architectures:[],documents:[],formal_questions:[],releases:[release],candidate_count:40,shared_formal_count:10,additional_candidate_count:30}))
  api.courseWorkflow=vi.fn(async(_,path,method='GET',body)=>{
    if(path==='teaching-sessions' && method==='GET')return lesson
    if(path==='teaching-sessions/s1')return lesson
    if(path==='teaching-sessions' && method==='POST'){lesson={session:{id:'s1',release_id:release.id,stage:'goals'},release,next_task:{action:'diagnose',reason:'尚无答题证据',knowledge_id:'linear_regression_loss'},decision:null,history:[],guidance:{items:[],recommendations:[],versions:{bkt:'mock',knowledge:'mock'}},explanations:[],has_objective_evidence:false};return{session_id:'s1'}}
    if(path==='teaching-sessions/s1/next'){lesson={...lesson,decision:assignment(),session:{...lesson.session,stage:'diagnosis'}};api.currentDecision.mockResolvedValue(assignment());return{session_id:'s1',decision:assignment()}}
    if(path==='teaching-sessions/s1/answers'){lesson={...lesson,decision:null,last_feedback:receipt(),session:{...lesson.session,stage:'analysis'}};api.currentDecision.mockResolvedValue(null);api.mastery.mockResolvedValue(state(1));api.history.mockResolvedValue({revision:1,items:[receipt()]});return{session_id:'s1',result:receipt()}}
    if(path==='course-builder/drafts' && method==='POST'){saved={draft_id:'d1',revision:1};drafts=[{id:'d1',revision:1,payload:body.payload}];return saved}
    if(path==='course-builder/drafts/d1' && method==='GET')return{draft_id:'d1',revision:1,payload:drafts[0].payload,formal_blockers:['未审核'],formal_allowed:false,snapshot_hash:'a'.repeat(64)}
    if(path.startsWith('course-workflow/requests/')){if(saved)return saved;throw new ApiError('未找到',{status:404})}
    throw Error('unexpected '+method+' '+path)
  })
  return api
}
function setup(api=fixture(),storage=store()){
  const scope=effectScope();scopes.push(scope)
  return scope.run(()=>{const w=reactive(useWorkspace(api,memoryStore({student_id:'learner-test'})));return{api,w,flow:reactive(useTeachingWorkspace(api,w,storage)),storage}})
}
describe('Phase5 real workspace service boundaries',()=>{
  it('boot refresh and history restoration never allocate the next question',async()=>{
    const {api,w,flow}=setup();await w.boot();await flow.load();await w.refresh();await flow.load()
    expect(api.next).not.toHaveBeenCalled();expect(api.submit).not.toHaveBeenCalled()
    expect(api.courseWorkflow.mock.calls.filter(c=>c[2]==='POST')).toHaveLength(0)
    expect(api.currentDecision).toHaveBeenCalledTimes(2)
  })
  it('explicit session and diagnosis use new endpoints; score refresh does not allocate again',async()=>{
    const {api,w,flow}=setup();await w.boot();await flow.load();flow.selectedRelease=release.id
    await flow.begin();expect(flow.session.id).toBe('s1');expect(w.decision).toBe(null)
    await flow.allocate();w.selected='B';await flow.submit()
    expect(w.feedback.correct).toBe(true);expect(w.snapshot.revision).toBe(1)
    const posts=api.courseWorkflow.mock.calls.filter(c=>c[2]==='POST')
    expect(posts.map(c=>c[1])).toEqual(['teaching-sessions','teaching-sessions/s1/next','teaching-sessions/s1/answers'])
    await flow.load();expect(api.courseWorkflow.mock.calls.filter(c=>c[2]==='POST')).toHaveLength(3)
    expect(api.next).not.toHaveBeenCalled()
  })
  it('keeps a lost command and only reads receipts on refresh',async()=>{
    const {api,w,flow}=setup();await w.boot();await flow.load()
    const original=api.courseWorkflow.getMockImplementation()
    api.courseWorkflow.mockImplementation((id,path,method,body)=>method==='POST'?Promise.reject(new ApiError('lost',{uncertain:true})):original(id,path,method,body))
    await flow.begin();expect(flow.pending).not.toBe(null)
    const count=api.courseWorkflow.mock.calls.filter(c=>c[2]==='POST').length
    await flow.load();expect(api.courseWorkflow.mock.calls.filter(c=>c[2]==='POST')).toHaveLength(count)
  })
  it('blocks writes when a durable request id cannot be saved',async()=>{
    const {api,w,flow}=setup(fixture(),{getItem:()=>null,setItem:()=>{throw Error('full')}})
    await w.boot();await flow.load();await flow.begin();expect(api.courseWorkflow.mock.calls.filter(c=>c[2]==='POST')).toHaveLength(0)
    expect(flow.error).toContain('无法保留')
  })
  it('splits workspace navigation and retains all auxiliary learning entries',async()=>{
    const api=fixture();const wrapper=mount(App,{props:{client:api,store:memoryStore({student_id:'learner-test'})}});wrappers.push(wrapper);await flushPromises()
    const names=wrapper.findAll('nav button').map(b=>b.text())
    expect(names).toEqual(expect.arrayContaining(['资料学习','练习','学习进度','学习记录','我的笔记','原文资料','正式学习与复习']))
    expect(names).not.toContain('习题管理')
    await wrapper.findAll('.workspace-switch button').find(b=>b.text()==='课程构建').trigger('click');await flushPromises()
    expect(wrapper.findAll('nav button').map(b=>b.text())).toEqual(['课程概览','课程资料','知识体系','习题管理','课程审核与发布'])
    expect(wrapper.text()).toContain('不是教师账号或真实权限隔离')
    expect(api.next).not.toHaveBeenCalled();expect(api.submit).not.toHaveBeenCalled()
  })
  it('starts on legacy resource links in the builder, without rewriting their IDs',async()=>{
    history.replaceState(null,'','/#/materials?resource=old-stable-id')
    const wrapper=mount(App,{props:{client:fixture(),store:memoryStore({student_id:'learner-test'})}});wrappers.push(wrapper);await flushPromises()
    expect(wrapper.get('.workspace-switch [aria-pressed=true]').text()).toBe('课程构建')
    expect(location.hash).toContain('old-stable-id')
  })
  it('completes an explicit formal-learning deep link into a bound diagnosis without the legacy next endpoint',async()=>{
    history.replaceState(null,'','/#/learn')
    const api=fixture();const wrapper=mount(App,{props:{client:api,store:memoryStore()}});wrappers.push(wrapper);await flushPromises()
    await wrapper.get('#learner-id').setValue('learner-test')
    await wrapper.get('.start-form').trigger('submit');await flushPromises()
    expect(api.next).not.toHaveBeenCalled()
    expect(api.courseWorkflow.mock.calls.filter(c=>c[2]==='POST').map(c=>c[1])).toEqual(['teaching-sessions','teaching-sessions/s1/next'])
    expect(wrapper.find('.question-panel input[value="B"]').exists()).toBe(true)
    await wrapper.get('.question-panel input[value="B"]').setValue(true);await wrapper.get('.question-panel form').trigger('submit');await flushPromises()
    expect(wrapper.get('.feedback').text()).toContain('答对了')
    const allocations=api.courseWorkflow.mock.calls.filter(c=>c[1].endsWith('/next')).length
    await wrapper.get('[aria-label="刷新学习记录"]').trigger('click');await flushPromises()
    expect(wrapper.get('.feedback').text()).toContain('答对了')
    expect(api.courseWorkflow.mock.calls.filter(c=>c[1].endsWith('/next'))).toHaveLength(allocations)
    expect(api.tutor).not.toHaveBeenCalled()
  })
  it('keeps builder drafts separate and refreshes without saving or publishing',async()=>{
    const scope=effectScope();scopes.push(scope);const api=fixture(),storage=store(),student=ref('learner-test')
    const b=scope.run(()=>reactive(useCourseBuilder(api,student,storage)))
    await b.load();b.fresh();b.editor.title='保留的构建草稿';b.persist()
    const second=scope.run(()=>reactive(useCourseBuilder(api,student,storage)));await second.load()
    expect(second.editor.title).toBe('保留的构建草稿')
    expect(api.courseWorkflow.mock.calls.filter(c=>c[2] && c[2]!=='GET')).toHaveLength(0)
    await second.save();expect(second.current).toBe('d1');expect(second.dirty).toBe(false)
    await second.load();expect(api.courseWorkflow.mock.calls.filter(c=>c[2] && c[2]!=='GET')).toHaveLength(1)
  })
})
