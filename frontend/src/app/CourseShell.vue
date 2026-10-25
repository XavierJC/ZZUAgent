<script setup>
import { ref, watch } from 'vue'
import LegacyShell from './LegacyShell.vue'
import AppSidebar from './AppSidebar.vue'
import ProductDialog from '../shared/ProductDialog.vue'
import Icon from '../components/Icon.vue'
import '../product.css'
import '../shared/academic.css'
const props = defineProps({ space: Object })
const menuOpen = ref(false), collapsed = ref(false), main = ref(null)
watch(() => props.space.tab, () => { menuOpen.value = false })
function navigate(page, params = {}) { props.space.navigate(page, params); menuOpen.value = false }
</script>
<template>
  <LegacyShell v-if="!space.modern" :space="space"><slot /></LegacyShell>
  <div v-else class="product-shell" :class="{'sidebar-collapsed':collapsed,'management-shell':space.isBuilder}">
    <a class="skip-link" href="#main-content" @click.prevent="main?.focus()">跳到主要内容</a>
    <aside v-if="!collapsed" class="product-sidebar"><AppSidebar :space="space" @navigate="navigate" /></aside>
    <div class="product-main-shell">
      <header class="product-topbar"><div><button class="product-icon-button sidebar-toggle" :aria-label="collapsed?'展开侧栏':'收起侧栏'" :aria-expanded="!collapsed" @click="collapsed=!collapsed"><Icon name="menu" :size="19" /></button><button class="product-icon-button mobile-menu-toggle" aria-label="打开学习导航" :aria-expanded="menuOpen" @click="menuOpen=true"><Icon name="menu" :size="19" /></button><span class="product-course">机器学习</span><Icon name="chevron" :size="13" /><strong>{{space.pageTitle}}</strong><span v-if="space.isBuilder" class="shell-context-label">课程构建</span></div><div class="product-top-actions"><button :disabled="Boolean(space.w.busy)" aria-label="刷新当前页面" title="只读取已保存记录" @click="space.refreshCurrent()"><Icon name="refresh" :size="17" /></button><details class="product-profile"><summary><span class="product-avatar">{{space.w.student?.slice(0,1).toUpperCase() || 'E'}}</span><span>我的学习</span></summary><div><strong>{{space.w.student || '尚未进入学习空间'}}</strong><p>演示学习标识，不具备身份认证能力。</p><button v-if="space.w.active" :disabled="Boolean(space.w.busy || space.w.pending)" @click="space.leaveStudent()">切换学习标识</button></div></details></div></header>
      <main id="main-content" ref="main" tabindex="-1" class="product-main" :class="{'product-notebook-main':space.tab==='notebook'}"><slot /></main>
    </div>
    <ProductDialog :open="menuOpen" title="学习导航" @close="menuOpen=false"><AppSidebar :space="space" @navigate="navigate" /></ProductDialog>
  </div>
</template>
