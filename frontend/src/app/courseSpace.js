import { computed, inject, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { api as defaultApi } from '../api.js'
import { useWorkspace } from '../features/learning/useWorkspace.js'
import { useTeachingWorkspace } from '../features/learning/useTeachingWorkspace.js'
import { createFeatureRegistry } from './featureRegistry.js'
import { featureDefinitions, pageFeatures } from './featureDefinitions.js'
import { usePageRoute } from './usePageRoute.js'
import { auxiliaryTabs, builderTabs, studentTabs } from './navigation.js'

export const courseSpaceKey = Symbol('EduAgent course space')
export const useCurrentCourseSpace = () => inject(courseSpaceKey)

export function useCourseSpace(props) {
  const client = props.client || defaultApi
  const modern = typeof client.notebooks === 'function'
  const w = reactive(useWorkspace(client, props.store))
  const flow = reactive(useTeachingWorkspace(client, w))
  const student = computed(() => w.student)
  const registry = createFeatureRegistry({ client, w, flow, student, notesStore: props.notesStore }, featureDefinitions)
  const { route, go } = usePageRoute(() => registry.persist() && (!flow.pending || flow.persist()), modern ? 'notebooks' : 'study')
  const tab = computed(() => route.value.page)
  const isBuilder = computed(() => builderTabs.some(item => item.id === tab.value))
  const pageTitle = computed(() => tab.value === 'notebooks' ? '学习' : tab.value === 'learn' && modern ? '练习 · 测一下' : tab.value === 'notebook' ? registry.peek('notebooks')?.current?.detail.title || '学习笔记本' : [...studentTabs, ...builderTabs, ...auxiliaryTabs].find(i => i.id === tab.value)?.name)
  const goalsText = computed(() => w.snapshot?.goals.map(w.topicName).join('、'))
  const course = computed(() => ({ id: 'machine_learning', title: '机器学习',
    subtitle: flow.data?.release ? `学习版本：${flow.data.release.title}` : '资料 · 问答 · 练习 · 学习进度' }))
  const formMode = ref('new'), learnerId = ref(`learner-${crypto.randomUUID().slice(0, 8)}`), goals = ref(modern ? [] : ['logistic_regression'])
  const routeError = ref('')
  let routeEpoch = 0

  function navigate(page, params = {}) {
    if (page === tab.value && !Object.keys(params).length) return
    const notes = registry.peek('notes')
    return notes ? notes.navigate(() => go(page, params)) : go(page, params)
  }
  function leaveStudent() {
    const leave = () => { if (go(modern ? 'notebooks' : 'study')) w.leave() }
    const notes = registry.peek('notes')
    return notes ? notes.navigate(leave) : leave()
  }
  async function start() {
    const chosen = flow.selectedRelease, formal = tab.value === 'learn'
    const selectedGoals = goals.value.length ? goals.value : w.knowledge.map(p=>p.id)
    await w.start(learnerId.value, selectedGoals, formMode.value === 'restore', flow.enabled || !formal)
    if (w.active && flow.enabled) {
      await flow.load()
      if ((!modern || formal) && formMode.value !== 'restore' && flow.releases.some(r => r.id === chosen)) {
        flow.selectedRelease = chosen
        await flow.begin()
        if (formal && flow.session) await flow.allocate()
      }
    }
    if (w.active && !formal) go(modern ? 'notebooks' : 'study')
  }
  async function restoreRoute() {
    const serial = ++routeEpoch, owner = w.student, page = tab.value, params = route.value.params
    if (!w.active) return
    routeError.value = ''
    try {
      for (const name of pageFeatures[page] || []) registry.use(name)
      const current = () => serial === routeEpoch && w.student === owner && tab.value === page
      if (page === 'bank' && params.view === 'practice') { go('practice', params, true); return }
      if (page === 'study' && params.question && (!params.knowledge || w.knowledge.some(p => p.id === params.knowledge))) {
        const study = registry.use('chat')
        await study.load()
        if (!current()) return
        study.prepare(params.question)
        go('study', {}, true)
      }
      const bank = ['materials','resources'].includes(page) ? registry.peek('library') : registry.peek('practice')
      if (['materials', 'bank', 'practice', 'resources'].includes(page) && (params.resource || params.question)) {
        if (page === 'bank') bank.filter.resource_id = params.resource || ''
        await bank.load()
        if (!current()) return
        if (['materials', 'resources'].includes(page)) {
          bank.section = 'resources'
          const item = bank.resources.find(r => r.resource_id === params.resource)
          if (item && item.resource_id !== bank.resource?.resource_id) await bank.selectResource(item)
        } else {
          bank.section = page === 'practice' ? 'practice' : 'bank'
          if (params.question && params.question !== bank.current?.id) await bank.open(params.question)
        }
      }
      if (page === 'notes' && params.note) {
        const notes = registry.use('notes')
        await notes.load()
        if (current()) await notes.open(params.note)
      }
    } catch (error) { if (serial === routeEpoch) routeError.value = error.message }
  }
  async function refreshCurrent() {
    const page = tab.value
    if (!w.active) return w.boot()
    if (page === 'notebooks') return registry.use('notebooks').load()
    if (page === 'notebook') {
      const books = registry.use('notebooks')
      const entry = await books.open(route.value.params.book)
      return entry?.chat.load()
    }
    if (['builder', 'publish'].includes(page)) return registry.use('builder').load()
    if (page === 'architecture') return registry.use('architecture').load()
    if (page === 'insights') return Promise.all([registry.use('assessment').load(), registry.use('guides').load()])
    if (['practice', 'bank'].includes(page)) return registry.use('practice').load()
    if (page === 'resources') return registry.use('library').load()
    if (page === 'materials') return Promise.all([registry.use('library').load(), registry.use('documents').load()])
    if (page === 'notes') return registry.use('notes').load()
    if (page === 'study') return Promise.all([registry.use('chat').load(), registry.use('assessment').load()])
    await w.refresh(); return flow.load()
  }
  async function explainNext() {
    const study = registry.use('chat'), owner = w.student
    await study.load()
    if (owner !== w.student) return
    const scope = flow.data?.release?.retrieval_scope, point = flow.data?.next_task?.knowledge_id || w.decision?.knowledge_id
    if (scope) {
      const allowed = scope.filter(r => study.sources.some(s => s.source_type === r.source_type && s.source_id === r.source_id && s.source_version === r.source_version))
      const linked = allowed.filter(r => r.source_type === 'teaching_material' && study.sources.some(s => s.source_id === r.source_id && s.knowledge_point_ids.includes(point)))
      study.selected = linked.length ? linked : allowed
    }
    study.prepare(`请围绕${w.topicName(point)}解释关键概念，举一个例子，并说明怎样准备下一次正式练习。${flow.data?.next_task?.reason || ''}`)
    navigate('study')
  }
  function protectDraft(event) {
    if (flow.pending || registry.hasUnsaved()) { event.preventDefault(); event.returnValue = '' }
  }
  watch([route, () => w.active, student], restoreRoute, { flush: 'sync' })
  watch(() => w.active, active => { if (active) flow.load() })
  watch(() => flow.data?.guidance, value => { const self = registry.peek('assessment'); if (value && self) self.overview = value })
  onMounted(w.boot)
  onMounted(flow.publicCourses)
  onMounted(() => window.addEventListener('beforeunload', protectDraft))
  onUnmounted(() => { routeEpoch++; window.removeEventListener('beforeunload', protectDraft); registry.dispose() })
  return reactive({ client, modern, w, flow, registry, features: registry.states, course, route, tab, isBuilder, pageTitle, goalsText,
    replaceRoute: (page, params) => go(page, params, true),
    formMode, learnerId, goals, routeError, start, navigate, leaveStudent, refreshCurrent, explainNext })
}
