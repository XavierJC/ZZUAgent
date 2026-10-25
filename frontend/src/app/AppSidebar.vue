<script setup>
import Icon from '../components/Icon.vue'
defineProps({ space: Object })
const emit = defineEmits(['navigate'])
const main = [{ id:'notebooks', title:'学习笔记本', icon:'home' }, { id:'practice', title:'题库与练习', icon:'check' }, { id:'insights', title:'学习进度', icon:'activity' }]
const tools = [{id:'study',title:'资料助教',icon:'spark'},{id:'notes',title:'我的笔记',icon:'note'},{id:'history',title:'学习记录',icon:'history'},{id:'learn',title:'正式诊断与复测',icon:'target'},{id:'resources',title:'原文资料',icon:'folder'}]
const management = [{id:'builder',title:'课程概览'},{id:'materials',title:'课程资料'},{id:'architecture',title:'知识体系'},{id:'bank',title:'题目整理与审核'},{id:'publish',title:'课程审核与发布'}]
const selected = (page, space) => space.tab === page || page === 'notebooks' && space.tab === 'notebook'
</script>
<template>
  <div class="sidebar-content">
    <a href="#/notebooks" class="product-brand" @click.prevent="emit('navigate','notebooks')"><span><Icon name="cap" :size="23" /></span><strong>EduAgent<small>智学郑大 · 学习空间</small></strong></a>
    <button v-if="space.w.active" class="product-new" @click="emit('navigate','notebooks',{new:'1'})"><Icon name="plus" :size="17" />新建笔记本</button>
    <p class="product-nav-label">学习空间</p>
    <nav aria-label="学习导航"><button v-for="item in main" :key="item.id" :class="{selected:selected(item.id,space)}" :aria-current="selected(item.id,space)?'page':undefined" @click="emit('navigate',item.id)"><Icon :name="item.icon" :size="19" />{{item.title}}</button></nav>
    <details class="product-tools" :open="tools.some(i=>i.id===space.tab)"><summary>学习工具</summary><nav aria-label="学习辅助"><button v-for="item in tools" :key="item.id" :class="{selected:space.tab===item.id}" :aria-current="space.tab===item.id?'page':undefined" @click="emit('navigate',item.id)"><Icon :name="item.icon" :size="18" />{{item.title}}</button></nav></details>
    <details class="product-management" :open="space.isBuilder"><summary><Icon name="settings" :size="18" />课程管理</summary><nav aria-label="课程管理"><button v-for="item in management" :key="item.id" :class="{selected:space.tab===item.id}" :aria-current="space.tab===item.id?'page':undefined" @click="emit('navigate',item.id)">{{item.title}}</button></nav><p>本机内容维护 · 演示标识不是账号认证</p></details>
    <div class="product-sidebar-bottom"><span class="product-status-dot" />本地学习空间<small>资料与记录保存在本机</small></div>
  </div>
</template>
