import { afterEach, describe, expect, it, vi } from 'vitest'
import { effectScope, nextTick, reactive } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { useReviewPractice } from '../useReviewPractice.js'
import ReviewPracticePanel from '../components/ReviewPracticePanel.vue'
import LearningOverview from '../views/LearningOverview.vue'
import App from '../App.vue'
import { createApi } from '../api.js'
import { assignment, client, memoryStore, state } from './fixtures.js'

const scopes = [], wrappers = []
afterEach(() => { scopes.splice(0).forEach(s => s.stop()); wrappers.splice(0).forEach(w => w.unmount()); localStorage.clear() })
const storage = () => { const m = new Map(); return {getItem: k => m.get(k) || null, setItem: (k,v) => m.set(k,v)} }
const items = () => [0, 1].map(i => ({ review_key: `key-${i}`, event_id: `old-${i}`, question: assignment(i).question,
  correct_answer: 'B', explanation: '原解析 $x^2$。', last_correct: i === 1 }))
const response = id => ({student_id: id, mode: 'self_review', learning_revision: 2, bkt_updated: false, items: items()})
const stopped = () => ({...assignment(2), question: null, action: 'stopped', stop_reason: 'insufficient_questions', reason: '新题已耗尽'})
function setup(store = storage(), api = {reviewExercises: vi.fn(async id => response(id))}) {
  const scope = effectScope(); scopes.push(scope)
  const w = reactive({student: 'a', decision: stopped()})
  const r = scope.run(() => reactive(useReviewPractice(api, w, store)))
  return {r, w, api, store}
}

describe('exhausted-question self-review', () => {
  it('offers a working continuation without needing approved personal questions', async () => {
    const {r, w, api} = setup()
    const workspace = {...w, busy:'', history:[], snapshot:state(2), activeTopic:'线性回归', topicName:x=>x}
    const v = mount(LearningOverview, {props:{w:workspace, review:r}}); wrappers.push(v)
    expect(v.text()).toContain('正式新题已做完，可以继续复习')
    const button = v.findAll('button').find(b => b.text() === '复习已做题（不更新掌握度）')
    await button.trigger('click'); await flushPromises()
    expect(api.reviewExercises).toHaveBeenCalledWith('a')
    expect(v.findAll('.review-practice input[type=radio]')).toHaveLength(4)
    await v.get('.review-practice input[value=B]').setValue(true)
    await v.get('.review-practice form').trigger('submit')
    expect(v.get('.review-practice .feedback').text()).toContain('本次复习答对了')
    await v.findAll('button').find(b=>b.text()==='复习下一题').trigger('click')
    expect(r.current.review_key).toBe('key-1')
    expect(r.result).toBeNull()
    expect(workspace.snapshot.revision).toBe(2)
  })
  it('repeats with feedback but never calls formal answers, next or model APIs', async () => {
    const api = {...client(), reviewExercises:vi.fn(async id=>response(id))}
    const {r}=setup(storage(),api); await r.open(); r.select('A'); r.submit(); r.submit()
    expect(r.result.correct).toBe(false); expect(r.records).toHaveLength(1)
    r.next(); r.select('B'); r.submit(); expect(r.result.correct).toBe(true)
    r.next(); expect(r.current.review_key).toBe('key-0')
    expect(api.submit).not.toHaveBeenCalled(); expect(api.next).not.toHaveBeenCalled(); expect(api.tutor).not.toHaveBeenCalled()
  })
  it('restores an unfinished answer and a completed result using reads only', async () => {
    const first=setup(); await first.r.open(); first.r.select('B')
    const second=setup(first.store); await flushPromises()
    expect(second.r.active).toBe(true); expect(second.r.selected).toBe('B'); expect(second.r.result).toBeNull()
    second.r.submit(); const reviewId=second.r.result.review_id
    const third=setup(first.store); await flushPromises()
    expect(third.r.result.review_id).toBe(reviewId); expect(third.r.records).toHaveLength(1)
    expect(third.api.reviewExercises).toHaveBeenCalledTimes(1)
  })
  it('keeps identities separate and ignores a late old-identity response', async () => {
    let resolve
    const api={reviewExercises:vi.fn(id=>id==='a'?new Promise(r=>resolve=r):Promise.resolve({...response(id),items:[]}))}
    const {r,w}=setup(storage(),api); const pending=r.open()
    w.student='b'; await nextTick(); await r.open(); resolve(response('a')); await pending
    expect(r.items).toEqual([]); expect(r.records).toEqual([]); expect(r.selected).toBe('')
    expect(r.busy).toBe(false)
  })
  it('keeps usable feedback when browser storage is blocked and reports its limit', async () => {
    const {r}=setup({getItem:()=>null,setItem:()=>{throw Error('quota')}})
    await r.open(); r.select('B'); r.submit()
    expect(r.result.correct).toBe(true); expect(r.storageWarning).toContain('当前页面')
  })
  it('discards stale saved results instead of using an unmatched snapshot', async () => {
    const first=setup(); await first.r.open(); first.r.select('B'); first.r.submit()
    const second=setup(first.store,{reviewExercises:vi.fn(async id=>({...response(id),items:[{...items()[0],review_key:'new-version'}]}))})
    await flushPromises(); expect(second.r.result).toBeNull(); expect(second.r.selected).toBe(''); expect(second.r.records).toEqual([])
  })
  it('renders empty, failed and retry states without allocating formal questions', async () => {
    const api={reviewExercises:vi.fn().mockRejectedValueOnce(Error('网络中断')).mockResolvedValue({...response('a'),items:[]})}
    const {r}=setup(storage(),api); await r.open()
    const v=mount(ReviewPracticePanel,{props:{review:r,topicName:x=>x}}); wrappers.push(v)
    expect(v.get('[role=alert]').text()).toContain('网络中断')
    await v.findAll('button').find(b=>b.text()==='重新读取复习题').trigger('click'); await flushPromises()
    expect(v.text()).toContain('还没有可复习的已做题')
  })
  it('the application can restore review across navigation without writes', async () => {
    const api=client(); api.reviewExercises=vi.fn(async id=>response(id)); api.currentDecision.mockResolvedValue(stopped())
    const v=mount(App,{props:{client:api,store:memoryStore({student_id:'learner-test'})}}); wrappers.push(v); await flushPromises()
    await v.findAll('button').find(b=>b.text()==='复习已做题（不更新掌握度）').trigger('click'); await flushPromises()
    await v.get('.review-practice input[value=B]').setValue(true)
    await v.findAll('nav button').find(b=>b.text()==='学习记录').trigger('click'); await flushPromises()
    await v.findAll('nav button').find(b=>b.text()==='我的学习').trigger('click'); await flushPromises()
    expect(v.get('.review-practice input[value=B]').element.checked).toBe(true)
    expect(api.submit).not.toHaveBeenCalled(); expect(api.next).not.toHaveBeenCalled()
  })
  it('API contract is read-only with an encoded student scope', async () => {
    const fetcher=vi.fn(async()=>({ok:true,json:async()=>response('scope name')}))
    await createApi(fetcher).reviewExercises('scope name')
    expect(fetcher.mock.calls[0][0]).toBe('/api/v1/students/scope%20name/review-exercises')
    expect(fetcher.mock.calls[0][1].method).toBe('GET')
  })
})
