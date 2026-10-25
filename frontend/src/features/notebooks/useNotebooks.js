import { computed, effectScope, onScopeDispose, reactive, ref, shallowReactive, watch } from 'vue'
import { useStudyWorkbench } from '../chat/useStudyWorkbench.js'
import { usePersonalBank } from '../practice/usePersonalBank.js'

export const notebookRef = item => ({ source_type: item.source_type, source_id: item.source_id, source_version: item.source_version })
const scopedStorage = (storage, key) => ({ getItem: name => storage.getItem(`${key}:${name}`), setItem: (name, value) => storage.setItem(`${key}:${name}`, value) })

export function useNotebooks(client, student, storage = localStorage) {
  const items = ref([]), current = ref(null), busy = ref(''), error = ref(''), notice = ref(''), pending = ref(null)
  const archived = ref(false), catalog = ref([]), entries = shallowReactive({})
  const creationDraft = ref({ title: '', description: '' })
  const scopes = new Map()
  let epoch = 0, serial = 0, restored = false, savedDrafts = {}
  const key = () => `eduagent.notebooks.v1.${student.value}`
  function persist() {
    if (!student.value) return true
    if(Object.values(entries).some(e=>e.chat?.persist()===false || e.bank?.persist()===false))return false
    try { storage.setItem(key(), JSON.stringify({ pending: pending.value, creationDraft: creationDraft.value, noteDrafts: { ...savedDrafts, ...Object.fromEntries(Object.entries(entries).map(([id, e]) => [id, e.noteDraftId])) } })); return true }
    catch { error.value = '无法保留笔记本操作编号，请先检查本机存储。'; return false }
  }
  function restore() {
    if (restored) return
    try { const saved = JSON.parse(storage.getItem(key()) || 'null'); pending.value = saved?.pending || null; savedDrafts = saved?.noteDrafts || {}; if(typeof saved?.creationDraft?.title==='string' && typeof saved?.creationDraft?.description==='string') creationDraft.value=saved.creationDraft } catch { /* Server records remain authoritative. */ }
    restored = true
  }
  function dispose() { scopes.forEach(s => s.stop()); scopes.clear(); Object.keys(entries).forEach(id => delete entries[id]) }
  onScopeDispose(dispose)
  watch(creationDraft, () => { if(restored)persist() }, { deep:true, flush:'sync' })
  watch(student, () => { epoch++; serial++; dispose(); restored = false; savedDrafts = {}; creationDraft.value={title:'',description:''}; items.value = []; current.value = null; pending.value = null; busy.value = ''; error.value = ''; notice.value = ''; catalog.value = [] }, { flush: 'sync' })

  async function load() {
    if (!student.value) return
    restore()
    const token = epoch, owner = student.value
    busy.value = 'list'; error.value = ''
    try {
      if (pending.value) {
        try { await client.notebookReceipt(owner, pending.value.body.request_id); if (token !== epoch) return; pending.value = null; persist(); notice.value = '已恢复原操作回执，没有重复提交。' }
        catch { if (token === epoch) notice.value = '原操作待核对；刷新只读取回执，不自动重新提交。' }
      }
      const result = await client.notebooks(owner, archived.value)
      if (token === epoch) items.value = result.items
    } catch (e) { if (token === epoch) error.value = e.message }
    finally { if (token === epoch) busy.value = '' }
  }

  function makeEntry(detail) {
    const scope = effectScope(true), id = detail.id
    scopes.set(id, scope)
    return scope.run(() => {
      const entry = reactive({ detail, chat: null, bank: null, noteDraftId: savedDrafts[id] || null })
      const adapter = {
        ...client, teachingContexts: undefined,
        knowledgeSources: async owner => {
          const result = await client.notebook(owner, id)
          if (owner !== student.value) return { items: [] }
          entry.detail = result
          return { items: result.sources.filter(s => s.source_type !== 'personal_question').map(s => ({ ...s, index_status: s.current_status === 'current' ? s.index_status : 'failed' })) }
        },
        workbenchRuns: owner => client.notebookRuns(owner, id),
        workbenchRun: (owner, rid) => client.notebookRun(owner, id, rid),
        workbenchAsk: (owner, body) => client.notebookAsk(owner, id, { ...body, expected_revision: entry.detail.revision }),
        openSource: (owner, body) => client.notebookPreview(owner, id, { ...body, expected_revision: entry.detail.revision }),
        saveWorkbenchNote: async (owner, rid) => {
          const result = await client.saveNotebookAnswer(owner, id, rid)
          const updated = await client.notebook(owner, id)
          if (owner === student.value) entry.detail = updated
          return result
        },
      }
      entry.chat = reactive(useStudyWorkbench(adapter, student, scopedStorage(storage, `notebook.${id}`)))
      return entry
    })
  }

  async function open(id) {
    if (!student.value || !id) return
    restore()
    const owner = student.value, token = epoch, opening = ++serial
    busy.value = 'open'; error.value = ''
    try {
      const detail = await client.notebook(owner, id)
      if (token !== epoch || opening !== serial) return
      if (!entries[id]) entries[id] = makeEntry(detail)
      else entries[id].detail = detail
      current.value = entries[id]
      return current.value
    } catch (e) { if (token === epoch && opening === serial) error.value = e.message }
    finally { if (token === epoch && opening === serial) busy.value = '' }
  }

  async function execute(kind, id, body) {
    if (pending.value || busy.value) { error.value = '请等待当前操作或先核对原回执。'; return null }
    const token = epoch, owner = student.value
    pending.value = { kind, id, body }; if (!persist()) { pending.value = null; return null }
    busy.value = 'save'; error.value = ''
    try {
      const result = await (kind === 'create' ? client.createNotebook(owner, body) : kind === 'sources' ? client.notebookSources(owner, id, body) : client.updateNotebook(owner, id, body))
      if (token !== epoch) return null
      pending.value = null; if(kind==='create')creationDraft.value={title:'',description:''}; persist(); busy.value = ''
      await load(); await open(id)
      return result
    } catch (e) { if (token === epoch) { error.value = e.message; if (!e.uncertain) pending.value = null; persist() }; return null }
    finally { if (token === epoch) busy.value = '' }
  }
  async function retry() {
    if(!pending.value || busy.value)return null
    const operation=pending.value
    pending.value=null
    // Explicit user retry uses the original id/content, never a fresh operation.
    return execute(operation.kind,operation.id,operation.body)
  }
  function create(title, description = '') {
    const id = crypto.randomUUID()
    return execute('create', id, { id, title, description, request_id: crypto.randomUUID() })
  }
  function setSources(sources) {
    if (!current.value) return
    return execute('sources', current.value.detail.id, { request_id: crypto.randomUUID(), expected_revision: current.value.detail.revision, sources: sources.map(notebookRef) })
  }
  function update(title, description, archive = false) {
    if (!current.value) return
    return execute('update', current.value.detail.id, { id: current.value.detail.id, request_id: crypto.randomUUID(), expected_revision: current.value.detail.revision, title, description, archived: archive })
  }
  async function loadCatalog() {
    const owner = student.value, token = epoch
    try { const result = await client.knowledgeSources(owner); if (token === epoch) catalog.value = result.items }
    catch (e) { if (token === epoch) error.value = e.message }
  }
  async function attach(source) {
    const refs = current.value.detail.sources.filter(s => !(s.source_type === source.source_type && s.source_id === source.source_id))
    return setSources([...refs, source])
  }
  function rememberNote(id) { if (current.value) { current.value.noteDraftId = id; persist() } }

  function practice(entry = current.value) {
    if (!entry || entry.bank) return entry?.bank
    const id = entry.detail.id
    const adapter = { ...client, bank: async (owner, path, method = 'GET', body) => {
      if (path.startsWith('personal-bank/questions?')) return client.notebookQuestions(owner, id)
      if (/^personal-bank\/questions\/[^/]+$/.test(path) && method==='GET') return client.notebookQuestion(owner, id, path.split('/').at(-1))
      if (path === 'personal-bank/practice') {
        if (method === 'GET') return client.notebookSessions(owner, id)
        if (!body.question_id) throw Error('请选择本笔记本内的一道题。')
        return client.notebookPractice(owner, id, { request_id: body.request_id, question_id: body.question_id, expected_revision: entry.detail.revision })
      }
      const session = path.match(/^personal-bank\/practice\/([^/]+)(?:\/(answer|draft))?$/)
      if (session) return session[2] === 'answer' ? client.notebookAnswer(owner, id, session[1], body) : session[2] === 'draft' ? client.notebookPracticeDraft(owner, id, session[1], body) : client.notebookSession(owner, id, session[1])
      if (path.startsWith('personal-bank/requests/')) return client.notebookPracticeReceipt(owner, id, path.split('/').at(-1))
      return client.bank(owner, path, method, body)
    } }
    entry.bank = scopes.get(id).run(() => reactive(usePersonalBank(adapter, student, scopedStorage(storage, `notebook.${id}`))))
    return entry.bank
  }
  const hasUnsaved=computed(()=>Boolean(pending.value || creationDraft.value.title || creationDraft.value.description || Object.values(entries).some(e=>e.chat?.busy==='ask' || e.chat?.pendingId || e.bank?.dirty || e.bank?.pending)))
  return { items, current, entries, creationDraft, busy, error, notice, pending, archived, catalog, hasUnsaved, load, open, create, setSources, update, retry, loadCatalog, attach, rememberNote, practice, persist }
}
