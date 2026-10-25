import { afterEach, describe, expect, it, vi } from 'vitest'
import { effectScope, reactive, ref, nextTick } from 'vue'
import { mount, flushPromises } from '@vue/test-utils'
import { useCourseDocuments } from '../useCourseDocuments.js'
import DocumentManager from '../components/DocumentManager.vue'
import { createApi, ApiError } from '../api.js'

const job = (extra = {}) => ({ id: 'job1', version_id: 'v1', mode: 'local', status: 'partial', unit_count: 1,
  model_calls: 0, current_status: 'current', parser_version: 'local-v1', created_at: '2026-10-21T00:00:00Z', ...extra })
const doc = (extra = {}) => ({ id: 'doc1', title: '自建PCA课件', source_note: '自建', revision: 1,
  version: { id: 'v1', format: 'pdf', file_revision: 1 }, parse: job(), ...extra })
const unit = () => ({ id: 'unit1', title: '第1页', text: '原文 $x$', content_md: '# 公式 $x$\n\n<script>window.executed=1</script>',
  interpretation_md: '模型解释', location: { page_number: 1 }, origin: 'local_extraction', blocks: [], warnings: ['pdf_layout_and_math_unverified'] })
function storage() { const data = new Map(); return { data, getItem: k => data.get(k) || null, setItem: (k, v) => data.set(k, v) } }
function client() {
  return {
    documents: vi.fn().mockResolvedValue({ items: [doc()] }), documentCapabilities: vi.fn().mockResolvedValue({ vision_enabled: true, vision_provider: 'DeepSeek', vision_model: 'synthetic', vision_max_output_tokens: 3000 }),
    document: vi.fn().mockResolvedValue(doc()), documentRuns: vi.fn().mockResolvedValue([job()]), documentUnits: vi.fn().mockResolvedValue({ run: job(), items: [unit()], total: 1 }),
    documentReceipt: vi.fn().mockResolvedValue({ result: doc() }), documentDownloadUrl: vi.fn().mockReturnValue('/original'),
    uploadDocument: vi.fn().mockResolvedValue(doc()), uploadDocumentVersion: vi.fn().mockResolvedValue(doc({ revision: 2 })),
    updateDocument: vi.fn().mockResolvedValue(doc()), deleteDocument: vi.fn().mockResolvedValue({ deleted: true }),
    parseDocument: vi.fn().mockResolvedValue(doc()), visionDocument: vi.fn().mockResolvedValue(job({ id: 'vision1', mode: 'vision' })),
  }
}
const scopes = [], wrappers = []
function setup(api = client(), store = storage()) {
  const scope = effectScope(), student = ref('a')
  const w = scope.run(() => reactive(useCourseDocuments(api, student, store)))
  scopes.push(scope)
  return { w, api, store, student }
}
afterEach(() => { wrappers.splice(0).forEach(w => w.unmount()); scopes.splice(0).forEach(s => s.stop()); vi.useRealTimers() })

describe('course document state and external transmission', () => {
  it('uploads only after a local-rights confirmation and keeps identity before sending', async () => {
    const { w, api, store } = setup(); await w.load()
    w.file = new File(['text'], 'a.md'); w.title = '标题'; await w.upload()
    expect(api.uploadDocument).not.toHaveBeenCalled()
    w.rights = true
    api.uploadDocument.mockImplementationOnce(async (_, file, body) => {
      const saved = JSON.parse(store.getItem('eduagent.documents.v1.a'))
      expect(saved.pending.request_id).toBe(body.request_id)
      expect(body.local_rights_confirmed).toBe(true); expect(file.name).toBe('a.md')
      return doc()
    })
    expect(await w.upload()).toBe(true); expect(w.current.id).toBe('doc1')
    expect(w.file).toBeNull(); expect(w.rights).toBe(false); expect(api.visionDocument).not.toHaveBeenCalled()
  })
  it('restores a lost response by GET receipt without uploading or paying again', async () => {
    const { w, api, store } = setup(); await w.load()
    w.file = new File(['text'], 'a.md'); w.title = '标题'; w.rights = true
    api.uploadDocument.mockRejectedValueOnce(new ApiError('网络中断', { uncertain: true }))
    await w.upload(); expect(w.pending.request_id).toBeTruthy()
    await w.upload(); expect(api.uploadDocument).toHaveBeenCalledTimes(1)
    const restored = setup(api, store).w; await restored.load()
    expect(restored.pending).toBeNull(); expect(restored.current.id).toBe('doc1')
    expect(api.uploadDocument).toHaveBeenCalledTimes(1); expect(api.visionDocument).not.toHaveBeenCalled()
    expect(restored.notice).toContain('没有重新提交')
  })
  it('keeps an unknown operation pending until a user explicitly ends waiting', async () => {
    const { w, api, store } = setup()
    store.setItem('eduagent.documents.v1.a', JSON.stringify({ pending: { request_id: 'unknown', operation: 'vision' } }))
    api.documentReceipt.mockRejectedValue(new ApiError('未知', { status: 404 }))
    await w.load(); expect(w.pending.request_id).toBe('unknown')
    w.consent = true; await w.vision(); expect(api.visionDocument).not.toHaveBeenCalled()
    w.releasePending(); expect(w.pending).toBeNull(); expect(w.notice).toContain('再次计费')
  })
  it('requires fresh per-page consent, bounds pages, and never stores consent', async () => {
    const { w, api, store } = setup(); await w.load(); await w.select('doc1')
    w.pages = '1'; await w.vision(); expect(api.visionDocument).not.toHaveBeenCalled()
    w.consent = true; await w.vision()
    expect(api.visionDocument.mock.calls[0][2]).toMatchObject({ version_id: 'v1', pages: [1], consent_external: true })
    expect(w.consent).toBe(false)
    w.consent = true; w.pages = '2'; expect(w.consent).toBe(false)
    w.pages = '1,2,3,4'; w.consent = true; await w.vision(); expect(api.visionDocument).toHaveBeenCalledTimes(1)
    const restored = setup(api, store).w; await restored.load(); expect(restored.consent).toBe(false)
    expect(store.getItem('eduagent.documents.v1.a')).not.toContain('consent')
  })
  it('does not send vision when the server capability is disabled', async () => {
    const { w, api } = setup(); await w.load(); await w.select('doc1')
    w.capabilities.vision_enabled = false; w.pages = '1'; w.consent = true
    await w.vision(); expect(api.visionDocument).not.toHaveBeenCalled()
  })
  it('refuses writes when the receipt cannot be stored', async () => {
    const { w, api } = setup(client(), { getItem: () => null, setItem: () => { throw Error('quota') } })
    w.file = new File(['text'], 'a.md'); w.title = '标题'; w.rights = true
    await w.upload(); expect(api.uploadDocument).not.toHaveBeenCalled(); expect(w.error).toContain('请求编号')
  })
  it('discards late responses after changing the demo student', async () => {
    const { w, api, student } = setup(); await w.load()
    let resolve; api.document.mockReturnValueOnce(new Promise(r => { resolve = r }))
    const opening = w.select('doc1'); student.value = 'b'; resolve(doc()); await opening
    expect(w.current).toBeNull(); expect(w.units).toEqual([]); expect(w.busy).toBe('')
    expect(api.documentUnits).not.toHaveBeenCalled()
  })
  it('preserves upload drafts and metadata edits through ordinary read refresh', async () => {
    const { w, api, store } = setup(); await w.load(); await w.select('doc1')
    w.title = '下份课件'; w.sourceNote = '待上传'; w.editTitle = '编辑尚未保存'
    await nextTick(); await w.load(); expect(w.editTitle).toBe('编辑尚未保存')
    const restored = setup(api, store).w; await restored.load()
    expect(restored.title).toBe('下份课件'); expect(restored.sourceNote).toBe('待上传')
    expect(api.updateDocument).not.toHaveBeenCalled(); expect(api.parseDocument).not.toHaveBeenCalled()
  })
  it('sends exact revisions for metadata, version, retry and soft deletion', async () => {
    const { w, api } = setup(); await w.load(); await w.select('doc1')
    w.editTitle = '新标题'; await w.saveMetadata(); expect(api.updateDocument.mock.calls[0][2].expected_revision).toBe(1)
    await w.updateVersion(new File(['x'], 'new.pdf')); expect(api.uploadDocumentVersion.mock.calls[0][3].expected_revision).toBe(1)
    await w.retry(); expect(api.parseDocument.mock.calls[0][2].expected_revision).toBe(1)
    api.documents.mockResolvedValueOnce({ items: [] }); await w.remove()
    expect(api.deleteDocument.mock.calls[0][2].expected_revision).toBe(1); expect(w.current).toBeNull()
    expect(w.notice).toContain('不会被物理清除')
  })
  it('deletes a failed document by ID without changing another document or upload draft', async () => {
    const { w, api, store } = setup(); await w.load(); await w.select('doc1')
    w.title = '未上传的草稿'; w.file = new File(['draft'], 'draft.md')
    api.deleteDocument.mockImplementationOnce(async (owner, id, body) => {
      expect(owner).toBe('a'); expect(id).toBe('failed-doc'); expect(body.expected_revision).toBe(7)
      expect(JSON.parse(store.getItem('eduagent.documents.v1.a')).pending.request_id).toBe(body.request_id)
      return { deleted: true }
    })
    expect(await w.removeById('failed-doc', 7)).toBe(true)
    expect(w.current.id).toBe('doc1'); expect(w.title).toBe('未上传的草稿'); expect(w.file.name).toBe('draft.md')
    expect(api.parseDocument).not.toHaveBeenCalled(); expect(api.visionDocument).not.toHaveBeenCalled()
  })
  it('does not issue a deletion when identity changes during revision lookup', async () => {
    const { w, api, student } = setup(); let resolve
    api.document.mockReturnValueOnce(new Promise(r => { resolve = r }))
    const removing = w.removeById('failed-doc'); student.value = 'b'; resolve(doc({ id: 'failed-doc' }))
    expect(await removing).toBe(false); expect(api.deleteDocument).not.toHaveBeenCalled(); expect(w.current).toBeNull()
  })
  it('keeps an uncertain deletion and queries its receipt without another DELETE', async () => {
    const { w, api } = setup(); await w.load()
    api.deleteDocument.mockRejectedValueOnce(new ApiError('回执丢失', { uncertain: true }))
    expect(await w.removeById('failed-doc', 1)).toBe(false); expect(w.pending.operation).toBe('delete')
    await w.removeById('failed-doc', 1); expect(api.deleteDocument).toHaveBeenCalledTimes(1)
    api.documentReceipt.mockResolvedValueOnce({ result: { id: 'failed-doc', deleted: true } })
    await w.load(); expect(w.pending).toBeNull(); expect(api.deleteDocument).toHaveBeenCalledTimes(1)
  })
})

describe('document presentation and HTTP adapter', () => {
  it('renders page position, safe Markdown, formulas and warnings with labelled inputs', async () => {
    const { w } = setup(); await w.load(); await w.select('doc1')
    const wrapper = mount(DocumentManager, { props: { workspace: w } }); wrappers.push(wrapper); await flushPromises()
    expect(wrapper.text()).toContain('PDF第1页'); expect(wrapper.text()).toContain('复杂公式尚未核验')
    expect(wrapper.find('.katex').exists()).toBe(true); expect(wrapper.find('script').exists()).toBe(false)
    for (const id of ['doc-file', 'doc-title', 'doc-source', 'doc-edit-title', 'doc-pages', 'doc-run']) {
      expect(wrapper.find(`label[for="${id}"]`).exists()).toBe(true)
    }
    expect(wrapper.text()).toContain('可读解析内容可直接问答')
    const submit = wrapper.findAll('button').find(b => b.text().includes('上传并本地解析'))
    expect(submit.attributes('disabled')).toBeDefined()
  })
  it('uses browser multipart boundaries and scoped download/query parameters', async () => {
    const fetcher = vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) }), api = createApi(fetcher)
    await api.uploadDocument('a/b', new File(['x'], 'x.md'), { request_id: 'r' })
    const [path, options] = fetcher.mock.calls[0]
    expect(path).toContain('/a%2Fb/documents'); expect(options.body).toBeInstanceOf(FormData)
    expect(options.headers).not.toHaveProperty('Content-Type'); expect(JSON.parse(options.body.get('metadata')).request_id).toBe('r')
    await api.documentUnits('a', 'd/id', 'r&x', 10)
    expect(fetcher.mock.calls[1][0]).toContain('d%2Fid/units?run_id=r%26x&offset=10')
    expect(api.documentDownloadUrl('a', 'd', 'v?1')).toContain('version_id=v%3F1')
  })
})
