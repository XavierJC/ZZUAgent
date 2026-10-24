import { computed, ref, watch } from 'vue'
import { noteStore } from '../../noteStorage.js'

const clone = (value) => value == null ? value : JSON.parse(JSON.stringify(value))
const fields = (note) => ({ title: note.title.trim(), content_md: note.content_md,
  knowledge_point_ids: [...note.knowledge_point_ids].sort() })
const same = (first, second) => Boolean(first && second && JSON.stringify(fields(first)) === JSON.stringify(fields(second)))
const validFields = (value) => value && typeof value.id === 'string'
  && /^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$/.test(value.id)
  && typeof value.title === 'string' && typeof value.content_md === 'string'
  && Array.isArray(value.knowledge_point_ids) && value.knowledge_point_ids.every(key => typeof key === 'string')
  && Number.isInteger(value.revision) && value.revision >= 0
const validRecord = (record) => validFields(record?.draft)
  && (!record.baseline || (validFields(record.baseline) && record.baseline.id === record.draft.id))
  && (!record.pending || (['create', 'update', 'import', 'delete'].includes(record.pending.kind)
    && record.pending.id === record.draft.id && validFields(record.pending.snapshot)
    && record.pending.payload && typeof record.pending.payload === 'object'))

export function useNotesWorkspace(api, student, store = noteStore()) {
  const items = ref([]), draft = ref(null), baseline = ref(null), pending = ref(null)
  const busy = ref(''), error = ref(''), notice = ref(''), storageError = ref(''), conflict = ref(false)
  const query = ref(''), knowledge = ref(''), guard = ref(null), localDrafts = ref([])
  let generation = 0, loaded = ''
  const dirty = computed(() => Boolean(draft.value && (!baseline.value || !same(draft.value, baseline.value))))
  const status = computed(() => busy.value === 'save' || busy.value === 'import' ? '保存中'
    : pending.value ? '结果待确认' : conflict.value ? '版本冲突' : error.value ? '保存失败'
      : dirty.value ? '未保存' : draft.value ? '已保存' : '未选择笔记')
  const current = (token, owner) => generation === token && student.value === owner
  function scope() {
    const value = store.read(student.value)
    return { active_id: typeof value.active_id === 'string' ? value.active_id : null,
      records: value.records && typeof value.records === 'object' && !Array.isArray(value.records) ? value.records : {} }
  }
  function persist() {
    if (!student.value) return false
    const saved = scope()
    saved.active_id = draft.value?.id || null
    if (draft.value) {
      if (dirty.value || pending.value) saved.records[draft.value.id] = clone({ draft: draft.value, baseline: baseline.value, pending: pending.value })
      else delete saved.records[draft.value.id]
    }
    const ok = store.write(student.value, saved)
    storageError.value = ok ? '' : '本机草稿保存失败。请先复制正文，避免刷新或切换造成丢失。'
    localDrafts.value = Object.values(saved.records).filter(validRecord).map(record => ({ id: record.draft.id, title: record.draft.title }))
    return ok
  }
  function reset() {
    generation++; loaded = ''; items.value = []; draft.value = null; baseline.value = null; pending.value = null
    busy.value = ''; error.value = ''; notice.value = ''; storageError.value = ''; conflict.value = false
    guard.value = null; localDrafts.value = []; query.value = ''; knowledge.value = ''
  }
  watch(student, reset, { flush: 'sync' })
  watch(draft, () => { if (draft.value) persist() }, { deep: true })

  async function refreshList(owner = student.value, token = generation) {
    const result = await api.notes(owner, query.value, knowledge.value)
    if (current(token, owner)) items.value = result.items
  }
  async function refreshAfterWrite(owner) {
    const token = generation
    try { await refreshList(owner, token) } catch { if (current(token, owner)) notice.value += ' 列表刷新失败，可手动刷新列表。' }
  }
  function restore(record) {
    draft.value = clone(record.draft); baseline.value = clone(record.baseline); pending.value = clone(record.pending)
    conflict.value = false; error.value = ''; notice.value = '已恢复本机未完成草稿；服务器内容以保存后的版本为准。'
  }
  async function openDirect(id) {
    const token = generation, owner = student.value
    busy.value = 'open'; error.value = ''; notice.value = ''
    try {
      const record = scope().records[id]
      if (validRecord(record)) restore(record)
      else {
        const note = await api.note(owner, id)
        if (!current(token, owner)) return
        draft.value = clone(note); baseline.value = clone(note); pending.value = null; conflict.value = false
      }
      if (current(token, owner)) persist()
    } catch (exception) { if (current(token, owner)) error.value = exception.message }
    finally { if (current(token, owner)) busy.value = '' }
  }
  async function load() {
    if (!student.value || busy.value) return
    const token = generation, owner = student.value
    busy.value = 'load'; error.value = ''
    try {
      await refreshList(owner)
      if (!current(token, owner)) return
      if (loaded !== owner) {
        loaded = owner
        const saved = scope()
        localDrafts.value = Object.values(saved.records).filter(validRecord).map(record => ({ id: record.draft.id, title: record.draft.title }))
        if (saved.active_id) {
          if (validRecord(saved.records[saved.active_id])) restore(saved.records[saved.active_id])
          else {
            try {
              const note = await api.note(owner, saved.active_id)
              if (current(token, owner)) { draft.value = clone(note); baseline.value = clone(note) }
            } catch (exception) { if (exception.status !== 404) throw exception }
          }
        }
      }
    } catch (exception) { if (current(token, owner)) error.value = exception.message }
    finally { if (current(token, owner)) busy.value = '' }
  }
  function navigate(action) {
    if (busy.value) return
    if (pending.value) { error.value = '先核对未确认的保存或删除结果，再切换笔记。'; return }
    if (dirty.value) guard.value = { kind: 'leave', action }
    else return action()
  }
  function newDirect() {
    draft.value = { id: crypto.randomUUID(), title: '未命名笔记', content_md: '', knowledge_point_ids: [], revision: 0 }
    baseline.value = null; pending.value = null; conflict.value = false; error.value = ''; notice.value = ''; persist()
  }
  const newNote = () => navigate(newDirect)
  const open = (id) => navigate(() => openDirect(id))
  function finishSaved(note, operation) {
    const unchanged = same(draft.value, operation.snapshot)
    baseline.value = clone(note); pending.value = null; conflict.value = false
    if (unchanged) draft.value = clone(note)
    else draft.value = { ...draft.value, revision: note.revision, created_via: note.created_via }
    error.value = ''; notice.value = note.import_warnings?.join('；') || '服务器已保存。'
    persist()
  }
  function finishDeleted() {
    const saved = scope(), id = draft.value?.id
    if (id) delete saved.records[id]
    saved.active_id = null
    if (!store.write(student.value, saved)) storageError.value = '服务器已删除，但本机草稿清理失败；请勿重试创建旧编号。'
    draft.value = null; baseline.value = null; pending.value = null; conflict.value = false; error.value = ''
    localDrafts.value = Object.values(saved.records).filter(validRecord).map(record => ({ id: record.draft.id, title: record.draft.title }))
    notice.value = '笔记已从列表删除。'
  }
  async function execute(operation) {
    const token = generation, owner = student.value
    busy.value = operation.kind === 'import' ? 'import' : operation.kind === 'delete' ? 'delete' : 'save'
    error.value = ''; notice.value = ''
    try {
      let result
      if (operation.kind === 'create') result = await api.createNote(owner, operation.payload)
      else if (operation.kind === 'update') result = await api.updateNote(owner, operation.id, operation.payload)
      else if (operation.kind === 'import') result = await api.importNote(owner, operation.payload)
      else result = await api.deleteNote(owner, operation.id, operation.payload.expected_revision)
      if (!current(token, owner)) return
      if (operation.kind === 'delete') finishDeleted()
      else finishSaved(result, operation)
      await refreshAfterWrite(owner)
    } catch (exception) {
      if (!current(token, owner)) return
      error.value = exception.message
      if (!exception.uncertain) { pending.value = null; conflict.value = exception.status === 409; persist() }
      else notice.value = '请求结果尚未确认。请先核对服务器，重试将保留原编号和原内容。'
    } finally { if (current(token, owner)) busy.value = '' }
  }
  async function save() {
    if (busy.value || !draft.value) return
    if (pending.value) {
      if (pending.value.retryReady) { pending.value.retryReady = false; if (persist()) await execute(clone(pending.value)) }
      else await reconcile()
      return
    }
    if (conflict.value) { error.value = '请读取服务器版本或另存为新笔记，不会自动覆盖冲突。'; return }
    if (!dirty.value) return
    if (!draft.value.title.trim()) { error.value = '请填写标题。'; return }
    if (new TextEncoder().encode(draft.value.content_md).length > 65536) { error.value = '每篇笔记最多 64 KiB UTF-8 文本。'; return }
    const snapshot = clone(draft.value)
    const operation = baseline.value
      ? { kind: 'update', id: snapshot.id, payload: { expected_revision: baseline.value.revision, ...fields(snapshot) }, snapshot }
      : { kind: 'create', id: snapshot.id, payload: { id: snapshot.id, ...fields(snapshot) }, snapshot }
    pending.value = operation
    if (!persist()) { pending.value = null; return }
    await execute(clone(operation))
  }
  async function reconcile() {
    if (!pending.value || busy.value) return
    const operation = clone(pending.value), token = generation, owner = student.value
    busy.value = 'check'; error.value = ''
    try {
      const note = await api.note(owner, operation.id)
      if (!current(token, owner)) return
      if (operation.kind !== 'delete' && same(note, operation.snapshot)) {
        finishSaved(note, operation); await refreshAfterWrite(owner)
      } else if (operation.kind !== 'create' && operation.kind !== 'import'
                 && note.revision !== operation.payload.expected_revision) {
        pending.value = null; conflict.value = true; error.value = '服务器已有不同版本，本地草稿保留，请读取或另存。'; persist()
      } else {
        pending.value.retryReady = true; persist(); notice.value = '暂未确认原请求已生效，可手动重试同一请求。'
      }
    } catch (exception) {
      if (!current(token, owner)) return
      if (exception.status === 404 && operation.kind === 'delete') { finishDeleted(); await refreshAfterWrite(owner) }
      else if (exception.status === 404 && ['create', 'import'].includes(operation.kind)) {
        pending.value.retryReady = true; persist(); notice.value = '暂未找到该编号，可重试原请求，不会生成新编号。'
      } else {
        error.value = exception.message
        if (exception.status === 404) { pending.value = null; conflict.value = true; persist() }
      }
    } finally { if (current(token, owner)) busy.value = '' }
  }
  function requestDelete() {
    if (!draft.value || busy.value || pending.value) return
    guard.value = { kind: 'delete' }
  }
  async function resolveGuard(choice) {
    const entry = guard.value
    if (!entry || busy.value) return
    if (choice === 'cancel') { guard.value = null; return }
    if (entry.kind === 'delete') {
      guard.value = null
      if (!baseline.value) { finishDeleted(); return }
      const operation = { kind: 'delete', id: draft.value.id,
        payload: { expected_revision: baseline.value.revision }, snapshot: clone(draft.value) }
      pending.value = operation
      if (persist()) await execute(clone(operation))
      else pending.value = null
      return
    }
    if (choice === 'save') { await save(); if (dirty.value || pending.value || conflict.value || error.value) return }
    else if (!persist()) return
    guard.value = null; await entry.action()
  }
  function saveAsNew() {
    if (busy.value || pending.value || !draft.value) return
    draft.value = { ...draft.value, id: crypto.randomUUID(), revision: 0 }
    baseline.value = null; conflict.value = false; error.value = ''; notice.value = '已保留本地内容为新草稿，请保存。'; persist()
  }
  async function readServer() {
    if (busy.value || pending.value || !draft.value) return
    if (!persist()) return
    const saved = scope(), recovery = clone(draft.value)
    recovery.id = crypto.randomUUID(); recovery.revision = 0
    saved.records[recovery.id] = { draft: recovery, baseline: null, pending: null }
    if (!store.write(student.value, saved)) { storageError.value = '无法保留本地副本，请先复制正文。'; return }
    localDrafts.value = Object.values(saved.records).filter(validRecord).map(record => ({ id: record.draft.id, title: record.draft.title }))
    const id = draft.value.id, owner = student.value, token = generation
    busy.value = 'open'; error.value = ''
    try {
      const note = await api.note(owner, id)
      if (!current(token, owner)) return
      draft.value = clone(note); baseline.value = clone(note); conflict.value = false
      notice.value = '已读取服务器版本；本地修改已保留为本机草稿副本。'
    } catch (exception) { if (current(token, owner)) error.value = exception.message }
    finally { if (current(token, owner)) busy.value = '' }
  }
  function importFile(file) {
    if (!file) return
    return navigate(async () => {
      const owner = student.value, token = generation
      busy.value = 'import'; error.value = ''
      try {
        if (file.size > 65536) throw new Error('导入文件最多 64 KiB。')
        if (!/\.(md|markdown|txt)$/i.test(file.name)) throw new Error('只支持 Markdown/TXT 文件。')
        const bytes = new Uint8Array(await file.arrayBuffer())
        if (bytes.byteLength > 65536) throw new Error('导入文件最多 64 KiB。')
        const text = new TextDecoder('utf-8', { fatal: true }).decode(bytes).replace(/\r\n?/g, '\n')
        if (/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/.test(text)) throw new Error('文件包含异常控制字符。')
        if (!current(token, owner)) return
        const id = crypto.randomUUID(), heading = file.name.replace(/\.[^.]+$/, '').slice(0, 120)
        draft.value = { id, title: heading, content_md: text, knowledge_point_ids: [], revision: 0 }
        baseline.value = null; conflict.value = false
        const encoded = btoa(Array.from(bytes, byte => String.fromCharCode(byte)).join(''))
        const operation = { kind: 'import', id, payload: { id, file_name: file.name, content_base64: encoded }, snapshot: clone(draft.value) }
        pending.value = operation
        if (!persist()) { pending.value = null; return }
        await execute(clone(operation))
      } catch (exception) { if (current(token, owner)) error.value = exception instanceof TypeError ? '文件必须为有效 UTF-8 文本。' : exception.message }
      finally { if (current(token, owner)) busy.value = '' }
    })
  }
  return { items, draft, baseline, pending, busy, error, notice, storageError, conflict, query, knowledge,
    guard, localDrafts, dirty, status, load, save, newNote, open, navigate, resolveGuard,
    requestDelete, saveAsNew, readServer, importFile, reconcile, persist }
}
