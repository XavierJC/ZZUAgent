import { describe, it, expect, vi, afterEach } from 'vitest'
import { ref, reactive, computed, nextTick } from 'vue'
import { mount, flushPromises } from '@vue/test-utils'
import { useSelfAssessments } from '../useSelfAssessments.js'
import { useStudyGuidance } from '../useStudyGuidance.js'
import SelfAssessmentPanel from '../components/SelfAssessmentPanel.vue'
import LearningGuidancePanel from '../components/LearningGuidancePanel.vue'
import StudyGuidePanel from '../components/StudyGuidePanel.vue'
import App from '../App.vue'
import { ApiError } from '../api.js'
import { client as learningApi, memoryStore } from './fixtures.js'
import { api, storage, guidance, guideRun, course, personal } from './study-guidance-fixtures.js'

let wrapper
afterEach(() => { wrapper?.unmount(); wrapper = null; localStorage.clear() })

describe('independent self reports', () => {
  it('saves only edited rows, confidence may be null, and refreshes with reads only', async () => {
    const client = api(), store = storage(), owner = ref('a'), w = reactive(useSelfAssessments(client, owner, store)); await w.load()
    expect(w.draft.gradient_descent.level).toBeNull()
    w.draft.gradient_descent.level = 3; await w.save()
    const body = client.saveSelfAssessments.mock.calls[0][1]
    expect(body.items).toEqual([{ knowledge_id: 'gradient_descent', level: 3, confidence: null }])
    expect(body.expected_revision).toBe(0); expect(w.revision).toBe(1)
    expect(w.dirty).toBe(false); expect(w.overview.learning_revision).toBe(0)
    const restored = reactive(useSelfAssessments(client, owner, store)); await restored.load()
    expect(restored.draft.gradient_descent.level).toBe(3)
    expect(client.saveSelfAssessments).toHaveBeenCalledTimes(1); expect(client.next).not.toHaveBeenCalled()
    expect(client.tutor).not.toHaveBeenCalled(); expect(client.workbenchAsk).not.toHaveBeenCalled()
  })
  it('restores a separate self draft without altering any note storage', async () => {
    const client = api(), store = storage(), owner = ref('a'), w = reactive(useSelfAssessments(client, owner, store)); await w.load()
    store.setItem('eduagent.notes.v1.a', 'untouched')
    w.draft.gradient_descent.level = 4; w.draft.gradient_descent.confidence = 2
    const restored = reactive(useSelfAssessments(client, owner, store)); await restored.load()
    expect(restored.dirty).toBe(true); expect(restored.draft.gradient_descent.confidence).toBe(2)
    expect(store.getItem('eduagent.notes.v1.a')).toBe('untouched')
    owner.value = 'b'; await restored.load(); expect(restored.draft.gradient_descent.level).toBeNull()
  })
  it('reconciles a lost successful save using only the same request receipt', async () => {
    const client = api(), store = storage(), owner = ref('a'), w = reactive(useSelfAssessments(client, owner, store)); await w.load()
    const save = client.saveSelfAssessments.getMockImplementation()
    client.saveSelfAssessments.mockImplementation(async (...args) => { await save(...args); throw new ApiError('lost', { uncertain: true }) })
    w.draft.gradient_descent.level = 2; await w.save(); const id = w.pending.payload.request_id
    const restored = reactive(useSelfAssessments(client, owner, store)); await restored.load()
    expect(client.selfAssessmentReceipt).toHaveBeenCalledWith('a', id)
    expect(restored.pending).toBeNull(); expect(restored.revision).toBe(1)
    expect(client.saveSelfAssessments).toHaveBeenCalledTimes(1)
  })
  it('retains a conflicting draft and requires explicit read/review before a new CAS save', async () => {
    const client = api(), w = reactive(useSelfAssessments(client, ref('a'), storage())); await w.load()
    w.draft.gradient_descent.level = 3
    client.setSnapshot(guidance(2)); await w.save()
    expect(w.conflict).toBe(true); expect(w.draft.gradient_descent.level).toBe(3)
    expect(w.canGenerate).toBe(false)
    await w.readLatest(); expect(w.revision).toBe(2); expect(w.draft.gradient_descent.level).toBe(3)
    expect(client.saveSelfAssessments).toHaveBeenCalledTimes(1)
    await w.save(); expect(client.saveSelfAssessments.mock.calls[1][1].expected_revision).toBe(2)
  })
  it('blocks writes if independent draft persistence fails', async () => {
    const client = api(), store = storage(), w = reactive(useSelfAssessments(client, ref('a'), store)); await w.load()
    store.setItem = () => { throw new Error('quota') }; w.draft.gradient_descent.level = 2; await w.save()
    expect(client.saveSelfAssessments).not.toHaveBeenCalled(); expect(w.error).toContain('本机')
  })
  it('does not paint a late student response into a different demo scope', async () => {
    const client = api(), owner = ref('a'), w = reactive(useSelfAssessments(client, owner, storage())); await w.load()
    let resolve
    client.saveSelfAssessments.mockImplementation(() => new Promise(r => { resolve = r }))
    w.draft.gradient_descent.level = 2; const saving = w.save(); owner.value = 'b'
    resolve({ committed_revision: 1, current_revision: 1, items: [] }); await saving
    expect(w.overview).toBeNull(); expect(w.draft).toEqual({}); expect(w.pending).toBeNull()
  })
})

describe('guide ownership and recovery', () => {
  async function setup() {
    const client = api(), owner = ref('a'), state = ref(guidance()), chosen = ref([course, personal]), allowed = ref(true), store = storage()
    const w = reactive(useStudyGuidance(client, owner, state, chosen, allowed, store)); await w.load()
    return { client, owner, state, chosen, allowed, store, w }
  }
  it('defaults to rules with empty retrieval scope and includes both learning revisions', async () => {
    const { client, w } = await setup(); await w.generate()
    expect(client.generateStudyGuide.mock.calls[0][1]).toMatchObject({ mode: 'rules', sources: [], expected_learning_revision: 0, expected_assessment_revision: 0, allow_personal_external: false })
    expect(w.current.rules_md).toContain('本地规则')
    expect(client.next).not.toHaveBeenCalled()
  })
  it('never inherits Chat consent and clears guide consent per round and version change', async () => {
    const { client, w, state } = await setup(); const chatConsent = ref(true)
    w.mode = 'model'; expect(w.consent).toBe(false); await w.generate()
    expect(client.generateStudyGuide.mock.calls[0][1].allow_personal_external).toBe(false)
    w.consent = true; await w.generate(); expect(client.generateStudyGuide.mock.calls[1][1].allow_personal_external).toBe(true)
    expect(w.consent).toBe(false); expect(chatConsent.value).toBe(true)
    w.consent = true; state.value = guidance(1); expect(w.consent).toBe(false)
    expect(w.stale).toBe(true)
  })
  it('restores an uncertain guide by GET without repeating the paid request', async () => {
    const { client, owner, state, chosen, allowed, store, w } = await setup()
    client.generateStudyGuide.mockRejectedValue(new ApiError('timeout', { uncertain: true })); w.mode = 'model'
    await w.generate(); const id = w.pendingId; await w.generate()
    client.studyGuide.mockResolvedValue({ ...guideRun(), request_id: id, status: 'uncertain', reason: 'execution_unconfirmed' })
    const restored = reactive(useStudyGuidance(client, owner, state, chosen, allowed, store)); await restored.load()
    expect(restored.pendingId).toBe(id); expect(client.generateStudyGuide).toHaveBeenCalledTimes(1)
    expect(client.studyGuide).toHaveBeenCalledWith('a', id)
    restored.release(); expect(restored.pendingId).toBeNull()
  })
  it('blocks unsaved-state generation and rejects empty model scope', async () => {
    const { client, w, allowed, chosen } = await setup(); allowed.value = false; await w.generate()
    expect(client.generateStudyGuide).not.toHaveBeenCalled()
    allowed.value = true; chosen.value = []; w.mode = 'model'; await w.generate()
    expect(w.error).toContain('必须选择'); expect(client.generateStudyGuide).not.toHaveBeenCalled()
  })
  it('keeps an unresolved request blocked even when its source snapshot is also stale', async () => {
    const { client, w } = await setup()
    client.generateStudyGuide.mockResolvedValue({ ...guideRun(), status: 'uncertain', reason: 'model_timeout', stale_reasons: ['sources_changed'] })
    await w.generate()
    expect(w.pendingId).toBeTruthy(); expect(w.stale).toBe(true)
    await w.generate(); expect(client.generateStudyGuide).toHaveBeenCalledTimes(1)
  })
})

describe('Studio integration', () => {
  it('offers labelled keyboard form controls, comparison and server-defined existing actions', async () => {
    const client = api(), w = reactive(useSelfAssessments(client, ref('a'), storage())); await w.load()
    wrapper = mount(SelfAssessmentPanel, { props: { workspace: w } })
    await wrapper.get('#self-level-gradient_descent').setValue(3)
    await wrapper.get('#self-confidence-gradient_descent').setValue(4)
    await wrapper.get('form').trigger('submit'); await flushPromises()
    expect(w.revision).toBe(1); expect(wrapper.text()).toContain('答题与BKT保持独立')
    wrapper.unmount(); wrapper = mount(LearningGuidancePanel, { props: { overview: w.overview } })
    expect(wrapper.text()).toContain('待诊断（先验不是诊断）')
    await wrapper.get('.guide-actions button').trigger('click'); expect(wrapper.emitted('navigate')[0]).toEqual(['learn'])
  })
  it('renders saved guide Markdown/LaTeX, labels stale snapshots and opens inert citations', async () => {
    const client = api(), owner = ref('a'), state = ref(guidance()), w = reactive(useStudyGuidance(client, owner, state, ref([course]), ref(true), storage())); await w.load()
    w.current = { ...guideRun(), citations: [{ ...personal, citation_id: 'note_n1_r1:1', title: '个人笔记', raw_md: '<script>bad()</script> $w$',
      start_line: 1, end_line: 1 }], source_statuses: [{ ...personal, current_status: 'deleted' }] }
    state.value = guidance(1)
    wrapper = mount(StudyGuidePanel, { props: { workspace: w, selfWorkspace: { canGenerate: true }, capabilities: { model_enabled: true, provider: 'DeepSeek', model: 'test' } }, attachTo: document.body })
    expect(wrapper.text()).toContain('可能过期'); expect(wrapper.find('.katex').exists()).toBe(true)
    const button = wrapper.get('.wb-citation'); button.element.focus(); await button.trigger('click'); await nextTick()
    expect(wrapper.get('[role="dialog"]').text()).toContain('软删除'); expect(wrapper.find('script').exists()).toBe(false)
    await wrapper.get('[role="dialog"]').trigger('keydown', { key: 'Escape' }); await nextTick()
    expect(document.activeElement).toBe(button.element); expect(client.generateStudyGuide).not.toHaveBeenCalled()
  })
  it('saves self reports and refreshes Studio without allocating another exercise in App', async () => {
    const client = { ...learningApi(), ...api(), knowledgeSources: vi.fn().mockResolvedValue({ items: [course] }),
      workbenchRuns: vi.fn().mockResolvedValue([]), workbenchCapabilities: vi.fn().mockResolvedValue({ model_enabled: false }) }
    // Keep the existing application boot allocation, then verify no additional
    // allocation is caused by the new self-report/guide refresh paths.
    client.next = learningApi().next
    wrapper = mount(App, { props: { client, store: memoryStore({ student_id: 'learner-test' }) } }); await flushPromises()
    const assignments = client.next.mock.calls.length
    await wrapper.findAll('nav button').find(b => b.text() === '资料学习工作台').trigger('click'); await flushPromises()
    await wrapper.get('#self-level-gradient_descent').setValue(2)
    await wrapper.get('.self-panel form').trigger('submit'); await flushPromises()
    await wrapper.findAll('button').find(b => b.text() === '只读刷新学情与自评').trigger('click'); await flushPromises()
    expect(client.next).toHaveBeenCalledTimes(assignments)
    expect(client.saveSelfAssessments).toHaveBeenCalledTimes(1)
    expect(client.generateStudyGuide).not.toHaveBeenCalled()
  })
})
