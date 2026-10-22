import { afterEach, describe, expect, it, vi } from 'vitest'
import { effectScope, ref, reactive, nextTick } from 'vue'
import { mount, flushPromises } from '@vue/test-utils'
import { usePersonalBank } from '../usePersonalBank.js'
import PersonalBankWorkspace from '../components/PersonalBankWorkspace.vue'
import { ApiError, createApi } from '../api.js'

const copy = x => JSON.parse(JSON.stringify(x))
const payload = () => ({ number: '1', stem: '求 $x^2$ 导数 <script>window.bad=1</script>', question_type: 'single_choice', options: [{ key: 'A', text: '$2x$' }, { key: 'B', text: '$x$' }], answer: 'A', explanation: '对幂函数求导。', concepts: [] })
function store() { const m = new Map(); return { getItem: k => m.get(k) || null, setItem: (k, v) => m.set(k, v) } }
function client() {
  let row = { id: 'q1', revision: 1, payload: payload(), status: 'draft', source: {}, source_status: 'manual', duplicate_ids: [], answer_provenance: 'unknown' }
  let savedSession = null
  const resources = [{ resource_id: 'r1', title: '自建原题', status: 'active', source_version: 'v1', parse_id: null, original_source_type: 'text', original_source_id: 't1', resource_type: 'exercise_material', format: 'txt', links: [], revision: 1 }]
  const receipts = new Map()
  return {
    documentPreview: vi.fn(() => '/preview'),
    row: () => copy(row), setRevision: n => { row.revision = n },
    bank: vi.fn(async (_, path, method = 'GET', body) => {
      if (path === 'course-resources') return { items: copy(resources), knowledge: [] }
      if (path === 'course-resources/r1') return { resource: copy(resources[0]), units: [{ text: '1. 求导', location: {}, id: 'u1' }], run_id: null }
      if (path.startsWith('personal-bank/requests/')) return receipts.get(path.split('/').at(-1)) || {}
      if (path.startsWith('personal-bank/questions?')) return { items: [copy(row)] }
      if (path === 'personal-bank/questions/q1' && method === 'GET') return copy(row)
      if (path === 'personal-bank/questions/q1' && method === 'PUT') {
        row = { ...row, payload: copy(body.payload), status: body.status, revision: row.revision + 1 }
        const receipt = { question_id: 'q1', revision: row.revision }; receipts.set(body.request_id, receipt); return receipt
      }
      if (path === 'personal-bank/extractions') { const result = { question_ids: ['q1'], resource_id: 'r1' }; receipts.set(body.request_id, result); return result }
      if (path === 'personal-bank/practice' && method === 'GET') return { items: savedSession ? [copy(savedSession)] : [] }
      if (path === 'personal-bank/practice' && method === 'POST') { savedSession = { id: 's1', question_id: 'q1', question_revision: row.revision, question: payload(), source: {}, status: 'open', result: null }; return { session_id: 's1' } }
      if (path === 'personal-bank/practice/s1') return copy(savedSession)
      if (path === 'personal-bank/practice/s1/answer') { savedSession.result = { correct: true, score: 1, correct_answer: 'A', selected_answer: body.selected_answer, explanation: '解释' }; return { session_id: 's1', result: copy(savedSession.result) } }
      throw Error(`Unexpected ${method} ${path}`)
    }),
  }
}
const scopes = [], wrappers = []
function setup(api = client(), storage = store()) { const scope = effectScope(), student = ref('student-a'); scopes.push(scope); return { w: scope.run(() => reactive(usePersonalBank(api, student, storage))), api, storage, student } }
afterEach(() => { wrappers.splice(0).forEach(w => w.unmount()); scopes.splice(0).forEach(s => s.stop()) })
const writes = api => api.bank.mock.calls.filter(c => c[2] && c[2] !== 'GET')

describe('personal resource to review to practice', () => {
  it('reuses selected resource and saved parse without upload or model calls', async () => {
    const { w, api } = setup(); await w.load(); await w.selectResource(w.resources[0]); w.extractionMode = 'local'; await w.extractResource()
    expect(w.current.id).toBe('q1'); expect(w.section).toBe('bank')
    expect(writes(api)[0]).toMatchObject(['student-a', 'personal-bank/extractions', 'POST', { resource_id: 'r1', source_version: 'v1', run_id: null }])
    expect(writes(api)).toHaveLength(1)
  })
  it('saves with explicit human confirmation and starts ordinary practice only', async () => {
    const { w, api } = setup(); await w.load(); await w.open('q1'); w.editor.stem = '人工确认题干'; w.reviewed = true; w.confirmAnswer = true
    await w.save('practice'); expect(w.current.status).toBe('practice'); expect(w.dirty).toBe(false)
    expect(writes(api)[0][3]).toMatchObject({ expected_revision: 1, reviewed: true, confirm_answer: true, status: 'practice' })
    await w.start('q1'); w.selected = 'A'; await w.submit(); expect(w.session.result.correct).toBe(true)
    expect(api.bank.mock.calls.some(c => /\/next|\/answers$/.test(c[1]))).toBe(false)
  })
  it('restores an editor draft on refresh using GET only and keeps paste independently', async () => {
    const { w, api, storage } = setup(); await w.load(); await w.open('q1'); w.editor.stem = '本机修改'; w.paste = '另一个待提取原题'; await nextTick(); w.persist()
    const restored = setup(api, storage).w; await restored.load()
    expect(restored.editor.stem).toBe('本机修改'); expect(restored.paste).toBe('另一个待提取原题'); expect(restored.dirty).toBe(true); expect(writes(api)).toHaveLength(0)
  })
  it('protects independent drafts when switching questions and creating a new one', async () => {
    const { w } = setup(); await w.load(); await w.open('q1'); w.editor.stem = '保留旧草稿'; w.newQuestion(); w.editor.stem = '新草稿'; await w.open('q1')
    expect(w.editor.stem).toBe('保留旧草稿'); w.newQuestion(); expect(w.editor.stem).toBe('新草稿')
  })
  it('blocks stale draft writes across repeated refresh and allows explicit recovery', async () => {
    const { w, api, storage } = setup(); await w.load(); await w.open('q1'); w.editor.stem = '旧版本草稿'; w.persist(); api.setRevision(3)
    const restored = setup(api, storage).w; await restored.load(); expect(restored.conflict).toBe(true); await restored.save(); expect(writes(api)).toHaveLength(0)
    restored.persist(); const again = setup(api, storage).w; await again.load(); expect(again.conflict).toBe(true)
    await again.keepConflictCopy(); expect(again.conflict).toBe(false); expect(again.editor.stem).toBe(api.row().payload.stem)
    const key = Object.keys(again.drafts).find(k => k.startsWith('recovery-')); again.restoreCopy(key); expect(again.editor.stem).toBe('旧版本草稿')
  })
  it('never automatically repeats an uncertain write after refresh', async () => {
    const { w, api, storage } = setup(); await w.load(); await w.open('q1'); const original = api.bank.getMockImplementation()
    api.bank.mockImplementation(async (...args) => { if (args[2] === 'PUT') { await original(...args); throw new ApiError('断网', { uncertain: true }) } return original(...args) })
    w.editor.stem = '服务器保存后网络中断'; await w.save(); expect(w.pending.request_id).toBeTruthy()
    await w.save(); expect(writes(api)).toHaveLength(1)
    const restored = setup(api, storage).w; await restored.load(); expect(restored.pending).toBeNull(); expect(writes(api)).toHaveLength(1)
  })
  it('does not send writes when local persistence fails', async () => {
    const { w, api } = setup(client(), { getItem: () => null, setItem: () => { throw Error('quota') } }); await w.load(); w.paste = '原题'; await w.extractText(); expect(writes(api)).toHaveLength(0)
  })
  it('discards late results from a previous demonstration student', async () => {
    const { w, api, student } = setup(); await w.load(); const original = api.bank.getMockImplementation(); let release
    api.bank.mockImplementation((...args) => args[1] === 'personal-bank/questions/q1' ? new Promise(resolve => { release = resolve }) : original(...args))
    const opening = w.open('q1'); student.value = 'student-b'; release(api.row()); await opening
    expect(w.current).toBeNull(); expect(w.questions).toEqual([])
  })
  it('restores saved practice without reallocation or repeat scoring', async () => {
    const { w, api, storage } = setup(); await w.load(); await w.start('q1'); w.selected = 'A'; await w.submit(); w.persist()
    const before = writes(api).length; const restored = setup(api, storage).w; await restored.load()
    expect(restored.session.result.correct).toBe(true); expect(writes(api)).toHaveLength(before)
  })
  it('renders safe formulas and labels; unknown answers are explicitly ungraded', async () => {
    const { w } = setup(); await w.load(); await w.open('q1'); w.section = 'bank'
    const wrapper = mount(PersonalBankWorkspace, { props: { workspace: w } }); wrappers.push(wrapper); await flushPromises()
    expect(wrapper.find('script').exists()).toBe(false); expect(wrapper.find('.katex').exists()).toBe(true)
    expect(wrapper.find('label[for="pb-stem"]').text()).toContain('题干'); expect(wrapper.text()).toContain('不进入BKT')
    w.section = 'practice'; await w.start('q1'); w.session.result = { correct: null, explanation: '没有可靠答案' }; await nextTick()
    expect(wrapper.text()).toContain('不进行客观判分'); expect(wrapper.find('button[type="submit"]').exists()).toBe(false)
  })
  it('uses scoped paths and private original previews', async () => {
    const fetcher = vi.fn(async () => ({ ok: true, status: 200, json: async () => ({}) })), api = createApi(fetcher)
    await api.bank('scope a', 'personal-bank/questions', 'POST', { request_id: 'r' })
    expect(fetcher.mock.calls[0][0]).toBe('/api/v1/students/scope%20a/personal-bank/questions')
    expect(api.documentPreview('a', 'd', 'v', 2)).toBe('/api/v1/students/a/documents/d/preview?version_id=v&page=2')
  })
  it('selects a completed saved vision record directly without copying IDs or resending a model request', async () => {
    const { w, api } = setup(); const original = api.bank.getMockImplementation()
    const resource = { resource_id: 'r1', original_source_id: 'd1', original_source_type: 'document', source_version: 'v1', parse_id: 'local' }
    api.bank.mockImplementation(async (...args) => {
      const path = args[1]
      if (path === 'course-resources/r1') return { resource, units: [], run_id: 'local' }
      if (path === 'documents/d1/parse-runs') return [
        { id: 'local', version_id: 'v1', status: 'ready', current_status: 'current', mode: 'local' },
        { id: 'vision', version_id: 'v1', status: 'partial', current_status: 'current', mode: 'vision' },
        { id: 'old', version_id: 'v0', status: 'ready', current_status: 'modified', mode: 'vision' },
      ]
      if (path.startsWith('documents/d1/units?')) return { items: [{ text: '保存的原题转录' }] }
      return original(...args)
    })
    await w.load(); await w.selectResource(resource); expect(w.parseRuns.map(r => r.id)).toEqual(['local', 'vision'])
    await w.selectRun('vision'); expect(w.sourceUnits[0].text).toBe('保存的原题转录'); w.extractionMode = 'local'; await w.extractResource()
    expect(writes(api)[0][3].run_id).toBe('vision'); expect(writes(api)).toHaveLength(1)
  })
})
