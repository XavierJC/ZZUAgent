import { computed, ref, watch } from 'vue'

const reference = (s) => ({ source_type: s.source_type, source_id: s.source_id, source_version: s.source_version })
export const sourceKey = (s) => `${s.source_type}:${s.source_id}`
const usable = (s) => ['ready', 'empty'].includes(s.index_status)

export function useStudyWorkbench(client, student, storage = globalThis.localStorage, lesson = null) {
  const sources = ref([]), selected = ref([]), query = ref(''), mode = ref('local'), consent = ref(false), teacherConsent=ref(false)
  const runs = ref([]), current = ref(null), busy = ref(''), error = ref(''), notice = ref(''), pendingId = ref(null)
  const capabilities = ref(null), drawer = ref(null), panel = ref('chat'), initialized = ref(false)
  let epoch = 0, restoring = false
  const chosen = computed(() => sources.value.filter(s => selected.value.some(r => sourceKey(r) === sourceKey(s) && r.source_version === s.source_version)))
  const personal = computed(() => chosen.value.filter(s => s.source_type === 'personal_note'))
  const teachers = computed(() => chosen.value.filter(s => s.source_type === 'teaching_material'))
  function persist() {
    if (!student.value || restoring || !initialized.value) return true
    try {
      storage.setItem(`eduagent.workbench.v1.${student.value}`, JSON.stringify({ selected: selected.value, query: query.value,
        last_request_id: current.value?.request_id || null, pending_request_id: pendingId.value }))
      return true
    } catch { error.value = '无法保留本轮请求编号，请检查浏览器存储；暂不发送模型请求。'; return false }
  }
  watch([selected, query], () => { consent.value = false; teacherConsent.value=false; persist() }, { deep: true, flush: 'sync' })
  watch(mode, () => { consent.value = false;teacherConsent.value=false })
  watch(student, () => {
    epoch++; initialized.value = false; sources.value = []; selected.value = []; query.value = ''
    runs.value = []; current.value = null; pendingId.value = null; drawer.value = null
    error.value = ''; notice.value = ''; busy.value = ''; consent.value = false;teacherConsent.value=false; mode.value = 'local'
  }, { flush: 'sync' })

  async function load() {
    const owner = student.value, token = epoch
    if (!owner || busy.value) return
    busy.value = 'load'; error.value = ''
    try {
      const [catalog, history, config] = await Promise.all([client.knowledgeSources(owner), client.workbenchRuns(owner), client.workbenchCapabilities(owner)])
      if (token !== epoch) return
      const scope = lesson?.scope?.()
      sources.value = scope ? catalog.items.filter(s=>s.source_type==='personal_note' || scope.some(r=>sourceKey(r)===sourceKey(s) && r.source_version===s.source_version)) : catalog.items; runs.value = history; capabilities.value = config
      let saved = null
      if (!initialized.value) {
        try { saved = JSON.parse(storage.getItem(`eduagent.workbench.v1.${owner}`) || 'null') } catch { notice.value = '本机工作台状态无法读取，服务器历史仍可查看。' }
        restoring = true
        query.value = typeof saved?.query === 'string' ? saved.query.slice(0, 1000) : ''
        selected.value = Array.isArray(saved?.selected) ? saved.selected.filter(s => s && ['course_material', 'personal_note','teaching_material'].includes(s.source_type)
          && typeof s.source_id === 'string' && typeof s.source_version === 'string').slice(0, 55)
          : catalog.items.filter(s => s.source_type === 'course_material' && usable(s)).map(reference)
        pendingId.value = saved?.pending_request_id || null
        current.value = history.find(r => r.request_id === saved?.last_request_id) || history[0] || null
        initialized.value = true; restoring = false
      }
      const previous = selected.value
      selected.value = previous.filter(ref => catalog.items.some(s => usable(s) && sourceKey(s) === sourceKey(ref) && s.source_version === ref.source_version))
      if (previous.length !== selected.value.length) notice.value = '部分所选来源已变化或未就绪，已取消其选择，请核对后重新勾选。'
      const contexts=client.teachingContexts ? (await client.teachingContexts(owner)).items : lesson?.contexts?.() || []
      if(token!==epoch)return
      for(const run of runs.value){const linked=contexts.find(r=>r.request_id===run.request_id);if(linked){run.lesson_context=linked.context;run.lesson_stale=linked.lesson_stale ?? linked.context.learning_revision!==lesson?.revision?.()}}
      if (current.value) current.value = history.find(r => r.request_id === current.value.request_id) || current.value
      if (pendingId.value) {
        try {
          const result = await client.workbenchRun(owner, pendingId.value)
          if (token !== epoch) return
          current.value = result
          if (result.status !== 'uncertain') pendingId.value = null
        } catch { if (token === epoch) notice.value = '尚不能确认原请求状态。仅查询记录，不会自动重新发送模型请求。' }
      }
      if (current.value) {
        const linked=contexts.find(r=>r.request_id===current.value.request_id)
        if(linked){current.value.lesson_context=linked.context;current.value.lesson_stale=linked.lesson_stale}
      }
      if (current.value?.status === 'uncertain') pendingId.value = current.value.request_id
      persist()
    } catch (e) { if (token === epoch) error.value = e.message }
    finally { if (token === epoch) busy.value = '' }
  }

  function toggle(source, checked) {
    consent.value = false
    selected.value = selected.value.filter(r => sourceKey(r) !== sourceKey(source))
    if (checked && usable(source)) selected.value.push(reference(source))
  }
  function view(run) { current.value = run; consent.value = false;teacherConsent.value=false; panel.value = 'chat'; persist() }
  async function ask() {
    if (busy.value || pendingId.value || !query.value.trim() || !chosen.value.length) return
    const owner = student.value, token = epoch
    const request = { request_id: crypto.randomUUID(), question: query.value.trim(), sources: chosen.value.map(reference),
      course_id: 'machine_learning', mode: mode.value, allow_personal_external: mode.value === 'model' && personal.value.length > 0 && consent.value,
      ...(teachers.value.length?{allow_teacher_external:mode.value==='model' && teacherConsent.value}:{}) }
    pendingId.value = request.request_id
    if (!persist()) { pendingId.value = null; return }
    busy.value = 'ask'; error.value = ''; notice.value = ''; consent.value = false;teacherConsent.value=false
    try {
      const session=lesson?.session?.()
      const result = await (session && client.teachingExplain ? client.teachingExplain(owner,session.id,request) : client.workbenchAsk(owner, request))
      if (token !== epoch) return
      current.value = result; runs.value = [result, ...runs.value.filter(r => r.request_id !== result.request_id)].slice(0, 20)
      if (result.status !== 'uncertain') pendingId.value = null
      persist()
      await lesson?.refresh?.()
    } catch (e) {
      if (token !== epoch) return
      error.value = e.message
      if (!e.uncertain) pendingId.value = null
      else notice.value = '请求编号已保留。请查询原请求状态；不会自动重发或自动调用模型。'
      persist()
    } finally { if (token === epoch) busy.value = '' }
  }
  function releaseUncertain() {
    pendingId.value = null
    notice.value = '已结束本轮等待。原请求仍保留在历史中；新问题会创建独立请求，可能产生新的模型费用。'
    persist()
  }
  async function open(source) {
    const token = epoch, owner = student.value
    error.value = ''
    try {
      const result = await client.openSource(owner, reference(source))
      if (token === epoch) drawer.value = { ...result, current_status: 'current', preview: true }
    } catch (e) { if (token === epoch) error.value = e.message }
  }
  function citation(item) {
    const state = current.value?.source_statuses.find(s => sourceKey(s) === sourceKey(item))
    drawer.value = { ...item, ...(item.source_type==='teaching_material' ? {original_page_url:`/api/v1/students/${encodeURIComponent(student.value)}/documents/${item.document_id}/preview?version_id=${item.version_id}&page=${item.page_number}`} : {}), current_status: state?.current_status || 'unavailable', preview: false }
  }
  async function save() {
    if (busy.value || !current.value) return null
    const owner = student.value, token = epoch, runId = current.value.request_id
    busy.value = 'save'; error.value = ''
    try {
      const result = await client.saveWorkbenchNote(owner, runId)
      if (token !== epoch) return null
      const run = runs.value.find(r => r.request_id === runId)
      if (run) run.saved_note_id = result.note_id
      if (current.value?.request_id === runId) current.value.saved_note_id = result.note_id
      notice.value = result.deleted ? '原另存笔记已软删除；重复保存不会恢复或新建。' : result.edited ? '已找到另存笔记；用户修改保留，原始回答仍在历史中。' : '回答已另存为可编辑笔记，引用和生成时间已保留。'
      persist()
      return result
    } catch (e) { if (token === epoch) error.value = `${e.message} 再次保存会复用同一笔记。`; return null }
    finally { if (token === epoch) busy.value = '' }
  }
  return { sources, selected, query, mode, consent, teacherConsent,teachers,chosen, personal, runs, current, busy, error, notice, pendingId,
    capabilities, drawer, panel, initialized, load, toggle, ask, view, open, citation, save, releaseUncertain }
}
