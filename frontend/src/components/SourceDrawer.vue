<script setup>
import { computed, nextTick, ref, watch, onUnmounted } from 'vue'
import MarkdownRenderer from './MarkdownRenderer.vue'
import { sourcePosition } from '../features/learning/journey.js'
const props = defineProps({ source: Object, embedded: Boolean, loading: Boolean })
const emit = defineEmits(['close','page'])
const dialog = ref(null)
const imageFailed=ref(false)
const page=computed(()=>props.source?.pages?.find(p=>p.ordinal===props.source.page_number))
let previousFocus
watch(() => props.source, async (value, old) => {
  if (value) {
    if (!old) previousFocus = document.activeElement
    imageFailed.value=false
    if(!old || value.source_id!==old.source_id){await nextTick(); dialog.value?.querySelector('button')?.focus()}
  } else previousFocus?.focus?.()
}, { immediate: true })
onUnmounted(() => previousFocus?.focus?.())
function keydown(event) {
  if (event.key === 'Escape') { event.preventDefault(); emit('close') }
  if (event.key !== 'Tab' || props.embedded) return
  const nodes = [...dialog.value.querySelectorAll('button:not(:disabled), a[href], summary, [tabindex="0"]')]
  const first = nodes[0], last = nodes.at(-1)
  if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus() }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus() }
}
const statuses = { current: '当前版本', modified: '来源已修改 · 以下保留当时快照', deleted: '来源已软删除 · 以下保留历史快照', unavailable: '当前来源不可用 · 以下为历史快照' }
</script>

<template>
  <div v-if="source" :class="embedded ? 'source-inline' : 'source-drawer-backdrop'" @click.self="!embedded && emit('close')">
    <section ref="dialog" class="source-drawer" :role="embedded ? 'region' : 'dialog'" :aria-modal="embedded ? undefined : 'true'" aria-labelledby="source-drawer-title" @keydown="keydown">
      <header><h2 id="source-drawer-title">{{ source.title }}</h2><button class="button secondary" aria-label="关闭原文抽屉" @click="emit('close')">关闭</button></header>
      <p class="badge">{{ source.source_type === 'personal_note' ? '个人笔记 · 非权威资料' : source.source_type==='uploaded_document'?'上传资料 · 未经人工核验':source.source_type==='teaching_material'?'教师课件 · 已确认片段':'课程资料 · 审阅状态以来源为准' }}</p>
      <p role="status">{{ statuses[source.current_status] }}</p>
      <p class="small muted">{{ source.preview ? '当前资料原文' : sourcePosition(source) + ' · 回答引用原文' }}</p>
      <div v-if="source.preview && source.pages?.length" class="source-page-picker"><label for="source-preview-page">{{source.file_format==='pptx'?'幻灯片':'页码 / 文本单位'}}</label><select id="source-preview-page" :value="source.page_number" :disabled="loading" @change="emit('page',Number($event.target.value))"><option v-for="p in source.pages" :key="p.ordinal" :value="p.ordinal">{{p.ordinal}} · {{p.readable?'可检索正文':'待识别或核对'}}</option></select><p v-if="loading" role="status">正在读取本地页面…</p><p v-if="page && !page.readable" class="wb-run-notice" role="status">本页尚无足够可检索正文，不能用来支持回答。可查看原页，并从资料旁选择识别缺失页面。</p><details v-if="page?.warnings.length"><summary>本页解析提示</summary><ul><li v-for="warning in page.warnings" :key="warning">{{warning}}</li></ul></details></div>
      <p v-if="!source.preview" class="small muted">这是回答生成时的片段快照，不能直接作为当前检索来源。</p>
      <MarkdownRenderer :source="source.raw_md" />
      <p v-if="source.truncated" role="status">本页文本较长，预览仅显示前60000字符；请打开原文件查看全文。</p>
      <template v-if="source.page_number"><p>{{source.file_format==='pptx'?'幻灯片':source.file_format && !['pdf','png','jpg','jpeg','webp'].includes(source.file_format)?'文本单位':'原文件页面'}} {{ source.page_number }} · {{ source.excerpt_origin==='corrected_transcription'?'经明确审核的校订转录':source.excerpt_origin==='reviewed_visual_transcription'?'经明确审核的模型转录':'原页解析片段' }}</p><details v-if="source.original_page_url && source.current_status!=='deleted'"><summary>查看对应原始课件页面</summary><img v-if="!imageFailed" :src="source.original_page_url" :alt="`课件第${source.page_number}页`" style="max-width:100%" @error="imageFailed=true" /><p v-else role="status">原页图片暂时无法显示，可打开原文件查看；已保存的文字快照仍保留。</p></details><p v-else-if="source.current_status==='deleted'">资料已软删除，当前入口不再提供原件访问；保留本轮引用片段快照。</p></template>
      <a v-if="source.original_file_url && source.current_status!=='deleted'" :href="source.original_file_url" target="_blank" rel="noopener noreferrer">打开对应版本的原文件</a><details><summary>来源与版本详情</summary><p class="wb-version">版本 {{ source.source_version }}<template v-if="!source.preview"><br />{{ source.section }} · 行 {{ source.start_line }}–{{ source.end_line }} · {{ source.citation_id }}</template></p><pre class="wb-raw">{{ source.raw_md }}</pre></details>
      <p v-if="source.source_type === 'personal_note'" class="small muted">删除笔记会使当前索引失效；软删除不会物理清除笔记正文或既有工作台引用快照。历史记录仍保存在本机数据库及可能的备份中。</p>
    </section>
  </div>
</template>
