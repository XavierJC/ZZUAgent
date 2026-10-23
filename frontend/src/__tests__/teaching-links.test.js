import { describe,it,expect,vi,afterEach } from 'vitest'
import { effectScope,ref,reactive } from 'vue'
import { mount,flushPromises } from '@vue/test-utils'
import { useTeachingLinks } from '../useTeachingLinks.js'
import TeachingMaterialReview from '../components/TeachingMaterialReview.vue'
const scopes=[]
afterEach(()=>scopes.splice(0).forEach(s=>s.stop()))
function setup(){const scope=effectScope();scopes.push(scope);const owner=ref('a'),m=new Map(),store={getItem:k=>m.get(k)||null,setItem:(k,v)=>m.set(k,v)}
  const client={teachingLinks:vi.fn(async()=>({items:[]})),courseBuilder:vi.fn(async()=>({architectures:[]})),courseWorkflow:vi.fn(async()=>{throw Error('uncertain')})}
  return {client,owner,store,b:scope.run(()=>reactive(useTeachingLinks(client,owner,store)))}
}
describe('teacher material review boundaries',()=>{
  it('restores candidate drafts without posting and clears another student scope',async()=>{
    const {client,b,owner}=setup();await b.load();b.draft.excerpt_md='local transcription';b.persist();await b.load()
    expect(client.courseWorkflow).not.toHaveBeenCalled();owner.value='b';expect(b.items).toEqual([]);expect(b.draft.excerpt_md).toBe('')
  })
  it('queries uncertain review receipts on refresh without resending the write',async()=>{
    const {client,b}=setup();await b.load();await b.create();expect(b.pending).toBeTruthy();await b.load()
    expect(client.courseWorkflow.mock.calls.filter(c=>c[2]==='POST')).toHaveLength(1)
    expect(client.courseWorkflow.mock.calls.some(c=>c[1].includes('/requests/'))).toBe(true)
  })
  it('requires a published concept and explicit original-page review before confirmation',async()=>{
    const b={items:[{id:'x',document_id:'d',version_id:'v',page_number:32,concept_id:'c',architecture_id:'a',status:'candidate',excerpt_md:'$TP/(TP+FP)$',original_text:'header'}],catalog:{architectures:[]},draft:{},load:vi.fn(),review:vi.fn()}
    const wrapper=mount(TeachingMaterialReview,{props:{workspace:b,documents:{},student:'s'}});await flushPromises()
    expect(wrapper.findAll('button').find(x=>x.text()==='确认此片段可检索').attributes('disabled')).toBeDefined()
    expect(b.review).not.toHaveBeenCalled();expect(wrapper.get('img').attributes('src')).toContain('page=32');wrapper.unmount()
  })
})
