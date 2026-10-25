<script setup>
import { computed, ref } from 'vue'
import Icon from '../../components/Icon.vue'
import { sourceKey } from '../chat/useStudyWorkbench.js'
defineProps({entry:Object,archived:Boolean})
const emit=defineEmits(['add'])
const query=ref('')
const label=s=>({personal_note:'个人笔记',uploaded_document:'上传资料 · 未核验',teaching_material:'已确认课件',course_material:'课程资料'}[s.source_type] || '资料')
const selected=(w,s)=>w.selected.some(r=>sourceKey(r)===sourceKey(s) && r.source_version===s.source_version)
</script>
<template><aside class="notebook-sources" aria-label="本笔记本资料"><header><h2><Icon name="folder" :size="18" />资料来源</h2><button v-if="!archived" class="product-icon-button" aria-label="管理笔记本资料" title="添加、移除或更新资料版本" @click="emit('add')"><Icon name="plus" :size="18" /></button></header><button v-if="!archived" class="product-source-add" @click="emit('add')"><Icon name="plus" :size="16" />添加或管理资料</button><label class="product-search"><Icon name="search" :size="15" /><input v-model="query" aria-label="搜索笔记本资料" placeholder="搜索资料…" /></label><p class="notebook-source-hint">勾选用于问答，打开查看原文。</p><ul><li v-for="source in entry.chat.sources.filter(s=>s.title.toLowerCase().includes(query.toLowerCase()))" :key="sourceKey(source)" :class="{chosen:selected(entry.chat,source)}"><div><input type="checkbox" :checked="selected(entry.chat,source)" :disabled="archived || source.current_status!=='current' || !['ready','empty'].includes(source.index_status)" :aria-label="`参与问答：${source.title}`" @change="entry.chat.toggle(source,$event.target.checked)" /><button :disabled="source.current_status!=='current'" @click="entry.chat.open(source)"><strong>{{source.title}}</strong><small>{{label(source)}} · {{source.current_status!=='current'?'版本已变化':source.index_status==='ready'?'已就绪':source.index_status==='empty'?'暂无正文':'未就绪'}}</small><small v-if="source.total_units!=null">可检索 {{source.readable_units}} / {{source.total_units}} 页或文本单位</small></button></div></li></ul><div v-if="!entry.chat.sources.length" class="notebook-source-empty"><Icon name="folder" :size="30" /><p>为这个学习主题添加课件或笔记。</p></div><footer>资料本体保留在本机；加入笔记本不会复制原件。个人笔记默认不参与问答。</footer></aside></template>
