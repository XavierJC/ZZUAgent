<script setup>
import Icon from '../components/Icon.vue'
defineProps({ space: Object })
const emit = defineEmits(['navigate'])
const main = [{ id:'notebooks', title:'学习', icon:'home' }, { id:'practice', title:'练习', icon:'check' }, { id:'insights', title:'进度', icon:'activity' }]
const tools = [{id:'notes',title:'我的笔记',icon:'note'},{id:'history',title:'学习记录',icon:'history'}]
const management = [{id:'materials',title:'课程资料'},{id:'bank',title:'题目整理与审核'},{id:'resources',title:'原文资料'},{id:'builder',title:'课程概览'},{id:'architecture',title:'知识体系'},{id:'publish',title:'课程审核与发布'},{id:'study',title:'独立资料助教'},{id:'learn',title:'正式诊断与复测'}]
const selected = (page, space) => space.tab === page || page === 'notebooks' && space.tab === 'notebook' || page==='practice' && space.tab==='learn'
</script>
<template>
  <div class="sidebar-content">
    <a href="#/notebooks" class="product-brand" @click.prevent="emit('navigate','notebooks')"><span><Icon name="cap" :size="23" /></span><strong>EduAgent<small>智学郑大 · 学习空间</small></strong></a>
    <button v-if="space.w.active && space.tab!=='notebooks'" class="product-new" @click="emit('navigate','notebooks',{new:'1'})"><Icon name="plus" :size="17" />新建笔记本</button>
    <p class="product-nav-label">开始学习</p>
    <nav aria-label="学习导航"><button v-for="item in main" :key="item.id" :class="{selected:selected(item.id,space)}" :aria-current="selected(item.id,space)?'page':undefined" @click="emit('navigate',item.id)"><Icon :name="item.icon" :size="19" />{{item.title}}</button></nav>
    <details class="product-tools" :open="tools.some(i=>i.id===space.tab)"><summary>我的记录</summary><nav aria-label="学习辅助"><button v-for="item in tools" :key="item.id" :class="{selected:space.tab===item.id}" :aria-current="space.tab===item.id?'page':undefined" @click="emit('navigate',item.id)"><Icon :name="item.icon" :size="18" />{{item.title}}</button></nav></details>
    <details class="product-management" :open="space.isBuilder"><summary><Icon name="settings" :size="18" />资料与高级设置</summary><nav aria-label="课程管理"><button v-for="item in management" :key="item.id" :class="{selected:space.tab===item.id}" :aria-current="space.tab===item.id && item.id!=='learn'?'page':undefined" @click="emit('navigate',item.id)">{{item.title}}</button></nav><p>整理和发布工具按需使用，不影响直接学习。</p></details>
    <div class="product-sidebar-bottom"><span class="product-status-dot" />本地学习空间<small>资料与记录保存在本机</small></div>
  </div>
</template>
