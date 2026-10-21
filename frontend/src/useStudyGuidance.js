import { computed, ref, watch } from 'vue'

export function useStudyGuidance(client, student, snapshot, chosen, canGenerate, storage = globalThis.localStorage) {
  const runs = ref([]), current = ref(null), busy = ref(''), error = ref(''), notice = ref(''), pendingId = ref(null)
  const mode = ref('rules'), useSources = ref(false), consent = ref(false), drawer = ref(null), ready = ref(false)
  let epoch = 0, initialized = false
  const selected = computed(() => mode.value === 'model' || useSources.value ? chosen.value : [])
  const personal = computed(() => selected.value.filter(s => s.source_type === 'personal_note'))
  const stale = computed(() => !!current.value && (current.value.status === 'stale' || !!current.value.stale_reasons?.length || !!snapshot.value && (
    current.value.snapshot.learning_revision !== snapshot.value.learning_revision || current.value.snapshot.assessment_revision !== snapshot.value.assessment_revision)))
  watch([() => snapshot.value?.snapshot_hash, () => JSON.stringify(chosen.value.map(s => [s.source_id, s.source_version])), mode, useSources], () => { consent.value = false }, { flush: 'sync' })
  watch(student, () => { epoch++; initialized = false; runs.value = []; current.value = null; busy.value = ''; error.value = ''; notice.value = ''
    pendingId.value = null; mode.value = 'rules'; useSources.value = false; consent.value = false; drawer.value = null; ready.value = false }, { flush: 'sync' })
  function persist() {
    if (!student.value || !initialized) return true
    try { storage.setItem(`eduagent.guide.v1.${student.value}`, JSON.stringify({ last: current.value?.request_id || null, pending: pendingId.value })); return true }
    catch { error.value = '无法保留指南请求编号，暂不发送生成请求。'; return false }
  }
  async function load() {
    if (!student.value || busy.value) return
    const owner = student.value, token = epoch
    busy.value = 'load'; error.value = ''
    try {
      const history = await client.studyGuides(owner); if (token !== epoch) return
      runs.value = history
      if (!initialized) {
        let cached
        try { cached = JSON.parse(storage.getItem(`eduagent.guide.v1.${owner}`) || 'null') } catch { /* Read server records only. */ }
        pendingId.value = typeof cached?.pending === 'string' ? cached.pending : null
        current.value = history.find(r => r.request_id === cached?.last) || history[0] || null; initialized = true
      } else if (current.value) current.value = history.find(r => r.request_id === current.value.request_id) || current.value
      if (pendingId.value) {
        try { const result = await client.studyGuide(owner, pendingId.value); if (token !== epoch) return
          current.value = result; if (result.status !== 'uncertain') pendingId.value = null
        } catch { if (token === epoch) notice.value = '原指南执行情况尚不能确认；刷新只读取记录，不自动重发。' }
      }
      if (current.value?.status === 'uncertain') pendingId.value = current.value.request_id
      ready.value = true; persist()
    } catch (e) { if (token === epoch) error.value = e.message }
    finally { if (token === epoch) busy.value = '' }
  }
  async function generate() {
    if (busy.value || pendingId.value || !canGenerate.value || !snapshot.value || !initialized) return
    if (mode.value === 'model' && !selected.value.length) { error.value = '模型模式必须选择资料来源。'; return }
    const owner = student.value, token = epoch
    const body = { request_id: crypto.randomUUID(), course_id: 'machine_learning', mode: mode.value,
      expected_learning_revision: snapshot.value.learning_revision, expected_assessment_revision: snapshot.value.assessment_revision,
      sources: selected.value.map(s => ({ source_type: s.source_type, source_id: s.source_id, source_version: s.source_version })),
      allow_personal_external: mode.value === 'model' && personal.value.length > 0 && consent.value }
    pendingId.value = body.request_id
    if (!persist()) { pendingId.value = null; return }
    busy.value = 'generate'; error.value = ''; notice.value = ''; consent.value = false
    try {
      const result = await client.generateStudyGuide(owner, body); if (token !== epoch) return
      current.value = result; runs.value = [result, ...runs.value.filter(r => r.request_id !== result.request_id)].slice(0, 20)
      if (result.status !== 'uncertain') pendingId.value = null
      persist()
    } catch (e) { if (token === epoch) { error.value = e.message; if (!e.uncertain) pendingId.value = null
      else notice.value = '指南编号已保留；请查询原请求，不自动重发付费请求。'; persist() } }
    finally { if (token === epoch) busy.value = '' }
  }
  function view(run) { current.value = run; consent.value = false; persist() }
  function release() { pendingId.value = null; notice.value = '已结束等待，原请求保留；独立新模型请求可能另计费。'; persist() }
  function citation(item) { drawer.value = { ...item, preview: false,
    current_status: current.value.source_statuses.find(s => s.source_type === item.source_type && s.source_id === item.source_id)?.current_status || 'unavailable' } }
  return { runs, current, busy, error, notice, pendingId, mode, useSources, consent, drawer, selected, personal, stale, ready, load, generate, view, release, citation }
}
