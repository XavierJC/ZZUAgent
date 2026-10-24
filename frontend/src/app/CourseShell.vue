<script setup>
import { computed } from 'vue'
import Icon from '../components/Icon.vue'
import { studentTabs, builderTabs, auxiliaryTabs as auxiliary } from './navigation.js'
const props = defineProps({ space: Object })
const w = computed(() => props.space.w), n = computed(() => props.space.features.notes || {})
const tab = computed(() => props.space.tab), isBuilder = computed(() => props.space.isBuilder)
const tabs = computed(() => isBuilder.value ? builderTabs : studentTabs)
const pageTitle = computed(() => props.space.pageTitle)
const goTab = (...args) => props.space.navigate(...args)
const leaveStudent = () => props.space.leaveStudent()
const refreshCurrent = () => props.space.refreshCurrent()
</script>
<template>
  <div class="app-shell">
    <aside class="sidebar">
      <a class="brand" href="#" @click.prevent="goTab('study')"><span class="brand-symbol"><Icon name="cap" :size="27" /></span><span><strong>智学郑大</strong><small>EduAgent</small></span></a>
      <details class="workspace-management"><summary>课程管理</summary><div class="workspace-switch" aria-label="工作区切换"><button :aria-pressed="!isBuilder" @click="goTab('study')">学生学习</button><button :aria-pressed="isBuilder" @click="goTab('builder')">课程构建</button></div><p class="small muted">本机内容维护，不是身份认证。</p></details><p class="sidebar-label">{{ isBuilder ? '本机内容维护' : '学习空间' }}</p>
      <nav aria-label="学习导航"><button v-for="item in tabs" :key="item.id" :class="{ active: tab === item.id }" :aria-current="tab === item.id ? 'page' : undefined" @click="goTab(item.id)"><Icon :name="item.icon" /><span>{{ item.name }}</span><span v-if="tab === item.id" class="nav-dot" /></button></nav><details v-if="!isBuilder" class="more-tools"><summary>更多工具</summary><nav aria-label="学习辅助"><button v-for="item in auxiliary" :key="item.id" :class="{active:tab===item.id}" @click="goTab(item.id)"><Icon :name="item.icon" />{{ item.name }}</button></nav></details>
      <div class="sidebar-course"><span class="course-art"><Icon name="book" :size="25" /></span><p class="eyebrow">CURRENT COURSE</p><h3>{{space.course.title}}</h3><p>{{space.course.subtitle}}</p><div class="course-line" /><span>诊断 · 学习 · 练习 · 反馈</span></div>
      <div class="sidebar-bottom"><span class="status-dot" :class="{ online: w.health?.status === 'ok' }" />{{ w.health ? '本地学习服务' : '连接学习服务中' }}<small>校园创新应用 · 演示原型</small></div>
    </aside>

    <div class="main-shell">
      <header class="topbar"><div class="breadcrumb">{{space.course.title}} <span>/</span><strong>{{ pageTitle }}</strong></div><div class="topbar-actions"><span v-if="w.active" class="learner-chip">{{ w.student }}</span><button class="icon-button" :disabled="Boolean(w.busy || n.busy)" :aria-label="tab === 'notes' ? '刷新笔记列表' : '刷新学习记录'" title="刷新学习记录，不调用模型" @click="refreshCurrent()"><Icon name="refresh" :size="18" /></button><button v-if="w.active" class="icon-button" :disabled="Boolean(w.busy || w.pending || n.busy)" aria-label="切换学习标识" title="切换学习标识，保留学习记录" @click="leaveStudent()"><Icon name="logout" :size="18" /></button></div></header>
      <main id="main-content" class="workspace">
        <slot />
        <footer class="workspace-footer"><span><span class="tiny-dot" />{{w.reviewNotice}}</span><span>EduAgent · 让学习有迹可循</span></footer>
      </main>
    </div>
  </div>
</template>

