<script setup>
import { computed, defineAsyncComponent, h } from 'vue'
const props = defineProps({ space: Object })
const loadingComponent = { render: () => h('p', { role: 'status', class: 'loading-state' }, '正在打开课程页面…') }
const errorComponent = { render: () => h('section', { role: 'alert', class: 'alert alert-error' }, '页面资源加载失败。请刷新页面重试，已保存的记录和本机草稿会保留；不会重新发送模型请求。') }
const page = loader => defineAsyncComponent({ loader, loadingComponent, errorComponent, delay: 0, timeout: 20000 })
// A page chunk loads only when visited. No model or mutation is retried by a loader.
const pages = {
  notebooks: page(() => import('../features/notebooks/NotebooksPage.vue')),
  notebook: page(() => import('../features/notebooks/NotebookPage.vue')),
  study: page(() => import('../features/chat/StudyPage.vue')),
  practice: page(() => import('../features/practice/PracticePage.vue')),
  insights: page(() => import('../features/learning/InsightsPage.vue')),
  learn: page(() => import('../features/learning/FormalLearningPage.vue')),
  history: page(() => import('../features/learning/HistoryPage.vue')),
  notes: page(() => import('../features/notes/NotesPage.vue')),
  materials: page(() => import('../features/materials/MaterialsPage.vue')),
  resources: page(() => import('../features/materials/ReadMaterialsPage.vue')),
  bank: page(() => import('../features/practice/QuestionBankPage.vue')),
  architecture: page(() => import('../features/authoring/ArchitecturePage.vue')),
  builder: page(() => import('../features/authoring/BuilderPage.vue')),
}
pages.publish = pages.builder
const current = computed(() => pages[props.space.tab])
</script>
<template><component :is="current" :key="space.w.student" /></template>
