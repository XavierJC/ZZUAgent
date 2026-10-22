import { computed, ref, watch } from 'vue'

const copy = value => JSON.parse(JSON.stringify(value))
export function useKnowledgeArchitecture(client, student, storage = globalThis.localStorage) {
  const items = ref([]), current = ref(null), draft = ref(null), published = ref(null), mode = ref('published')
  const baseline = ref(''), editRevision = ref(0), conflict = ref(false), busy = ref(''), error = ref(''), notice = ref('')
  const selected = ref(null), search = ref(''), preview = ref(null), chosenCandidates = ref([]), documents = ref([]), chosenDocuments = ref([])
  const formal = ref([]), learning = ref(null), pending = ref(null), guard = ref(null), publishConsent = ref(false), visible = ref(false)
  const recoveries = ref([])
  let epoch = 0, restored = false, local = { records: {} }, proceed = null
  const dirty = computed(() => Boolean(draft.value && JSON.stringify(draft.value) !== baseline.value))
  const graph = computed(() => mode.value === 'draft' ? draft.value : published.value?.graph)
  const node = computed(() => graph.value?.[selected.value?.kind === 'chapter' ? 'chapters' : 'concepts']?.find(n => n.id === selected.value?.id))
  const sources = computed(() => mode.value === 'draft' ? current.value?.draft.sources || [] : published.value?.sources || [])
  const key = () => `eduagent.architectures.v1.${student.value}`
  function persist() {
    if (!restored || !student.value) return true
    if (current.value && draft.value) local.records[current.value.id] = { graph: copy(draft.value), baseline: baseline.value, revision: editRevision.value }
    if (current.value && preview.value) { local.previews ||= {}; local.previews[current.value.id] = { batch_id: preview.value.id, graph: copy(preview.value.graph), chosen: [...chosenCandidates.value] } }
    try { storage.setItem(key(), JSON.stringify({ ...local, recoveries: recoveries.value, selected: current.value?.id, mode: mode.value, pending: pending.value })); return true }
    catch { error.value = '本机知识结构草稿无法保存，暂不提交写入。'; return false }
  }
  watch(draft, () => { publishConsent.value = false; if (restored) persist() }, { deep: true, flush: 'sync' })
  watch([preview, chosenCandidates], () => { if (restored) persist() }, { deep: true, flush: 'sync' })
  watch(student, () => {
    epoch++; restored = false; local = { records: {} }; current.value = null; draft.value = null; items.value = []; published.value = null
    selected.value = null; learning.value = null; pending.value = null; busy.value = ''; preview.value = null; chosenDocuments.value = []
    baseline.value = ''; editRevision.value = 0; conflict.value = false; error.value = ''; notice.value = ''; guard.value = null; proceed = null
    recoveries.value = []; documents.value = []; formal.value = []; publishConsent.value = false
  }, { flush: 'sync' })
  async function open(id, token = epoch, discard = false) {
    const owner = student.value, value = await client.architecture(owner, id)
    if (token !== epoch) return
    const saved = !discard && local.records[id], savedPreview = local.previews?.[id]
    current.value = value; baseline.value = JSON.stringify(value.draft.graph); editRevision.value = value.revision; conflict.value = false
    if (saved && JSON.stringify(saved.graph) !== saved.baseline && JSON.stringify(saved.graph) !== baseline.value) {
      baseline.value = saved.baseline; editRevision.value = saved.revision; conflict.value = saved.revision !== value.revision
      draft.value = copy(saved.graph)
    } else draft.value = copy(value.draft.graph)
    selected.value = null; learning.value = null; preview.value = null; chosenCandidates.value = []; publishConsent.value = false
    if (!value.published_version) { published.value = null; mode.value = 'draft' }
    else {
      const p = await client.architectureVersion(owner, id, value.published_version)
      if (token !== epoch) return
      published.value = p
    }
    if (savedPreview) {
      const candidate = await client.architectureCandidates(owner, id, savedPreview.batch_id)
      if (token !== epoch) return
      candidate.graph = copy(savedPreview.graph); preview.value = candidate; chosenCandidates.value = savedPreview.chosen || []
    }
    persist()
  }
  async function load() {
    if (!student.value || busy.value) return
    const token = epoch, owner = student.value; busy.value = 'load'; error.value = ''
    try {
      if (!restored) {
        try { local = JSON.parse(storage.getItem(key()) || 'null') || { records: {} }; local.records ||= {} } catch { local = { records: {} }; notice.value = '本机缓存无效，服务器数据仍保留。' }
        pending.value = local.pending || null; mode.value = local.mode === 'draft' ? 'draft' : 'published'; restored = true
        recoveries.value = Array.isArray(local.recoveries) ? local.recoveries.slice(-3) : []
      }
      const [list, docs, points] = await Promise.all([client.architectures(owner), client.documents(owner), client.knowledge()])
      if (token !== epoch) return
      items.value = list.items; documents.value = docs.items; formal.value = points
      let id = current.value?.id || local.selected, recoveredBatch = null
      if (pending.value) {
        try {
          const receipt = await client.architectureReceipt(owner, pending.value.request_id)
          if (token !== epoch) return
          id = receipt.architecture_id; recoveredBatch = receipt.batch_id; pending.value = null; notice.value = '原操作回执已恢复，没有重新提交。'
        } catch { if (token === epoch) notice.value = '原操作尚待核对，刷新只查询，不自动重发。' }
      }
      if (id && list.items.some(i => i.id === id)) await open(id, token)
      if (recoveredBatch && token === epoch) {
        const candidate = await client.architectureCandidates(owner, id, recoveredBatch)
        if (token === epoch) { preview.value = candidate; chosenCandidates.value = [] }
      }
      persist()
    } catch (e) { if (token === epoch) error.value = e.message }
    finally { if (token === epoch) busy.value = '' }
  }
  function navigate(action) {
    if (busy.value) return
    if (dirty.value) { proceed = action; guard.value = true } else return action()
  }
  function resolveGuard(choice) {
    if (choice === 'cancel') { guard.value = null; proceed = null; return }
    if (choice === 'keep' && !persist()) return
    if (choice === 'discard' && current.value) { delete local.records[current.value.id]; baseline.value = JSON.stringify(draft.value) }
    const next = proceed; proceed = null; guard.value = null; return next?.()
  }
  async function select(id) {
    return navigate(async () => { const token = epoch; busy.value = 'open'; error.value = ''
      try { await open(id, token) } catch (e) { if (token === epoch) error.value = e.message }
      finally { if (token === epoch) busy.value = '' } })
  }
  async function write(operation, body, action, after) {
    if (busy.value || pending.value) return false
    const token = epoch; pending.value = { request_id: body.request_id, operation, architecture_id: current.value?.id }
    if (!persist()) { pending.value = null; return false }
    busy.value = operation; error.value = ''; publishConsent.value = false
    try {
      const receipt = await action()
      if (token !== epoch) return false
      pending.value = null; await after(receipt, token)
      if (token !== epoch) return false
      persist(); return true
    } catch (e) {
      if (token !== epoch) return false
      error.value = e.message; if (!e.uncertain) pending.value = null
      if (e.status === 409) conflict.value = true
      persist(); return false
    } finally { if (token === epoch) busy.value = '' }
  }
  async function create(name) {
    if (!name.trim()) return
    return navigate(async () => {
      const owner = student.value, body = { request_id: crypto.randomUUID(), name: name.trim() }
      await write('create', body, () => client.createArchitecture(owner, body), async (r, token) => {
        const list = await client.architectures(owner); if (token !== epoch) return
        items.value = list.items; mode.value = 'draft'; await open(r.architecture_id, token)
      })
    })
  }
  async function save() {
    if (!current.value || conflict.value || mode.value !== 'draft') return false
    const owner = student.value, id = current.value.id, sent = copy(draft.value)
    const body = { request_id: crypto.randomUUID(), expected_revision: editRevision.value, graph: sent }
    return write('save', body, () => client.saveArchitecture(owner, id, body), async (r, token) => {
      const changed = JSON.stringify(draft.value) !== JSON.stringify(sent), typing = copy(draft.value)
      delete local.records[id]; await open(id, token, true)
      if (token !== epoch) return
      if (changed) { draft.value = typing; baseline.value = JSON.stringify(sent); editRevision.value = r.revision }
      notice.value = '草稿已保存，尚未发布。'
    })
  }
  async function fork() {
    if (!current.value || !published.value) return
    const owner = student.value, id = current.value.id, body = { request_id: crypto.randomUUID(), expected_revision: current.value.revision, version: published.value.version }
    return write('fork', body, () => client.forkArchitecture(owner, id, body), async (r, token) => {
      mode.value = 'draft'; delete local.records[id]; await open(id, token, true)
    })
  }
  async function publish() {
    if (!publishConsent.value || dirty.value || conflict.value) return false
    const owner = student.value, id = current.value.id, body = { request_id: crypto.randomUUID(), expected_revision: editRevision.value, confirmed: true }
    return write('publish', body, () => client.publishArchitecture(owner, id, body), async (r, token) => {
      delete local.records[id]; mode.value = 'published'; await open(id, token, true); notice.value = '已发布不可变版本；候选先修仍未确认。'
    })
  }
  async function version(number) {
    if (!current.value || busy.value) return
    const token = epoch; busy.value = 'version'
    try { const value = await client.architectureVersion(student.value, current.value.id, Number(number)); if (token === epoch) { published.value = value; mode.value = 'published'; selected.value = null; learning.value = null; persist() } }
    catch (e) { if (token === epoch) error.value = e.message }
    finally { if (token === epoch) busy.value = '' }
  }
  function selectNode(kind, id) { selected.value = { kind, id }; learning.value = null; if (kind === 'concept') readState() }
  async function readState() {
    if (!node.value || selected.value.kind !== 'concept') return
    // Unsaved formal associations cannot be presented as server-confirmed facts.
    if (mode.value === 'draft' && dirty.value) { notice.value = '先保存概念关联，再读取已有正式学情。'; return }
    const token = epoch, id = selected.value.id, architectureId = current.value.id, askedMode = mode.value, askedVersion = published.value?.version, askedRevision = editRevision.value
    try {
      const data = await client.conceptLearningState(student.value, architectureId, id, mode.value === 'draft' ? null : published.value.version, mode.value === 'draft')
      if (token === epoch && selected.value?.id === id && current.value?.id === architectureId && mode.value === askedMode && published.value?.version === askedVersion && editRevision.value === askedRevision && !(mode.value === 'draft' && dirty.value)) learning.value = data
    } catch (e) { if (token === epoch) error.value = e.message }
  }
  async function candidates() {
    if (!chosenDocuments.value.length || !current.value) return
    const owner = student.value, id = current.value.id
    const docs = chosenDocuments.value.map(key => documents.value.find(d => d.id === key)).filter(Boolean)
    const body = { request_id: crypto.randomUUID(), expected_revision: current.value.revision,
      documents: docs.map(d => ({ document_id: d.id, version_id: d.version.id, run_id: d.parse.id })) }
    return write('candidates', body, () => client.extractArchitecture(owner, id, body), async (r, token) => {
      const data = await client.architectureCandidates(owner, id, r.batch_id)
      if (token === epoch) { preview.value = data; chosenCandidates.value = []; notice.value = '仅生成候选预览，未修改或发布结构。' }
    })
  }
  function importCandidates() {
    if (!preview.value || mode.value !== 'draft' || current.value.draft.status !== 'editing') return
    const ids = new Set(chosenCandidates.value), existing = new Set(draft.value.chapters.map(c => c.id))
    const chapters = preview.value.graph.chapters.filter(c => ids.has(c.id) && !existing.has(c.id)).map(copy)
    chapters.forEach(c => existing.add(c.id)); chapters.forEach(c => { if (!existing.has(c.parent_id)) c.parent_id = null })
    const known = new Set(draft.value.concepts.map(c => c.id))
    const concepts = preview.value.graph.concepts.filter(c => ids.has(c.id) && !known.has(c.id)).map(copy)
    concepts.forEach(c => { c.chapter_ids = c.chapter_ids.filter(id => existing.has(id)) })
    draft.value = { ...draft.value, chapters: [...draft.value.chapters, ...chapters], concepts: [...draft.value.concepts, ...concepts] }
    notice.value = '候选已加入本机草稿；请编辑、保存并明确确认后发布。'
    if (local.previews) delete local.previews[current.value.id]
    preview.value = null
  }
  function addNode(kind) {
    if (!draft.value) return
    const id = crypto.randomUUID(), base = { id, summary: '', origins: [], review_status: 'candidate' }
    if (kind === 'chapter') draft.value.chapters.push({ ...base, title: '新章节', parent_id: null, order: draft.value.chapters.length })
    else draft.value.concepts.push({ ...base, name: '新概念', chapter_ids: [], formal_knowledge_ids: [] })
    selectNode(kind, id)
  }
  function removeNode() {
    const item = node.value; if (!item) return
    if (selected.value.kind === 'chapter' && (draft.value.chapters.some(c => c.parent_id === item.id) || draft.value.concepts.some(c => c.chapter_ids.includes(item.id)))) {
      error.value = '该章节仍有子章节或概念引用，请先解除引用。'; return
    }
    if (selected.value.kind === 'concept' && draft.value.relations.some(r => r.source_id === item.id || r.target_id === item.id)) {
      error.value = '该概念仍有关系列表引用，请先删除关系。'; return
    }
    const group = selected.value.kind === 'chapter' ? 'chapters' : 'concepts'
    draft.value[group] = draft.value[group].filter(n => n.id !== item.id); selected.value = null; learning.value = null
  }
  function acceptServer() {
    if (!current.value || busy.value) return
    // Retain conflict recovery before an explicit replacement with server state.
    recoveries.value = [...recoveries.value.slice(-2), { architecture_id: current.value.id, graph: copy(draft.value), revision: editRevision.value }]
    if (!persist()) return
    const token = epoch
    delete local.records[current.value.id]; open(current.value.id, token, true).catch(e => { if (token === epoch) error.value = e.message })
  }
  function restoreRecovery() {
    const previous = [...recoveries.value].reverse().find(r => r.architecture_id === current.value?.id)
    if (!previous || current.value.draft.status !== 'editing') return
    baseline.value = JSON.stringify(current.value.draft.graph); editRevision.value = current.value.revision
    draft.value = copy(previous.graph); conflict.value = false; mode.value = 'draft'
    notice.value = '恢复副本已放入本机草稿，以当前版本为基础；请检查后手动保存，不会自动发布。'
  }
  function sourceDownload(source) { return client.documentDownloadUrl(student.value, source.document_id, source.version_id) }
  function releasePending() { pending.value = null; notice.value = '已结束等待，原回执保留；新提交使用新的请求编号。'; persist() }
  return { items, current, draft, published, mode, graph, node, selected, search, baseline, editRevision, dirty, conflict, busy, error, notice,
    sources, preview, chosenCandidates, documents, chosenDocuments, formal, learning, pending, guard, publishConsent, visible,
    load, select, create, save, fork, publish, version, selectNode, readState, candidates, importCandidates, addNode, removeNode,
    persist, resolveGuard, acceptServer, restoreRecovery, recoveries, sourceDownload, releasePending }
}
