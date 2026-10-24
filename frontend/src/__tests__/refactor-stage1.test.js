import { afterEach, describe, expect, it, vi } from 'vitest'
import { effectScope, nextTick, reactive, ref, watch } from 'vue'
import { mount } from '@vue/test-utils'
import App from '../App.vue'
import { createFeatureRegistry } from '../app/featureRegistry.js'
import { courseSpaceKey } from '../app/courseSpace.js'
import { useResourceLibrary } from '../features/materials/useResourceLibrary.js'
import { useNotesWorkspace } from '../features/notes/useNotesWorkspace.js'
import { settleCoursePage } from './course-page-testing.js'
import { client, memoryStore } from './fixtures.js'
import { notesApi, notesStore, deferred, note } from './notes-fixtures.js'

const cleanups = []
afterEach(() => { cleanups.splice(0).reverse().forEach(fn => fn()); localStorage.clear() })
const memory = () => { const data = new Map(); return { getItem: k => data.get(k) || null, setItem: (k, v) => data.set(k, v) } }
const source = { source_type: 'course_material', source_id: 'linear', source_version: 'v1', title: '课程说明', index_status: 'ready' }
function apiFixture() {
  return {
    ...client(), ...notesApi(),
    knowledgeSources: vi.fn(async () => ({ items: [source] })),
    workbenchCapabilities: vi.fn(async () => ({ model_enabled: true, provider: 'mock', model: 'test' })),
    workbenchRuns: vi.fn(async () => []), workbenchRun: vi.fn(), workbenchAsk: vi.fn(),
    documents: vi.fn(async () => ({ items: [] })), documentCapabilities: vi.fn(async () => ({})),
    learningGuidance: vi.fn(async () => ({ items: [], recommendations: [], assessment_revision: 0, learning_revision: 0, snapshot_hash: 'snapshot', versions: { bkt: 'test', knowledge: 'test', rules: 'test' } })),
    selfAssessmentHistory: vi.fn(async () => ({ items: [] })), studyGuides: vi.fn(async () => []),
    courseBuilder: vi.fn(), architectures: vi.fn(),
    bank: vi.fn(async (_id, path) => path === 'course-resources' ? { items: [], knowledge: [] } : { items: [] }),
  }
}
async function open(page = 'study', api = apiFixture()) {
  history.replaceState(null, '', '/#/' + page)
  const wrapper = mount(App, { props: { client: api, store: memoryStore({ student_id: 'learner-test' }), notesStore: notesStore() } })
  cleanups.push(() => wrapper.unmount())
  await settleCoursePage()
  return { wrapper, api, space: wrapper.findComponent({ name: 'CoursePage' }).vm.$.provides[courseSpaceKey] }
}
const nav = (w, label) => w.findAll('nav button').find(b => b.text() === label)

describe('feature lifetime and module boundaries', () => {
  it('creates state only on use, retains it on revisits, and peeks/guards create nothing', () => {
    const create = vi.fn(() => ({ draft: 'first' }))
    const r = createFeatureRegistry({}, { notes: { create } })
    cleanups.push(r.dispose)
    expect(r.peek('notes')).toBeUndefined(); expect(r.persist()).toBe(true); expect(r.hasUnsaved()).toBe(false)
    expect(create).not.toHaveBeenCalled()
    r.use('notes').draft = 'retained'
    expect(r.use('notes').draft).toBe('retained'); expect(create).toHaveBeenCalledTimes(1)
  })
  it('blocks navigation on storage failure and stops retained effects at final disposal', async () => {
    const owner = ref('a'), seen = vi.fn(), persist = vi.fn(() => false)
    const r = createFeatureRegistry({}, { notes: {
      create: () => { watch(owner, seen); return { persist, dirty: true } },
      needsSave: s => s.dirty, hasUnsaved: s => s.dirty,
    } })
    r.use('notes'); expect(r.persist()).toBe(false); expect(r.hasUnsaved()).toBe(true)
    owner.value = 'b'; await nextTick(); expect(seen).toHaveBeenCalledTimes(1)
    r.dispose(); owner.value = 'c'; await nextTick(); expect(seen).toHaveBeenCalledTimes(1)
    expect(() => r.use('notes')).toThrow('已关闭')
  })
  it('rejects feature dependency cycles without publishing a partially created module', () => {
    const r = createFeatureRegistry({}, { a: { create: c => c.use('b') }, b: { create: c => c.use('a') } })
    expect(() => r.use('a')).toThrow('循环依赖'); expect(Object.keys(r.states)).toEqual([]); r.dispose()
  })
  it('opens study without initializing practice, notes, guides or authoring requests', async () => {
    const { wrapper, api, space } = await open()
    expect(wrapper.find('.study-workbench').exists()).toBe(true)
    expect(Object.keys(space.features).sort()).toEqual(['assessment', 'chat', 'documents'])
    expect(api.bank).not.toHaveBeenCalled(); expect(api.notes).not.toHaveBeenCalled()
    expect(api.studyGuides).not.toHaveBeenCalled(); expect(api.courseBuilder).not.toHaveBeenCalled(); expect(api.architectures).not.toHaveBeenCalled()
    expect(api.next).not.toHaveBeenCalled(); expect(api.workbenchAsk).not.toHaveBeenCalled()
  })
  it('opens progress without reading chat history, personal sources, documents or practice', async () => {
    const { wrapper, api, space } = await open('insights')
    expect(wrapper.find('.progress-summary').exists()).toBe(true)
    expect(Object.keys(space.features).sort()).toEqual(['assessment', 'guides'])
    expect(api.knowledgeSources).not.toHaveBeenCalled(); expect(api.workbenchRuns).not.toHaveBeenCalled()
    expect(api.documents).not.toHaveBeenCalled(); expect(api.bank).not.toHaveBeenCalled(); expect(api.notes).not.toHaveBeenCalled()
    expect(api.studyGuides).toHaveBeenCalled(); expect(api.workbenchAsk).not.toHaveBeenCalled()
  })
  it('retains source selection/question draft across page chunks, browser back and refresh reads', async () => {
    const { wrapper, api, space } = await open()
    await wrapper.get('#wb-question').setValue('保留当前学习问题')
    const original = space.features.chat
    await nav(wrapper, '学习进度').trigger('click'); await settleCoursePage()
    expect(wrapper.find('#wb-question').exists()).toBe(false)
    history.replaceState(null, '', '/#/study'); window.dispatchEvent(new PopStateEvent('popstate')); await settleCoursePage()
    expect(space.features.chat).toBe(original)
    expect(wrapper.get('#wb-question').element.value).toBe('保留当前学习问题')
    expect(wrapper.get('[aria-label="选择来源：课程说明"]').element.checked).toBe(true)
    await wrapper.get('[aria-label="刷新学习记录"]').trigger('click'); await settleCoursePage()
    expect(wrapper.get('#wb-question').element.value).toBe('保留当前学习问题')
    expect(api.workbenchAsk).not.toHaveBeenCalled(); expect(api.next).not.toHaveBeenCalled(); expect(api.submit).not.toHaveBeenCalled()
  })
  it('retains a selected upload locally across unrelated page unmounts', async () => {
    const { wrapper, space } = await open()
    const file = new File(['synthetic'], 'example.txt')
    space.features.documents.file = file
    await nav(wrapper, '学习进度').trigger('click'); await settleCoursePage()
    await nav(wrapper, '资料学习').trigger('click'); await settleCoursePage()
    expect(space.features.documents.file).toBe(file)
    expect(space.features.documents.consent).toBe(false)
  })
  it('consumes a study navigation intent once and does not overwrite a later question', async () => {
    const { wrapper, space, api } = await open('study?question=准备一个问题&knowledge=gradient_descent')
    expect(wrapper.get('#wb-question').element.value).toBe('准备一个问题')
    expect(location.hash).toBe('#/study')
    await wrapper.get('#wb-question').setValue('后来输入的问题')
    await space.refreshCurrent(); await settleCoursePage()
    expect(wrapper.get('#wb-question').element.value).toBe('后来输入的问题'); expect(api.workbenchAsk).not.toHaveBeenCalled()
  })
  it('does not leak a note or a late note response across a synchronous student change', async () => {
    const owner = ref('a'), api = notesApi(), wait = deferred(), scope = effectScope()
    cleanups.push(() => scope.stop())
    const notes = scope.run(() => reactive(useNotesWorkspace(api, owner, notesStore())))
    notes.newNote(); notes.draft.content_md = 'student a private draft'
    api.note.mockReturnValueOnce(wait.promise)
    const reading = notes.open('12345678-1234-1234-1234-123456789abc')
    owner.value = 'b'
    expect(notes.draft).toBeNull()
    wait.resolve(note()); await reading; expect(notes.draft).toBeNull()
  })
})

function libraryFixture() {
  const row = { resource_id: 'resource-a', original_source_type: 'document', original_source_id: 'doc-a', source_version: 'v1', revision: 1, resource_type: 'teaching_material', links: [], status: 'active', title: '合成资料' }
  const api = { courseResources: vi.fn(async () => ({ items: [row], knowledge: [] })), courseResource: vi.fn(async () => ({ resource: { ...row }, units: [] })), saveCourseResource: vi.fn(), resourceReceipt: vi.fn() }
  const owner = ref('a'), storage = memory(), scope = effectScope()
  cleanups.push(() => scope.stop())
  const create = () => scope.run(() => reactive(useResourceLibrary(api, owner, storage)))
  return { api, owner, create, row, storage, w: create() }
}
describe('independent material catalogue', () => {
  it('opens the legacy resource route without initializing question or practice state', async () => {
    const api = apiFixture()
    const { wrapper, space } = await open('resources', api)
    expect(wrapper.text()).toContain('学习资料')
    expect(Object.keys(space.features)).toEqual(['library'])
    expect(api.bank.mock.calls.map(call => call[1])).toEqual(['course-resources'])
    expect(api.notes).not.toHaveBeenCalled(); expect(api.documents).not.toHaveBeenCalled()
  })
  it('reads catalogue without question/session endpoints and restores association drafts independently', async () => {
    const { w, create, row, api } = libraryFixture()
    await w.load(); await w.selectResource(row); w.editor.resource_type = 'exercise_material'; w.persist()
    const restored = create(); await restored.load()
    expect(restored.editor.resource_type).toBe('exercise_material'); expect(restored.dirty).toBe(true)
    expect(api.courseResources).toHaveBeenCalled(); expect(api.saveCourseResource).not.toHaveBeenCalled()
    await restored.selectResource({ ...row, resource_id: 'other' }); expect(restored.resource.resource_id).toBe(row.resource_id)
  })
  it('rejects a late detail response after switching students', async () => {
    const { w, row, owner, api } = libraryFixture(), wait = deferred()
    await w.load(); api.courseResource.mockReturnValueOnce(wait.promise)
    const reading = w.selectResource(row); owner.value = 'b'
    wait.resolve({ resource: row, units: [{ text: 'a private unit' }] }); await reading
    expect(w.resource).toBeNull(); expect(w.sourceUnits).toEqual([])
  })
  it('preserves typing during an association save instead of marking later edits as saved', async () => {
    const { w, row, api } = libraryFixture(), wait = deferred()
    await w.load(); await w.selectResource(row); w.editor.resource_type = 'exercise_material'
    api.saveCourseResource.mockReturnValueOnce(wait.promise)
    api.courseResource.mockResolvedValueOnce({ resource: { ...row, revision: 2, resource_type: 'exercise_material' }, units: [] })
    const saving = w.saveLinks(); w.editor.resource_type = 'reference'; wait.resolve({}); await saving
    expect(w.editor.resource_type).toBe('reference'); expect(w.editor.expected_revision).toBe(2); expect(w.dirty).toBe(true)
    expect(api.saveCourseResource.mock.calls[0][2].resource_type).toBe('exercise_material')
  })
  it('keeps uncertain association requests and only queries their original receipt after reload', async () => {
    const { w, row, api, create } = libraryFixture()
    await w.load(); await w.selectResource(row); w.editor.resource_type = 'reference'
    api.saveCourseResource.mockRejectedValueOnce(Object.assign(Error('lost'), { uncertain: true }))
    await w.saveLinks(); const id = w.pending.request_id
    api.resourceReceipt.mockRejectedValueOnce(Error('not confirmed'))
    const restored = create(); await restored.load()
    expect(restored.pending.request_id).toBe(id); expect(restored.editor.resource_type).toBe('reference')
    expect(api.saveCourseResource).toHaveBeenCalledTimes(1); expect(api.resourceReceipt).toHaveBeenCalledWith('a', id)
  })
  it('retains an explicit recovery copy when reading a newer resource after a conflict', async () => {
    const { w, row, api, create } = libraryFixture()
    await w.load(); await w.selectResource(row); w.editor.resource_type = 'reference'
    api.courseResource.mockResolvedValue({ resource: { ...row, revision: 2 }, units: [] })
    await w.readServer(); expect(w.dirty).toBe(false); expect(w.recoveries).toHaveLength(1)
    const restored = create(); await restored.load()
    expect(restored.editor.expected_revision).toBe(2)
    restored.restoreCopy(restored.recoveries[0]); expect(restored.editor.resource_type).toBe('reference')
    expect(restored.editor.expected_revision).toBe(1); expect(restored.dirty).toBe(true)
    expect(api.saveCourseResource).not.toHaveBeenCalled()
  })
})
