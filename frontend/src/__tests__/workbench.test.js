import { describe, it, expect, vi, afterEach } from 'vitest'
import { reactive, ref, nextTick } from 'vue'
import { mount, flushPromises } from '@vue/test-utils'
import { useStudyWorkbench } from '../useStudyWorkbench.js'
import StudyWorkbench from '../components/StudyWorkbench.vue'
import App from '../App.vue'
import { ApiError } from '../api.js'
import { client as learningClient, memoryStore, state } from './fixtures.js'
import { notesApi } from './notes-fixtures.js'

const course = { source_type: 'course_material', source_id: 'gradient', source_version: 'c1', title: '梯度下降', index_status: 'ready', source_revision: null }
const personal = { source_type: 'personal_note', source_id: 'note-a', source_version: 'r1-hash', title: '我的理解', index_status: 'ready', source_revision: 1 }
const citation = { ...course, citation_id: 'gradient:1', chunk_id: 'gradient:1', raw_md: '# 原文\n\n公式 $w$. <script>alert(1)</script>', start_line: 1, end_line: 3, section: '定义' }
const run = () => ({ request_id: 'run-1', status: 'local', question: '解释梯度下降', answer: '沿负梯度方向 $w$ 更新。[gradient:1]',
  model_calls: 0, reason: 'local_requested', created_at: '2026-10-20T08:00:00Z', updated_at: '2026-10-20T08:00:00Z',
  selected_sources: [course], source_statuses: [{ ...course, current_status: 'current' }], citations: [citation], saved_note_id: null })
function storage() { const data = new Map(); return { getItem: k => data.get(k) || null, setItem: (k,v) => data.set(k,v) } }
function client() {
  return { knowledgeSources: vi.fn().mockResolvedValue({ items: [course, personal] }), workbenchRuns: vi.fn().mockResolvedValue([]),
    workbenchCapabilities: vi.fn().mockResolvedValue({ model_enabled: true, provider: 'DeepSeek', model: 'test-model' }),
    workbenchAsk: vi.fn().mockImplementation(async (_, body) => ({ ...run(), request_id: body.request_id })),
    workbenchRun: vi.fn().mockResolvedValue(run()), openSource: vi.fn().mockResolvedValue({ ...course, raw_md: '# 当前全文' }),
    saveWorkbenchNote: vi.fn().mockResolvedValue({ note_id: 'saved-note', revision: 1, deleted: false, edited: false }) }
}
let wrapper
afterEach(() => { wrapper?.unmount(); wrapper = null; localStorage.clear() })

describe('workbench state and per-round consent', () => {
  it('selects only course defaults, preserves draft and selection across reload, never auto-posts', async () => {
    const api = client(), owner = ref('a'), store = storage()
    const w = reactive(useStudyWorkbench(api, owner, store)); await w.load()
    expect(w.chosen).toEqual([course])
    w.toggle(personal, true); w.query = '我的问题'; w.mode = 'model'; w.consent = true
    const restored = reactive(useStudyWorkbench(api, owner, store)); await restored.load()
    expect(restored.chosen).toHaveLength(2); expect(restored.query).toBe('我的问题')
    expect(restored.consent).toBe(false); expect(restored.mode).toBe('local')
    expect(api.workbenchAsk).not.toHaveBeenCalled()
  })
  it('sends explicit current consent only once and resets it when the query or choices change', async () => {
    const api = client(), w = reactive(useStudyWorkbench(api, ref('a'), storage())); await w.load()
    w.toggle(personal, true); w.mode = 'model'; w.query = '梯度下降'; w.consent = true
    await w.ask()
    expect(api.workbenchAsk.mock.calls[0][1].allow_personal_external).toBe(true)
    expect(w.consent).toBe(false)
    await w.ask()
    expect(api.workbenchAsk.mock.calls[1][1].allow_personal_external).toBe(false)
    w.consent = true; w.query = '修改问题'; expect(w.consent).toBe(false)
    w.consent = true; w.toggle(course, false); expect(w.consent).toBe(false)
  })
  it('does not submit empty selections or duplicate an uncertain paid request', async () => {
    const api = client(), store = storage(), w = reactive(useStudyWorkbench(api, ref('a'), store)); await w.load()
    w.toggle(course, false); w.query = '问题'; await w.ask(); expect(api.workbenchAsk).not.toHaveBeenCalled()
    w.toggle(course, true); api.workbenchAsk.mockRejectedValue(new ApiError('超时', { uncertain: true }))
    await w.ask(); const id = w.pendingId; expect(id).toBeTruthy()
    await w.ask(); expect(api.workbenchAsk).toHaveBeenCalledTimes(1)
    api.workbenchRun.mockResolvedValue({ ...run(), request_id: id, status: 'uncertain', reason: 'execution_unconfirmed' })
    const restored = reactive(useStudyWorkbench(api, ref('a'), store)); await restored.load()
    expect(api.workbenchRun).toHaveBeenCalledWith('a', id)
    expect(restored.pendingId).toBe(id); expect(api.workbenchAsk).toHaveBeenCalledTimes(1)
    restored.releaseUncertain(); expect(restored.pendingId).toBeNull()
  })
  it('removes changed versions instead of silently authorizing their newer contents', async () => {
    const api = client(), w = reactive(useStudyWorkbench(api, ref('a'), storage())); await w.load()
    w.toggle(personal, true); w.consent = true
    api.knowledgeSources.mockResolvedValue({ items: [course, { ...personal, source_version: 'r2-hash' }] })
    await w.load(); expect(w.chosen).toEqual([course]); expect(w.consent).toBe(false)
    expect(w.notice).toContain('重新勾选')
  })
  it('restores the original lesson version on a pending receipt without another model call', async () => {
    const api=client(), store=storage()
    store.setItem('eduagent.workbench.v1.a',JSON.stringify({pending_request_id:'run-1'}))
    const context={release_id:'old-release',release_version:2,learning_revision:0}
    api.teachingContexts=vi.fn().mockResolvedValue({items:[{request_id:'run-1',context,lesson_stale:true}]})
    const w=reactive(useStudyWorkbench(api,ref('a'),store));await w.load()
    expect(w.current.lesson_context).toEqual(context)
    expect(w.current.lesson_stale).toBe(true)
    expect(api.workbenchAsk).not.toHaveBeenCalled()
  })
  it('ignores late responses after switching demo students', async () => {
    const api = client(), owner = ref('a'), w = reactive(useStudyWorkbench(api, owner, storage())); await w.load()
    let resolve
    api.workbenchAsk.mockImplementation(() => new Promise(r => { resolve = r }))
    w.query = '问题'; const pending = w.ask(); owner.value = 'b'; resolve(run()); await pending
    expect(w.current).toBeNull(); expect(w.sources).toEqual([]); expect(w.pendingId).toBeNull()
    await w.load(); expect(api.workbenchRuns).toHaveBeenLastCalledWith('b')
  })
  it('refuses sending when browser cannot persist a request receipt', async () => {
    const api = client(), store = storage(), w = reactive(useStudyWorkbench(api, ref('a'), store)); await w.load()
    store.setItem = () => { throw new Error('quota') }; w.query = '问题'; await w.ask()
    expect(w.error).toContain('浏览器存储'); expect(api.workbenchAsk).not.toHaveBeenCalled()
  })
})

describe('workbench interface', () => {
  async function setup(api = client()) {
    const w = reactive(useStudyWorkbench(api, ref('a'), storage()))
    wrapper = mount(StudyWorkbench, { props: { workspace: w, snapshot: state(), goalNames: '逻辑回归' }, attachTo: document.body })
    await flushPromises(); return { api, w }
  }
  it('distinguishes opening from selecting, exposes local/model modes and per-round notice', async () => {
    const { api, w } = await setup()
    await wrapper.get('button[aria-label="打开资料：我的理解"]').trigger('click'); await flushPromises()
    expect(api.openSource).toHaveBeenCalled(); expect(w.chosen).toEqual([course])
    await wrapper.get('button[aria-label="关闭原文抽屉"]').trigger('click')
    await wrapper.get('input[aria-label="选择来源：我的理解"]').setValue(true)
    await wrapper.get('#wb-mode').setValue('model')
    expect(wrapper.get('.wb-consent').text()).toContain('DeepSeek')
    expect(wrapper.get('.wb-consent').text()).toContain('我的理解')
    expect(w.consent).toBe(false)
    await wrapper.get('#wb-question').setValue('梯度下降')
    await wrapper.get('.wb-question-form').trigger('submit'); await flushPromises()
    expect(api.workbenchAsk.mock.calls[0][1].allow_personal_external).toBe(false)
  })
  it('opens matching snapshot via inline citation, traps keyboard focus and restores focus on Escape', async () => {
    const { w } = await setup(); w.view(run()); await nextTick()
    const link = wrapper.get('a[href="#eduagent-citation/gradient%3A1"]')
    link.element.focus(); await link.trigger('click'); await nextTick()
    expect(wrapper.get('[role="dialog"]').text()).toContain('公式')
    expect(wrapper.get('[role="dialog"]').text()).toContain('行 1–3')
    expect(wrapper.find('script').exists()).toBe(false)
    expect(document.activeElement.getAttribute('aria-label')).toBe('关闭原文抽屉')
    await wrapper.get('[role="dialog"]').trigger('keydown', { key: 'Tab', shiftKey: true })
    expect(document.activeElement.tagName).toBe('SUMMARY')
    await wrapper.get('[role="dialog"]').trigger('keydown', { key: 'Escape' }); await nextTick()
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false); expect(document.activeElement).toBe(link.element)
  })
  it('labels a no-match model answer and restores it without another model request', async () => {
    const api = client()
    api.workbenchRuns.mockResolvedValue([{ ...run(), status: 'complete', reason: null, model_calls: 1,
      answer_basis: 'model_knowledge', citations: [], answer: '你好，可以解释其他学习问题。' }])
    const { w } = await setup(api)
    expect(wrapper.text()).toContain('以下回答来自模型自身知识')
    expect(wrapper.findAll('.wb-citation')).toHaveLength(0)
    expect(wrapper.findAll('#wb-mode option')).toHaveLength(2)
    w.mode = 'model'; await nextTick()
    expect(wrapper.text()).toContain('也可继续解释')
    expect(api.workbenchAsk).not.toHaveBeenCalled()
    await wrapper.get('.wb-history-item').trigger('click')
    expect(api.workbenchAsk).not.toHaveBeenCalled()
  })
  it('shows a specific validation error without claiming every format error is a false citation', async () => {
    const api = client()
    api.workbenchRuns.mockResolvedValue([{ ...run(), reason: 'unverified_model_answer', validation_error: 'invalid_json' }])
    await setup(api)
    expect(wrapper.text()).toContain('具体原因：返回内容不是可解析的JSON')
    expect(wrapper.text()).toContain('模型回答格式或引用未通过校验')
    expect(api.workbenchAsk).not.toHaveBeenCalled()
  })
  it('distinguishes missing body, conflicting aliases and forbidden control fields', async () => {
    const { w } = await setup()
    for (const [code, message] of [['missing_answer', '未找到可识别的回答正文字段'], ['ambiguous_fields', '相互冲突的回答字段'], ['forbidden_output_fields', '控制字段']]) {
      w.view({ ...run(), reason: 'unverified_model_answer', validation_error: code }); await nextTick()
      expect(wrapper.text()).toContain(message)
    }
  })
  it('explains truncated output and budget without retrying or showing a generic provider error', async () => {
    const api = client()
    api.workbenchCapabilities.mockResolvedValue({ model_enabled: true, provider: 'DeepSeek', model: 'test', max_output_tokens: 1500, max_model_calls: 3 })
    api.workbenchRuns.mockResolvedValue([{ ...run(), model_calls: 2, reason: 'model_output_truncated', finish_reason: 'length', max_output_tokens: 1500 }])
    const { w } = await setup(api)
    expect(wrapper.text()).toContain('回答被截断')
    expect(wrapper.text()).toContain('本轮每次输出上限：1500 token')
    expect(wrapper.text()).not.toContain('模型服务异常')
    w.mode = 'model'; await nextTick()
    expect(wrapper.text()).toContain('每次模型输出上限 1500 token')
    await wrapper.get('.wb-history-item').trigger('click')
    expect(api.workbenchAsk).not.toHaveBeenCalled()
  })
  it('explains the legacy incomplete-response receipt without guessing a truncation cause', async () => {
    const api = client()
    api.workbenchRuns.mockResolvedValue([{ ...run(), reason: 'incomplete_model_response', model_calls: 2 }])
    await setup(api)
    expect(wrapper.text()).toContain('模型未返回完整内容，具体终止原因不可用')
    expect(wrapper.text()).not.toContain('回答被截断')
    expect(api.workbenchAsk).not.toHaveBeenCalled()
  })
  it('combines source-based explanation and model supplement without a dedicated clock feature', async () => {
    const api = client()
    api.workbenchRuns.mockResolvedValue([{ ...run(), status: 'complete', reason: null, model_calls: 1,
      answer_basis: 'mixed', supplement_md: 'PCA应用包括可视化。',
      answer: '资料解释。[gradient:1]\n\n### 模型知识补充（无本地资料引用）\n\nPCA应用包括可视化。' }])
    await setup(api)
    expect(wrapper.text()).toContain('本轮结合了所选资料与模型知识')
    expect(wrapper.text()).toContain('模型知识补充（无本地资料引用）')
    expect(wrapper.text()).not.toContain('服务端时钟')
    expect(wrapper.findAll('.wb-citation')).toHaveLength(1)
    await wrapper.get('.wb-history-item').trigger('click')
    expect(api.workbenchAsk).not.toHaveBeenCalled()
  })
  it('shows stale/deleted snapshots and history without new model requests', async () => {
    const api = client(); api.workbenchRuns.mockResolvedValue([{ ...run(), source_statuses: [{ ...course, current_status: 'deleted' }] }])
    const { w } = await setup(api)
    expect(wrapper.text()).toContain('部分来源后来已修改')
    await wrapper.get('.wb-history-item').trigger('click'); await wrapper.get('.wb-citation').trigger('click'); await nextTick()
    expect(wrapper.get('[role="dialog"]').text()).toContain('软删除')
    expect(api.workbenchAsk).not.toHaveBeenCalled(); expect(w.current.request_id).toBe('run-1')
  })
  it('links Studio only to existing exercise/history and exposes small-screen panels', async () => {
    const { w } = await setup()
    const tab = wrapper.findAll('.wb-mobile-tabs button').find(b => b.text() === '学习工作室')
    await tab.trigger('click'); expect(w.panel).toBe('studio')
    expect(wrapper.get('.wb-grid').attributes('data-panel')).toBe('studio')
    await wrapper.findAll('.wb-studio-actions button')[0].trigger('click')
    expect(wrapper.emitted('navigate')[0]).toEqual(['learn'])
    expect(wrapper.findAll('button').some(b => /生成总结|学习卡片|知识导图/.test(b.text()))).toBe(false)
  })
  it('saves the answer once per click through the idempotent endpoint and opens notes for editing', async () => {
    const { api, w } = await setup(); w.view(run()); await nextTick()
    await wrapper.findAll('.wb-answer > button')[0].trigger('click'); await flushPromises()
    expect(api.saveWorkbenchNote).toHaveBeenCalledWith('a', 'run-1')
    expect(wrapper.emitted('edit-note')[0]).toEqual(['saved-note'])
    expect(w.current.saved_note_id).toBe('saved-note')
  })
  it('opens saved workbench answer in existing notes editor without losing its local drafts', async () => {
    const api = { ...learningClient(), ...notesApi(), ...client() }
    const savedId = 'dd60082c-678c-4eb6-8fb0-e6ae91e09fdd'
    api.workbenchRuns.mockResolvedValue([run()])
    api.saveWorkbenchNote.mockResolvedValue({ note_id: savedId, deleted: false })
    api.note.mockResolvedValue({ id: savedId, title: '助教回答', content_md: '$w$ 原回答', revision: 1, knowledge_point_ids: [], content_hash: 'h', index_status: 'ready',
      generation_origin: { request_id: 'run-1', original_revision: 1, generated_at: '2026-10-20T08:00:00Z', edited: false } })
    wrapper = mount(App, { props: { client: api, store: memoryStore({ student_id: 'learner-test' }) } }); await flushPromises()
    await wrapper.findAll('nav button').find(b => b.text() === 'AI伴学').trigger('click'); await flushPromises()
    await wrapper.findAll('.wb-answer > button')[0].trigger('click'); await flushPromises()
    expect(api.note).toHaveBeenCalledWith('learner-test', savedId)
    expect(wrapper.get('#note-title').element.value).toBe('助教回答')
    expect(wrapper.text()).toContain('当前为另存初版')
    await wrapper.get('#note-content').setValue('我的修改')
    expect(wrapper.text()).toContain('当前内容不代表原始回答')
  })
})
