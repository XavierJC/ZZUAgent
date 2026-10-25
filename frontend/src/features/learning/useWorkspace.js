import { computed, ref } from 'vue'
import { api as defaultApi } from '../../api.js'
import { browserStore } from '../../storage.js'

export const actionLabels = { diagnose: '初始诊断', review: '巩固薄弱点', practice: '针对练习',
  advance: '进入下一知识点', finish: '本轮学习已完成', stopped: '本轮练习已暂停' }
export const toolLabels = { get_learning_state: '读取学情', retrieve_course_material: '查阅课程资料',
  get_next_exercise: '安排后续练习' }
export const percent = (value) => `${(value * 100).toFixed(1)}%`

export function useWorkspace(api = defaultApi, store = browserStore()) {
  const health = ref(null), knowledge = ref([]), snapshot = ref(null), decision = ref(null)
  const history = ref([]), tutorRuns = ref([]), tutor = ref(null), sources = ref([])
  const student = ref(''), selected = ref(''), feedback = ref(null), pending = ref(null)
  const busy = ref(''), error = ref(''), notice = ref(''), searchBusy = ref(false)
  const topicName = (id) => knowledge.value.find((item) => item.id === id)?.name || id || '学习规划'
  const activeTopic = computed(() => topicName(feedback.value?.knowledge_id || decision.value?.knowledge_id))
  const active = computed(() => Boolean(snapshot.value))
  const reviewNotice = computed(() => health.value?.ai_checked_count
    ? `${health.value.question_count} 道课程诊断题已接入，AI检查不等于人工审核；掌握度为模型估计。`
    : health.value?.pending_review_count
    ? `${health.value.question_count} 道演示题仍待内容审阅，掌握度为模型估计。` : '掌握度为模型估计，仅供学习参考。')
  function remember() { return store.write({ student_id: student.value, pending: pending.value }) }
  function message(exception) { error.value = exception.message || '操作未完成，请稍后重试。' }
  async function lock(name, callback) {
    if (busy.value) return
    busy.value = name; error.value = ''; notice.value = ''
    try { await callback() } catch (exception) { message(exception) } finally { busy.value = '' }
  }
  async function readState() {
    const [state, answers, runs] = await Promise.all([
      api.mastery(student.value), (api.teachingHistory || api.history)(student.value), api.tutorRuns(student.value),
    ])
    snapshot.value = state; history.value = answers.items; tutorRuns.value = runs
    tutor.value = runs[0] || null
  }
  function restorePending(saved) {
    const entry = saved.pending
    if (entry?.student_id === student.value && typeof entry.decision_id === 'string'
        && typeof entry.event_id === 'string' && /^[ABCD]$/.test(entry.answer)) {
      pending.value = entry; selected.value = entry.answer
    }
  }
  const readDecision = () => api.currentDecision ? api.currentDecision(student.value) : Promise.resolve(null)
  async function boot() {
    await lock('boot', async () => {
      const [service, points] = await Promise.all([api.health(), api.knowledge()])
      health.value = service; knowledge.value = points
      const saved = store.read()
      if (typeof saved.student_id !== 'string' || !saved.student_id.trim()) return
      student.value = saved.student_id
      restorePending(saved)
      await readState()
      decision.value = await readDecision()
      if (pending.value) notice.value = '有一笔尚未确认的答题提交。请先重试原提交，以确认评分结果。'
    })
  }
  async function start(id, goals, restore = false, deferAllocation = false) {
    await lock('start', async () => {
      const normalized = id.trim()
      if (!normalized || normalized.length > 128) throw new Error('请填写 1～128 字符的学习标识。')
      if (/[/\\\u0000-\u001f\u007f]/.test(normalized)) throw new Error('学习标识不要包含斜杠、反斜杠或控制字符。')
      if (!restore && !goals.length) throw new Error('请至少选择一个学习目标。')
      const state = await api.start(normalized, restore ? undefined : goals)
      student.value = normalized; snapshot.value = state
      decision.value = null; feedback.value = null; selected.value = ''; pending.value = null; tutor.value = null
      history.value = []; tutorRuns.value = []; sources.value = []
      remember()
      await readState()
      decision.value = deferAllocation ? await readDecision() : await api.next(student.value)
    })
  }
  async function refresh() {
    await lock('refresh', async () => {
      const draftDecision = decision.value?.decision_id, draftAnswer = selected.value
      health.value = await api.health()
      if (!student.value) return
      await readState()
      decision.value = await readDecision()
      if (!pending.value) { feedback.value = null; selected.value = decision.value?.decision_id===draftDecision ? draftAnswer : '' }
    })
  }
  async function submit() {
    await lock('submit', async () => {
      if (!pending.value) {
        if (!decision.value?.question || !/^[ABCD]$/.test(selected.value)) return
        pending.value = { student_id: student.value, decision_id: decision.value.decision_id,
          event_id: crypto.randomUUID(), answer: selected.value }
      }
      // Persist BEFORE sending. A lost HTTP response can be retried with the
      // same event id even after a reload, without another BKT transition.
      if (!remember()) throw new Error('浏览器暂时无法保存提交编号，请允许本地存储后再提交，以便可靠重试。')
      const receipt = pending.value
      try {
        feedback.value = await api.submit(student.value, {
          decision_id: receipt.decision_id, event_id: receipt.event_id, answer: receipt.answer,
        })
        if (decision.value?.decision_id !== feedback.value.decision_id) decision.value = null
      } catch (exception) {
        if (!exception.uncertain && exception.status >= 400 && exception.status < 500) {
          pending.value = null; remember()
          await readState()
          decision.value = await readDecision()
          selected.value = ''
        }
        throw exception
      }
      pending.value = null; remember()
      await readState()
    })
  }
  async function next() {
    if (pending.value) return
    await lock('next', async () => {
      await readState()
      decision.value = await api.next(student.value)
      selected.value = ''; feedback.value = null
    })
  }
  async function ask(question) {
    const clean = question.trim()
    if (!clean || clean.length > 2000 || pending.value) return
    await lock('tutor', async () => {
      try { tutor.value = await api.tutor(student.value, clean) } catch (exception) {
        if (exception.uncertain) notice.value = '讲解可能仍在生成，请先刷新已保存记录。再次发送会发起新的模型请求。'
        throw exception
      }
      tutorRuns.value = [tutor.value, ...tutorRuns.value.filter((run) => run.run_id !== tutor.value.run_id)].slice(0, 5)
      // Do not automatically replace an unsubmitted exercise with text from
      // the model. The server supplies the sole authoritative assignment.
      if (!feedback.value) decision.value = await readDecision()
    })
  }
  async function search(query) {
    if (searchBusy.value || !query.trim()) return
    searchBusy.value = true; error.value = ''
    try { sources.value = await api.search(query.trim()) } catch (exception) { message(exception) }
    finally { searchBusy.value = false }
  }
  function leave() {
    if (busy.value || pending.value) return
    student.value = ''; snapshot.value = null; decision.value = null; tutor.value = null
    history.value = []; tutorRuns.value = []; feedback.value = null; selected.value = ''; error.value = ''; notice.value = ''
    remember()
  }
  return { health, knowledge, snapshot, decision, history, tutorRuns, tutor, sources, student, selected,
    feedback, pending, busy, error, notice, searchBusy, active, activeTopic, reviewNotice, topicName,
    boot, start, refresh, submit, next, ask, search, leave }
}
