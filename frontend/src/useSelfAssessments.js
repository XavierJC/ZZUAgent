import { computed, ref, watch } from 'vue'

const clone = value => JSON.parse(JSON.stringify(value))
const fields = value => ({ level: value?.level ?? null, confidence: value?.confidence ?? null })
const same = (a, b) => JSON.stringify(fields(a)) === JSON.stringify(fields(b))
const valid = map => map && typeof map === 'object' && !Array.isArray(map) && Object.keys(map).length <= 5
  && Object.values(map).every(v => v && (v.level === null || Number.isInteger(v.level) && v.level >= 1 && v.level <= 4)
    && (v.confidence === null || Number.isInteger(v.confidence) && v.confidence >= 1 && v.confidence <= 5))

export function useSelfAssessments(client, student, storage = globalThis.localStorage) {
  const overview = ref(null), draft = ref({}), baseline = ref({}), revision = ref(0), history = ref([])
  const pending = ref(null), busy = ref(''), error = ref(''), notice = ref(''), conflict = ref(false)
  let epoch = 0, initialized = false
  const dirty = computed(() => Object.keys(draft.value).some(key => !same(draft.value[key], baseline.value[key])))
  const canGenerate = computed(() => !!overview.value && !dirty.value && !pending.value && !conflict.value && !busy.value)
  const masterySnapshot = computed(() => overview.value ? { threshold: overview.value.threshold, mastery: overview.value.items.map(p => ({
    knowledge_id: p.knowledge_id, name: p.name, probability: p.objective.probability ?? p.objective.prior_probability,
    attempts: p.objective.attempts, has_evidence: p.objective.has_evidence })) } : null)
  const status = computed(() => busy.value === 'save' ? '保存中' : pending.value ? '结果待确认' : conflict.value ? '版本冲突' : dirty.value ? '未保存自评' : revision.value ? '已保存自评' : '尚未填写自评')
  function persist() {
    if (!initialized || !student.value) return true
    try { storage.setItem(`eduagent.self.v1.${student.value}`, JSON.stringify({ draft: draft.value, baseline: baseline.value,
      revision: revision.value, pending: pending.value, conflict: conflict.value })); return true }
    catch { error.value = '自评草稿或提交编号无法保存在本机，请先保留内容；暂不发送保存。'; return false }
  }
  watch(draft, persist, { deep: true, flush: 'sync' })
  watch(student, () => { epoch++; initialized = false; overview.value = null; draft.value = {}; baseline.value = {}; revision.value = 0
    history.value = []; pending.value = null; busy.value = ''; error.value = ''; notice.value = ''; conflict.value = false }, { flush: 'sync' })
  const serverFields = snapshot => Object.fromEntries(snapshot.items.map(p => [p.knowledge_id, fields(p.self_report)]))
  function hydrate(snapshot) { baseline.value = serverFields(snapshot); draft.value = clone(baseline.value); revision.value = snapshot.assessment_revision }
  async function refreshReads(owner, token) {
    const [snapshot, records] = await Promise.all([client.learningGuidance(owner), client.selfAssessmentHistory(owner)])
    if (token !== epoch) return
    overview.value = snapshot; history.value = records.items
    return snapshot
  }
  async function load() {
    if (!student.value || busy.value) return
    const owner = student.value, token = epoch
    busy.value = 'load'; error.value = ''
    try {
      const snapshot = await refreshReads(owner, token); if (!snapshot || token !== epoch) return
      if (!initialized) {
        let cached
        try { cached = JSON.parse(storage.getItem(`eduagent.self.v1.${owner}`) || 'null') } catch { /* Server history remains authoritative. */ }
        const keys = new Set(snapshot.items.map(p => p.knowledge_id))
        if (valid(cached?.draft) && valid(cached?.baseline) && Number.isInteger(cached.revision) && cached.revision >= 0
            && Object.keys(cached.draft).length === keys.size && Object.keys(cached.baseline).length === keys.size
            && Object.keys(cached.draft).every(k => keys.has(k)) && Object.keys(cached.baseline).every(k => keys.has(k))) {
          draft.value = cached.draft; baseline.value = cached.baseline; revision.value = cached.revision
          if (cached.pending && typeof cached.pending.payload?.request_id === 'string' && Number.isInteger(cached.pending.payload.expected_revision)
              && Array.isArray(cached.pending.payload.items)) pending.value = cached.pending
          if (dirty.value || pending.value) {
            conflict.value = Boolean(cached.conflict) || cached.revision !== snapshot.assessment_revision
            notice.value = '已恢复本机自评草稿或原提交编号。'
          } else { hydrate(snapshot); conflict.value = false }
        } else hydrate(snapshot)
        initialized = true
      } else if (!dirty.value && !pending.value && !conflict.value) hydrate(snapshot)
      else if (revision.value !== snapshot.assessment_revision) { conflict.value = true; notice.value = '服务端自评已有变化，本机草稿保留。' }
      persist()
      if (pending.value) await reconcile(owner, token)
    } catch (e) { if (token === epoch) error.value = e.message }
    finally { if (token === epoch) busy.value = '' }
  }
  async function committed(receipt, operation, owner, token) {
    if (token !== epoch) return
    for (const item of receipt.items) {
      const submitted = operation.payload.items.find(i => i.knowledge_id === item.knowledge_id)
      if (same(draft.value[item.knowledge_id], submitted)) draft.value[item.knowledge_id] = fields(item)
      baseline.value[item.knowledge_id] = fields(item)
    }
    revision.value = receipt.committed_revision; pending.value = null
    conflict.value = receipt.current_revision !== receipt.committed_revision
    notice.value = conflict.value ? '原提交已保存，但已有更新自评，请读取新版本后确认。' : '自评已追加保存；答题与BKT保持独立。'
    error.value = ''; persist()
    try {
      const latest = await refreshReads(owner, token)
      if (latest && token === epoch && latest.assessment_revision !== revision.value) {
        if (dirty.value) { conflict.value = true; notice.value += ' 刷新发现更新的自评，本机改动保留。' }
        else { hydrate(latest); conflict.value = false; notice.value += ' 已显示服务端更新版本。' }
        persist()
      }
    } catch { if (token === epoch) notice.value += ' 只读刷新失败，可稍后刷新。' }
  }
  async function execute(operation) {
    const owner = student.value, token = epoch
    busy.value = 'save'; error.value = ''
    try { await committed(await client.saveSelfAssessments(owner, operation.payload), operation, owner, token) }
    catch (e) { if (token === epoch) { error.value = e.message
      if (!e.uncertain) { pending.value = null; conflict.value = e.status === 409 }
      notice.value = e.uncertain ? '提交结果待确认；刷新只查询原回执，不会追加新报告。' : '本机自评草稿已保留。'; persist() } }
    finally { if (token === epoch) busy.value = '' }
  }
  async function reconcile(owner = student.value, token = epoch) {
    const operation = pending.value; if (!operation) return
    try { await committed(await client.selfAssessmentReceipt(owner, operation.payload.request_id), operation, owner, token) }
    catch (e) { if (token === epoch) { if (e.status === 404) { pending.value.retryReady = true; notice.value = '未找到原回执；可以手动重试原编号与内容。' }
      else error.value = e.message; persist() } }
  }
  async function save() {
    if (busy.value || !initialized) return
    if (pending.value) {
      if (pending.value.retryReady) return execute(clone(pending.value))
      busy.value = 'read'; try { await reconcile() } finally { busy.value = '' }; return
    }
    if (conflict.value) { error.value = '先读取新版本并核对本机修改。'; return }
    const items = Object.entries(draft.value).filter(([key, value]) => !same(value, baseline.value[key]))
      .map(([knowledge_id, value]) => ({ knowledge_id, ...fields(value) }))
    if (!items.length) return
    if (items.some(item => !Number.isInteger(item.level) || item.level < 1 || item.level > 4)) {
      error.value = '变动的知识点需要选择1～4级；未自评的知识点可保持未填写。'; return
    }
    pending.value = { payload: { request_id: crypto.randomUUID(), course_id: 'machine_learning', expected_revision: revision.value, items } }
    if (!persist()) { pending.value = null; return }
    return execute(clone(pending.value))
  }
  async function readLatest() {
    if (busy.value || pending.value) return
    const token = epoch, owner = student.value
    busy.value = 'read'; error.value = ''
    try {
      const edits = Object.fromEntries(Object.entries(draft.value).filter(([k, v]) => !same(v, baseline.value[k])).map(([k,v]) => [k, clone(v)]))
      const snapshot = await refreshReads(owner, token); if (!snapshot || token !== epoch) return
      hydrate(snapshot); Object.assign(draft.value, edits); conflict.value = false
      notice.value = '已读取新版本，保留本机改动；请核对后再明确保存。'; persist()
    } catch (e) { if (token === epoch) error.value = e.message }
    finally { if (token === epoch) busy.value = '' }
  }
  return { overview, draft, baseline, revision, history, pending, busy, error, notice, conflict, dirty, canGenerate,
    masterySnapshot, status, load, save, readLatest, persist }
}
