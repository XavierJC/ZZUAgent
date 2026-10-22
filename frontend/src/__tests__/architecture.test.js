import { afterEach, describe, expect, it, vi } from 'vitest'
import { effectScope, reactive, ref, nextTick } from 'vue'
import { mount, flushPromises } from '@vue/test-utils'
import { useKnowledgeArchitecture } from '../useKnowledgeArchitecture.js'
import KnowledgeArchitecture from '../components/KnowledgeArchitecture.vue'
import { ApiError, createApi } from '../api.js'

const copy = x => JSON.parse(JSON.stringify(x))
const structure = () => ({ name: '机器学习体系', description: '', chapters: [{ id: 'chapter-a', title: '基础', summary: '', parent_id: null, order: 0, origins: [], review_status: 'candidate' }],
  concepts: [{ id: 'concept-a', name: '损失函数', summary: '$x^T x$ <script>alert(1)</script>', chapter_ids: ['chapter-a'], formal_knowledge_ids: [], origins: [], review_status: 'candidate' }], relations: [] })
function store() { const data = new Map(); return { getItem: k => data.get(k) || null, setItem: (k,v) => data.set(k,v) } }
function client() {
  let graph = structure(), revision = 1, published = null, status = 'editing'
  return {
    architectures: vi.fn().mockResolvedValue({ items: [{ id: 'architecture-a', title: '机器学习体系', published_version: 0, draft_status: 'editing' }] }),
    architecture: vi.fn().mockImplementation(async (_,id) => ({ id, title: graph.name, revision, published_version: published ? 1 : 0,
      draft: { status, base_version: 0, graph: copy(graph), sources: [] }, versions: published ? [{ version: 1, published_at: '2026-10-22' }] : [] })),
    createArchitecture: vi.fn().mockResolvedValue({ architecture_id: 'architecture-a', revision: 1 }),
    saveArchitecture: vi.fn().mockImplementation(async (_, id, body) => { graph = copy(body.graph); revision++; return { architecture_id: id, revision } }),
    publishArchitecture: vi.fn().mockImplementation(async (_,id) => { published = copy(graph); revision++; status = 'locked'; return { architecture_id:id,version:1,revision } }),
    forkArchitecture: vi.fn().mockImplementation(async (_,id) => { status = 'editing'; revision++; return { architecture_id:id,revision } }),
    architectureVersion: vi.fn().mockImplementation(async () => ({ version: 1, graph: copy(published), sources: [] })),
    architectureReceipt: vi.fn().mockResolvedValue({ architecture_id: 'architecture-a', revision: 2 }),
    documents: vi.fn().mockResolvedValue({ items: [{ id: 'document-a', title: '自建资料', version: { id: 'v1', file_revision: 1 }, parse: { id:'run1',status:'ready' } }] }),
    knowledge: vi.fn().mockResolvedValue([{ id: 'gradient_descent', name: '梯度下降' }]),
    conceptLearningState: vi.fn().mockResolvedValue({ concept_id:'concept-a', items: [], learning_revision:0, assessment_revision:0 }),
    extractArchitecture: vi.fn().mockResolvedValue({ batch_id: 'batch-a', architecture_id: 'architecture-a' }),
    architectureCandidates: vi.fn().mockResolvedValue({ id:'batch-a',graph:structure(),evidence:[],unclassified:[] }),
  }
}
const scopes = [], wrappers = []
function setup(api = client(), storage = store()) {
  const scope = effectScope(), student = ref('a'), w = scope.run(() => reactive(useKnowledgeArchitecture(api, student, storage)))
  scopes.push(scope); return { w, api, storage, student }
}
afterEach(() => { wrappers.splice(0).forEach(w => w.unmount()); scopes.splice(0).forEach(s => s.stop()) })

describe('architecture drafts and publication', () => {
  it('keeps unpublished candidates outside official navigation and saves before explicit publication', async () => {
    const { w, api } = setup(); await w.load(); await w.select('architecture-a')
    expect(w.published).toBeNull(); expect(w.mode).toBe('draft')
    w.draft.concepts[0].name = '已编辑'; await w.publish(); expect(api.publishArchitecture).not.toHaveBeenCalled()
    await w.save(); expect(w.dirty).toBe(false)
    await w.publish(); expect(api.publishArchitecture).not.toHaveBeenCalled()
    w.publishConsent = true; await w.publish()
    expect(w.mode).toBe('published'); expect(w.published.graph.concepts[0].name).toBe('已编辑')
    expect(api.publishArchitecture.mock.calls[0][2]).toMatchObject({ expected_revision:2,confirmed:true })
    await w.fork(); expect(w.mode).toBe('draft'); expect(w.current.draft.status).toBe('editing')
  })
  it('protects switching and restores local edits using only reads after refresh', async () => {
    const { w, api, storage } = setup(); await w.load(); await w.select('architecture-a'); w.draft.name = '本地未保存'
    await w.select('architecture-b'); expect(w.guard).toBe(true); expect(w.current.id).toBe('architecture-a')
    w.resolveGuard('cancel'); expect(w.current.id).toBe('architecture-a')
    const restored = setup(api,storage).w; await restored.load()
    expect(restored.draft.name).toBe('本地未保存'); expect(restored.dirty).toBe(true)
    expect(api.saveArchitecture).not.toHaveBeenCalled(); expect(api.publishArchitecture).not.toHaveBeenCalled()
    await w.select('architecture-b'); await w.resolveGuard('keep'); expect(w.current.id).toBe('architecture-b')
    await w.select('architecture-a'); expect(w.draft.name).toBe('本地未保存')
  })
  it('does not replace a server revision with a stale local draft', async () => {
    const { w, api, storage } = setup(); await w.load(); await w.select('architecture-a'); w.draft.name = '旧本地'
    const server = await api.architecture('a','architecture-a'); api.architecture.mockResolvedValue({ ...server,revision:9 })
    const restored = setup(api,storage).w; await restored.load()
    expect(restored.conflict).toBe(true); expect(restored.draft.name).toBe('旧本地')
    await restored.save(); expect(api.saveArchitecture).not.toHaveBeenCalled()
  })
  it('retains an unknown request and reconciles by GET rather than resubmission', async () => {
    const { w, api, storage } = setup(); await w.load(); await w.select('architecture-a'); w.draft.name = '网络中断'
    api.saveArchitecture.mockRejectedValueOnce(new ApiError('lost',{ uncertain:true }))
    await w.save(); expect(w.pending.request_id).toBeTruthy(); await w.save(); expect(api.saveArchitecture).toHaveBeenCalledTimes(1)
    const restored = setup(api,storage).w; await restored.load()
    expect(api.architectureReceipt).toHaveBeenCalledTimes(1); expect(api.saveArchitecture).toHaveBeenCalledTimes(1)
    expect(restored.draft.name).toBe('网络中断')
  })
  it('refuses writes when local receipt persistence fails', async () => {
    const api = client(), { w } = setup(api,{getItem:()=>null,setItem:()=>{throw Error('quota')}})
    await w.load(); await w.select('architecture-a'); w.draft.name = 'change'; await w.save()
    expect(api.saveArchitecture).not.toHaveBeenCalled()
  })
  it('discards late responses when changing the demonstration student', async () => {
    const { w, api, student } = setup(); await w.load()
    let resolve; api.architecture.mockReturnValueOnce(new Promise(r => { resolve = r }))
    const pending = w.select('architecture-a'); student.value = 'b'
    resolve({ id:'architecture-a',revision:1,draft:{status:'editing',graph:structure(),sources:[]},versions:[],published_version:0 })
    await pending; expect(w.current).toBeNull(); expect(w.draft).toBeNull()
  })
  it('previews before importing and never requests a model or automatic prerequisites', async () => {
    const { w, api } = setup(); await w.load(); await w.select('architecture-a'); w.chosenDocuments = ['document-a']
    const initial = copy(w.draft); await w.candidates()
    expect(w.draft).toEqual(initial); expect(w.preview).not.toBeNull(); expect(w.chosenCandidates).toEqual([])
    expect(api.extractArchitecture.mock.calls[0][2].documents).toEqual([{document_id:'document-a',version_id:'v1',run_id:'run1'}])
    const candidate = copy(structure()); candidate.concepts[0].id = 'new-concept'; candidate.concepts[0].name = '同名不合并'
    w.preview.graph = candidate; w.chosenCandidates = ['new-concept']; w.importCandidates()
    expect(w.draft.concepts).toHaveLength(2); expect(w.draft.relations).toEqual([])
    expect(api.saveArchitecture).not.toHaveBeenCalled()
  })
  it('blocks deletion of referenced nodes and reads only saved associations', async () => {
    const { w, api } = setup(); await w.load(); await w.select('architecture-a'); w.selectNode('chapter','chapter-a'); w.removeNode()
    expect(w.draft.chapters).toHaveLength(1); expect(w.error).toContain('引用')
    w.selectNode('concept','concept-a'); await flushPromises(); expect(api.conceptLearningState).toHaveBeenCalledTimes(1)
    w.draft.concepts[0].formal_knowledge_ids = ['gradient_descent']; await w.readState()
    expect(api.conceptLearningState).toHaveBeenCalledTimes(1); expect(w.notice).toContain('先保存')
    w.removeNode(); w.selectNode('chapter','chapter-a'); w.removeNode(); expect(w.draft.chapters).toHaveLength(0)
  })
  it('preserves typing that arrives while saving the earlier draft', async () => {
    const { w, api } = setup(); await w.load(); await w.select('architecture-a'); w.draft.name = 'first'
    const original = api.saveArchitecture.getMockImplementation(); let resolve
    api.saveArchitecture.mockImplementationOnce((...args) => new Promise(r => { resolve = async () => r(await original(...args)) }))
    const saving = w.save(); w.draft.name = 'second'; await resolve(); await saving
    expect(w.draft.name).toBe('second'); expect(w.dirty).toBe(true); expect(w.editRevision).toBe(2)
  })
  it('restores edited candidate preview after refresh without extracting it again', async () => {
    const { w, api, storage } = setup(); await w.load(); await w.select('architecture-a')
    w.chosenDocuments = ['document-a']; await w.candidates()
    w.preview.graph.concepts[0].name = '预览中修改'; w.chosenCandidates = ['concept-a']
    const restored = setup(api,storage).w; await restored.load()
    expect(restored.preview.graph.concepts[0].name).toBe('预览中修改'); expect(restored.chosenCandidates).toEqual(['concept-a'])
    expect(api.extractArchitecture).toHaveBeenCalledTimes(1)
  })
  it('recognizes a saved draft after a lost successful response instead of creating a false conflict', async () => {
    const { w, api, storage } = setup(); await w.load(); await w.select('architecture-a'); w.draft.name = '已提交'
    const original = api.saveArchitecture.getMockImplementation()
    api.saveArchitecture.mockImplementationOnce(async (...args) => { await original(...args); throw new ApiError('lost',{uncertain:true}) })
    await w.save(); const restored = setup(api,storage).w; await restored.load()
    expect(restored.dirty).toBe(false); expect(restored.conflict).toBe(false); expect(restored.editRevision).toBe(2)
    expect(api.saveArchitecture).toHaveBeenCalledTimes(1)
  })
})

describe('knowledge structure interface', () => {
  it('renders safe formulas and labelled controls with candidate and state boundaries', async () => {
    const { w } = setup(); await w.load(); await w.select('architecture-a'); w.selectNode('concept','concept-a')
    const wrapper = mount(KnowledgeArchitecture,{props:{workspace:w}}); wrappers.push(wrapper); await flushPromises()
    // Select again: a read refresh intentionally resets the detail selection.
    w.selectNode('concept','concept-a'); await flushPromises()
    expect(wrapper.text()).toContain('候选先修'); expect(wrapper.text()).toContain('不会为新概念创建掌握概率')
    for (const id of ['ka-new-name','ka-search','ka-name','ka-summary','ka-rel-source','ka-rel-target']) expect(wrapper.find(`label[for="${id}"]`).exists()).toBe(true)
    w.mode = 'published'; w.published = {version:1,graph:structure(),sources:[]}; await nextTick()
    expect(wrapper.find('script').exists()).toBe(false); expect(wrapper.find('.katex').exists()).toBe(true)
    expect(wrapper.text()).toContain('未关联正式知识点')
  })
  it('encodes scoped paths and PUT revisions without automatic retry', async () => {
    const fetcher = vi.fn().mockResolvedValue({ok:true,json:async()=>({})}), api = createApi(fetcher)
    await api.saveArchitecture('a/b','arch/id',{expected_revision:2,request_id:'r',graph:{}})
    expect(fetcher.mock.calls[0][0]).toContain('a%2Fb/knowledge-architectures/arch%2Fid/draft')
    expect(fetcher.mock.calls[0][1].method).toBe('PUT')
    await api.conceptLearningState('a','k','c',3,false)
    expect(fetcher.mock.calls[1][0]).toContain('draft=false&version=3')
  })
})
