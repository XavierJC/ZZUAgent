import { computed, ref, watch } from 'vue'

// Self-review is deliberately local. Its receipts never go to /answers or
// the personal-bank admission APIs, and never count as BKT evidence.
export function useReviewPractice(api, w, storage = globalThis.localStorage) {
  const enabled = Boolean(api.reviewExercises)
  const active = ref(false), items = ref([]), focus = ref(''), key = ref('')
  const selected = ref(''), result = ref(null), records = ref([])
  const busy = ref(false), error = ref(''), storageWarning = ref('')
  let epoch = 0
  const list = computed(() => items.value.filter(i => !focus.value || i.question.knowledge_id === focus.value))
  const current = computed(() => list.value.find(i => i.review_key === key.value) || null)
  const topics = computed(() => [...new Set(items.value.map(i => i.question.knowledge_id))])
  const storageKey = owner => `eduagent.self-review.v1:${encodeURIComponent(owner)}`

  function persist() {
    if (!w.student) return
    try {
      storage.setItem(storageKey(w.student), JSON.stringify({ active: active.value, focus: focus.value,
        key: key.value, selected: selected.value, result: result.value, records: records.value.slice(-50) }))
      storageWarning.value = ''
    } catch { storageWarning.value = '浏览器无法保存复习进度；本次仅在当前页面保留。' }
  }
  function choose(nextKey) {
    key.value = nextKey; selected.value = ''; result.value = null; persist()
  }
  function changeFocus(value) {
    focus.value = value
    choose(list.value[0]?.review_key || '')
  }
  async function load() {
    if (!enabled || !w.student) return
    const owner = w.student, token = ++epoch
    busy.value = true; error.value = ''
    try {
      const value = await api.reviewExercises(owner)
      if (token !== epoch || owner !== w.student) return
      if (value.student_id !== owner) throw new Error('复习资料与当前学习标识不匹配，请重新读取。')
      items.value = value.items
      if (focus.value && !topics.value.includes(focus.value)) focus.value = ''
      records.value = records.value.filter(r => items.value.some(i => i.review_key === r.review_key))
      if (!current.value) choose(list.value[0]?.review_key || '')
      else {
        if (!Object.hasOwn(current.value.question.options, selected.value)) selected.value = ''
        // Only restore a result that matches the current server snapshot.
        if (result.value?.review_key !== key.value || result.value?.selected_answer !== selected.value) result.value = null
        if (result.value) result.value = { ...result.value, correct: selected.value === current.value.correct_answer }
        persist()
      }
    } catch (e) {
      if (token === epoch) { error.value = e.message || '读取复习题失败，请重试。'; items.value = [] }
    } finally { if (token === epoch) busy.value = false }
  }
  async function open() {
    if (busy.value) return
    active.value = true
    if (!key.value) focus.value = w.decision?.knowledge_id || ''
    persist(); await load()
  }
  function close() { active.value = false; persist() }
  function select(answer) {
    if (!current.value || result.value || busy.value || !Object.hasOwn(current.value.question.options, answer)) return
    selected.value = answer; persist()
  }
  function submit() {
    if (!current.value || result.value || busy.value || !Object.hasOwn(current.value.question.options, selected.value)) return
    result.value = { review_id: crypto.randomUUID(), review_key: key.value, selected_answer: selected.value,
      correct: selected.value === current.value.correct_answer, created_at: new Date().toISOString() }
    records.value = [...records.value, result.value].slice(-50); persist()
  }
  function next() {
    if (!list.value.length || busy.value) return
    const index = list.value.findIndex(i => i.review_key === key.value)
    choose(list.value[(index + 1) % list.value.length].review_key)
  }
  watch(() => w.student, owner => {
    epoch++; busy.value = false; items.value = []; active.value = false; error.value = ''
    selected.value = ''; result.value = null; records.value = []; key.value = ''; focus.value = ''; storageWarning.value = ''
    if (!owner || !enabled) return
    try {
      const saved = JSON.parse(storage.getItem(storageKey(owner)) || '{}')
      active.value = saved.active === true; focus.value = typeof saved.focus === 'string' ? saved.focus : ''
      key.value = typeof saved.key === 'string' ? saved.key : ''; selected.value = typeof saved.selected === 'string' ? saved.selected : ''
      result.value = saved.result && typeof saved.result === 'object' ? saved.result : null
      records.value = Array.isArray(saved.records) ? saved.records.slice(-50).filter(r => r && typeof r === 'object') : []
    } catch { /* Missing/invalid local state does not block review. */ }
    if (active.value) load() // Read only; never allocate or submit on refresh.
  }, { immediate: true })
  return { enabled, active, items, list, topics, focus, current, selected, result, records,
    busy, error, storageWarning, open, close, load, select, submit, next, changeFocus }
}
