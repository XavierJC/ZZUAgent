import { computed, ref, watch } from 'vue'

export function useCourseDocuments(client, student, storage = globalThis.localStorage) {
  const items = ref([]), current = ref(null), runs = ref([]), units = ref([]), run = ref(null), total = ref(0), offset = ref(0)
  const busy = ref(''), error = ref(''), notice = ref(''), capabilities = ref(null), visible = ref(false), pending = ref(null)
  const file = ref(null), title = ref(''), sourceNote = ref(''), rights = ref(false), pages = ref(''), consent = ref(false)
  const editTitle = ref(''), editSource = ref('')
  let epoch = 0, restored = false
  const activeJobs = computed(() => runs.value.some(r => ['pending', 'processing'].includes(r.status)) ||
    items.value.some(d => ['pending', 'processing'].includes(d.parse?.status)))
  const key = () => `eduagent.documents.v1.${student.value}`
  function persist() {
    try {
      storage.setItem(key(), JSON.stringify({ pending: pending.value, selected: current.value?.id || null,
        draft: { title: title.value, sourceNote: sourceNote.value } }))
      return true
    } catch { error.value = '无法保留请求编号，请检查浏览器存储；暂不发送写入请求。'; return false }
  }
  watch([title, sourceNote], () => { if (restored && student.value) persist() })
  watch([pages, current], () => { consent.value = false }, { flush: 'sync' })
  watch(student, () => {
    epoch++; restored = false; items.value = []; current.value = null; runs.value = []; units.value = []; run.value = null
    file.value = null; pending.value = null; title.value = ''; sourceNote.value = ''; rights.value = false; pages.value = ''
    consent.value = false; error.value = ''; notice.value = ''; busy.value = ''
  }, { flush: 'sync' })

  async function open(id, token = epoch) {
    const owner = student.value
    const [document, history] = await Promise.all([client.document(owner, id), client.documentRuns(owner, id)])
    if (token !== epoch) return
    const previousId = current.value?.id
    const keepEdit = previousId === id && (editTitle.value !== current.value.title || editSource.value !== current.value.source_note)
    current.value = document; runs.value = history
    if (!keepEdit) { editTitle.value = document.title; editSource.value = document.source_note }
    const selectedRun = previousId === id && history.find(r => r.id === run.value?.id)
    run.value = selectedRun || document.parse
    offset.value = 0
    await readUnits(run.value.id, token)
    persist()
  }
  async function readUnits(runId = run.value?.id, token = epoch) {
    if (!current.value || !runId) return
    const result = await client.documentUnits(student.value, current.value.id, runId, offset.value)
    if (token !== epoch) return
    run.value = result.run; units.value = result.items; total.value = result.total
  }
  async function load() {
    if (!student.value || busy.value) return
    const token = epoch, owner = student.value
    busy.value = 'load'; error.value = ''
    try {
      let saved
      if (!restored) {
        try { saved = JSON.parse(storage.getItem(key()) || 'null') } catch { notice.value = '本机页面状态无法恢复，服务器资料仍保留。' }
        pending.value = saved?.pending || null
        title.value = saved?.draft?.title?.slice(0, 120) || ''; sourceNote.value = saved?.draft?.sourceNote?.slice(0, 500) || ''
        restored = true
      }
      const [list, config] = await Promise.all([client.documents(owner), client.documentCapabilities(owner)])
      if (token !== epoch) return
      items.value = list.items; capabilities.value = config
      if (pending.value) {
        try {
          const receipt = await client.documentReceipt(owner, pending.value.request_id)
          if (token !== epoch) return
          pending.value = null
          notice.value = '已恢复服务器操作回执；没有重新提交文件或调用模型。'
          saved = { selected: receipt.result.document_id || receipt.result.id }
        } catch { if (token === epoch) notice.value = '原请求仍待核对；刷新只查询，不自动重发。' }
      }
      const id = current.value?.id || saved?.selected
      if (id && list.items.some(d => d.id === id)) await open(id, token)
      else { current.value = null; runs.value = []; units.value = []; run.value = null }
      persist()
    } catch (e) { if (token === epoch) error.value = e.message }
    finally { if (token === epoch) busy.value = '' }
  }
  async function select(id) {
    if (busy.value) return
    const token = epoch
    busy.value = 'open'; error.value = ''
    try { await open(id, token) } catch (e) { if (token === epoch) error.value = e.message }
    finally { if (token === epoch) busy.value = '' }
  }
  async function selectRun(id) {
    if (busy.value) return
    const token = epoch
    busy.value = 'units'; error.value = ''; offset.value = 0
    try { await readUnits(id, token) } catch (e) { if (token === epoch) error.value = e.message }
    finally { if (token === epoch) busy.value = '' }
  }
  async function page(direction) {
    if (busy.value) return
    const token = epoch
    busy.value = 'units'; error.value = ''; offset.value = Math.max(0, offset.value + direction * 10)
    try { await readUnits(run.value.id, token) } catch (e) { if (token === epoch) error.value = e.message }
    finally { if (token === epoch) busy.value = '' }
  }
  async function write(operation, action, requestId, after) {
    if (busy.value || pending.value) return false
    const token = epoch
    pending.value = { request_id: requestId, operation }
    if (!persist()) { pending.value = null; return false }
    busy.value = operation; error.value = ''; notice.value = ''; consent.value = false
    try {
      const result = await action()
      if (token !== epoch) return false
      pending.value = null
      await after?.(result, token)
      if (token !== epoch) return false
      persist()
      return true
    } catch (e) {
      if (token !== epoch) return false
      error.value = e.message
      if (!e.uncertain) pending.value = null
      else notice.value = '操作编号已保留。请查询原回执，视觉解析不会自动重发。'
      persist(); return false
    } finally { if (token === epoch) busy.value = '' }
  }
  async function refreshAfter(id) {
    const token = epoch, owner = student.value
    const list = await client.documents(owner)
    if (token !== epoch) return
    items.value = list.items
    if (id) await open(id, token)
  }
  async function upload() {
    if (!file.value || !rights.value || !title.value.trim()) return false
    const owner = student.value, id = crypto.randomUUID(), selected = file.value
    return write('upload', () => client.uploadDocument(owner, selected, { request_id: id, title: title.value.trim(),
      source_note: sourceNote.value, local_rights_confirmed: true, course_id: 'machine_learning', material_role: 'teaching_slides' }), id,
      async result => { file.value = null; title.value = ''; sourceNote.value = ''; rights.value = false
        notice.value = '原件已保存，正在本地解析；可读内容就绪后即可问答，上传不会外发。'; await refreshAfter(result.id) })
  }
  async function updateVersion(selected) {
    if (!selected || !current.value) return
    const owner = student.value, doc = current.value, id = crypto.randomUUID()
    return write('version', () => client.uploadDocumentVersion(owner, doc.id, selected, { request_id: id,
      expected_revision: doc.revision, course_id: 'machine_learning' }), id,
      async result => { notice.value = '新文件已保存，旧解析不再代表当前版本。'; await refreshAfter(result.id) })
  }
  async function saveMetadata() {
    if (!current.value || !editTitle.value.trim()) return
    const owner = student.value, doc = current.value, id = crypto.randomUUID()
    return write('update', () => client.updateDocument(owner, doc.id, { request_id: id, expected_revision: doc.revision,
      title: editTitle.value.trim(), source_note: editSource.value }), id,
      async result => { notice.value = '资料信息已保存。'; await refreshAfter(result.id) })
  }
  async function remove() {
    const owner = student.value, doc = current.value, id = crypto.randomUUID()
    return write('delete', () => client.deleteDocument(owner, doc.id, { request_id: id, expected_revision: doc.revision }), id,
      async () => { current.value = null; units.value = []; runs.value = []; run.value = null
        await refreshAfter(); notice.value = '资料已软删除；本机原件、历史版本及备份不会被物理清除。' })
  }
  async function retry() {
    const owner = student.value, doc = current.value, id = crypto.randomUUID()
    return write('parse', () => client.parseDocument(owner, doc.id, { request_id: id, expected_revision: doc.revision }), id,
      async () => { run.value = null; await refreshAfter(doc.id); notice.value = '已创建新的本地解析任务。' })
  }
  async function vision() {
    if (!consent.value || !capabilities.value?.vision_enabled || !current.value) return false
    const values = pages.value.split(/[,，\s]+/).filter(Boolean)
    if (!values.length || values.some(v => !/^\d+$/.test(v)) || values.length > 3 || new Set(values).size !== values.length) {
      error.value = '请输入1～3个不同页码，例如1,2。'; return false
    }
    const owner = student.value, doc = current.value, id = crypto.randomUUID()
    return write('vision', () => client.visionDocument(owner, doc.id, { request_id: id, expected_revision: doc.revision,
      version_id: doc.version.id, pages: values.map(Number), consent_external: true }), id,
      async (result, token) => { notice.value = '本轮页面识别已排队，查看状态不会重复调用模型。'; await refreshAfter(doc.id); if (token === epoch) await readUnits(result.id, token) })
  }
  function releasePending() {
    pending.value = null; notice.value = '已结束等待，原记录仍保留；新视觉请求可能再次计费。'; persist()
  }
  const download = computed(() => current.value ? client.documentDownloadUrl(student.value, current.value.id, current.value.version.id) : '')
  return { supported: typeof client.documents === 'function', items, current, runs, units, run, total, offset, busy, error, notice, capabilities, visible, pending, file, title,
    sourceNote, rights, pages, consent, editTitle, editSource, activeJobs, download, load, select, selectRun, page,
    upload, updateVersion, saveMetadata, remove, retry, vision, releasePending }
}
