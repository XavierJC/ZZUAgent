import { afterEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { effectScope, reactive, ref } from 'vue'
import { usePersonalBank } from '../features/practice/usePersonalBank.js'
import LearningHome from '../features/notebooks/LearningHome.vue'
import ExerciseDesk from '../features/practice/ExerciseDesk.vue'
import SourceDrawer from '../components/SourceDrawer.vue'
import ProductDialog from '../shared/ProductDialog.vue'
import AppSidebar from '../app/AppSidebar.vue'
const clean=[]
afterEach(()=>{ clean.splice(0).reverse().forEach(w=>w.unmount());document.body.innerHTML='' })
const render=(component,props)=>{const w=mount(component,{props,attachTo:document.body});clean.push(w);return w}
describe('UI learning paths and accessibility',()=>{
  it('waits for an in-flight page read before restoring a question deep link',async()=>{
    let resolve
    const gate=new Promise(done=>{resolve=done})
    const api={bank:vi.fn(async(_owner,path)=>{if(path==='course-resources'){await gate;return{items:[],knowledge:[]}}if(path==='personal-bank/questions/q1')return{id:'q1',revision:1,payload:{stem:'deep link',question_type:'short_answer'},source:{}};return{items:[]}})}
    const scope=effectScope();clean.push({unmount:()=>scope.stop()})
    const bank=scope.run(()=>reactive(usePersonalBank(api,ref('synthetic-deep-link'))))
    const mounting=bank.load(),restoring=bank.load().then(()=>bank.open('q1'))
    expect(bank.current).toBeNull();resolve();await Promise.all([mounting,restoring]);expect(bank.current.id).toBe('q1')
    expect(api.bank.mock.calls.filter(c=>c[1]==='course-resources')).toHaveLength(1)
    expect(api.bank.mock.calls.every(c=>!c[2] || c[2]==='GET')).toBe(true)
  })
  it('uses saved evidence, never the BKT prior, on the learning home',()=>{
    const navigate=vi.fn(), space={goalsText:'梯度下降',navigate,w:{snapshot:{mastery:[{has_evidence:false,probability:.2,attempts:0}]}}}
    const ui=render(LearningHome,{space,books:{items:[]}})
    expect(ui.text()).toContain('待诊断');expect(ui.text()).not.toContain('20%');expect(ui.get('progress').attributes('value')).toBe('0')
    expect(navigate).not.toHaveBeenCalled()
  })
  it('continues the current notebook by stable ID without querying or creating data',async()=>{
    const navigate=vi.fn(),space={navigate,w:{},goalsText:'模型评估'}
    const ui=render(LearningHome,{space,books:{items:[],current:{detail:{id:'stable',title:'当前主题',archived:false}}}})
    await ui.get('.product-primary').trigger('click');expect(navigate).toHaveBeenCalledWith('notebook',{book:'stable'})
  })
  it('keeps all legacy learning and management entries in the same navigation',()=>{
    const ui=render(AppSidebar,{space:{tab:'publish',isBuilder:true,w:{active:true}}})
    expect(ui.text()).toContain('我的笔记');expect(ui.text()).toContain('正式诊断与复测');expect(ui.text()).toContain('原文资料');expect(ui.get('[aria-current=page]').text()).toBe('课程审核与发布')
  })
  it('opens the exact PDF version and page without claiming text highlighting',()=>{
    const ui=render(SourceDrawer,{source:{title:'合成PDF',source_type:'uploaded_document',file_format:'pdf',page_number:3,current_status:'current',raw_md:'Page three',original_file_url:'/original?version_id=v3'}})
    expect(ui.get('a').attributes('href')).toBe('/original?version_id=v3#page=3');expect(ui.text()).toContain('不提供文字高亮')
  })
  it('blocks background focus and restores it after Escape closes a dialog',async()=>{
    const button=document.createElement('button');document.body.append(button);button.focus()
    const ui=render(ProductDialog,{open:false,title:'编辑主题'});await ui.setProps({open:true});await flushPromises()
    expect(button.inert).toBe(true);await ui.get('[role=dialog]').trigger('keydown',{key:'Escape'});expect(ui.emitted('close')).toHaveLength(1)
    await ui.setProps({open:false});expect(button.inert).toBeFalsy();expect(document.activeElement).toBe(button)
  })
  it('counts unique completed questions and saves an unsent draft before navigating',async()=>{
    const q=id=>({id,status:'practice',source_status:'manual',source:{title:'合成题'},payload:{question_type:'short_answer',stem:id}})
    const session=(id,qid,result)=>({id,question_id:qid,question_revision:1,source:{title:'合成题'},question:{question_type:'short_answer',stem:qid},result,draft:{response_text:''}})
    const first=session('s1','q1',null),second=session('s2','q2',{correct:null})
    const w=reactive({questions:[q('q1'),q('q2')],knowledge:[],resources:[],sessions:[first,second,session('s3','q2',{correct:null})],session:first,selected:'未提交推导',needsReview:false,busy:'',pending:null,load:vi.fn(async()=>{}),saveResponseDraft:vi.fn(async()=>{first.draft.response_text='未提交推导'}),viewSession:vi.fn(async item=>{w.session=item;w.selected=''}),start:vi.fn()})
    const ui=render(ExerciseDesk,{workspace:w});await flushPromises()
    expect(ui.get('progress').attributes('value')).toBe('1');expect(ui.get('progress').attributes('max')).toBe('2');expect(ui.text()).toContain('第 1 题 / 共 2 题')
    await ui.get('.practice-number-nav').findAll('button')[1].trigger('click');await flushPromises()
    expect(w.saveResponseDraft).toHaveBeenCalledOnce();expect(w.viewSession).toHaveBeenCalledWith(second);expect(w.start).not.toHaveBeenCalled()
  })
})
