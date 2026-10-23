<script setup>
import { nextTick, ref, watch, onUnmounted } from 'vue'
import MarkdownRenderer from './MarkdownRenderer.vue'
const props = defineProps({ source: Object })
const emit = defineEmits(['close'])
const dialog = ref(null)
let previousFocus
watch(() => props.source, async (value, old) => {
  if (value) {
    if (!old) previousFocus = document.activeElement
    await nextTick(); dialog.value?.querySelector('button')?.focus()
  } else previousFocus?.focus?.()
})
onUnmounted(() => previousFocus?.focus?.())
function keydown(event) {
  if (event.key === 'Escape') { event.preventDefault(); emit('close') }
  if (event.key !== 'Tab') return
  const nodes = [...dialog.value.querySelectorAll('button:not(:disabled), a[href], summary, [tabindex="0"]')]
  const first = nodes[0], last = nodes.at(-1)
  if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus() }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus() }
}
const statuses = { current: '当前版本', modified: '来源已修改 · 以下保留当时快照', deleted: '来源已软删除 · 以下保留历史快照', unavailable: '当前来源不可用 · 以下为历史快照' }
</script>

<template>
  <div v-if="source" class="source-drawer-backdrop" @click.self="emit('close')">
    <section ref="dialog" class="source-drawer" role="dialog" aria-modal="true" aria-labelledby="source-drawer-title" @keydown="keydown">
      <header><h2 id="source-drawer-title">{{ source.title }}</h2><button class="button secondary" aria-label="关闭原文抽屉" @click="emit('close')">关闭</button></header>
      <p class="badge">{{ source.source_type === 'personal_note' ? '个人笔记 · 非权威资料' : source.source_type==='teaching_material'?'教师课件 · 已确认片段':'课程资料 · 审阅状态以来源为准' }}</p>
      <p role="status">{{ statuses[source.current_status] }}</p>
      <p class="small muted wb-version">版本 {{ source.source_version }}<template v-if="!source.preview"><br />{{ source.section }} · 行 {{ source.start_line }}–{{ source.end_line }} · {{ source.citation_id }}</template></p>
      <p v-if="!source.preview" class="small muted">这是回答生成时的片段快照，不能直接作为当前检索来源。</p>
      <MarkdownRenderer :source="source.raw_md" />
      <template v-if="source.page_number"><p>原PDF第{{ source.page_number }}页 · {{ source.excerpt_origin==='corrected_transcription'?'经明确审核的校订转录':source.excerpt_origin==='reviewed_visual_transcription'?'经明确审核的模型转录':'原页解析片段' }}</p><details v-if="source.original_page_url && source.current_status!=='deleted'"><summary>查看对应原始课件页面</summary><img :src="source.original_page_url" :alt="`课件第${source.page_number}页`" style="max-width:100%" /></details><p v-else-if="source.current_status==='deleted'">原件已删除，仍保留本轮引用片段快照。</p></template>
      <details><summary>查看原始 Markdown</summary><pre class="wb-raw">{{ source.raw_md }}</pre></details>
      <p v-if="source.source_type === 'personal_note'" class="small muted">删除笔记会使当前索引失效；软删除不会物理清除笔记正文或既有工作台引用快照。历史记录仍保存在本机数据库及可能的备份中。</p>
    </section>
  </div>
</template>
