<script setup>
import { onMounted } from 'vue'
import MarkdownRenderer from '../components/MarkdownRenderer.vue'
const props=defineProps({workspace:Object})
defineEmits(['navigate','edit-note'])
onMounted(()=>props.workspace.load())
</script>
<template>
  <section class="phase5-split"><aside class="panel"><h2>学习资料</h2><p>查看当前演示标识有权访问的资料；不因查看或切换而外发或更新掌握度。</p><button v-for="r in workspace.resources.filter(r=>r.status==='active')" :key="r.resource_id" class="pb-item" @click="workspace.selectResource(r)">{{ r.title }} · {{ r.rag_available?'可本地检索':'原件/解析可查看' }}</button><button class="button secondary" @click="$emit('navigate','materials')">到课程构建管理资料</button></aside><section class="panel"><p v-if="workspace.error" role="alert">{{ workspace.error }}</p><template v-if="workspace.resource"><h2>{{ workspace.resource.title }}</h2><button v-if="workspace.resource.original_source_type==='personal_note'" class="button secondary" @click="$emit('edit-note',workspace.resource.original_source_id)">编辑我的笔记</button><a v-if="workspace.resource.original_source_type==='document'" :href="`/api/v1/students/${encodeURIComponent(workspace.owner)}/documents/${workspace.resource.original_source_id}/original?version_id=${encodeURIComponent(workspace.resource.source_version)}`">查看原件（当时版本）</a><article v-for="u in workspace.sourceUnits" :key="u.id"><p>{{ u.location?.page_number ? '第'+u.location.page_number+'页' : u.location?.slide_number ? '幻灯片'+u.location.slide_number : '原文' }}</p><MarkdownRenderer :source="u.text" /></article></template><p v-else>选择资料查看原文。教师课件尚未全面接入RAG，不宣称自动定位知识片段。</p></section></section>
</template>
