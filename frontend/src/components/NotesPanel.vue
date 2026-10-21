<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import MarkdownRenderer from './MarkdownRenderer.vue'
import Icon from './Icon.vue'
import '../notes.css'

const props = defineProps({ workspace: { type: Object, required: true }, knowledge: Array })
const mode = ref('edit'), preview = ref('')
let timer
watch(() => [props.workspace.draft?.id, props.workspace.draft?.content_md], ([id, text], previous) => {
  clearTimeout(timer)
  if (!previous || id !== previous[0]) preview.value = text || ''
  else timer = setTimeout(() => { preview.value = text || '' }, 300)
}, { immediate: true })
const bytes = computed(() => new TextEncoder().encode(props.workspace.draft?.content_md || '').length)
const editingDisabled = computed(() => ['open', 'delete', 'import'].includes(props.workspace.busy))
function importFile(event) {
  props.workspace.importFile(event.target.files?.[0])
  event.target.value = ''
}
onMounted(props.workspace.load)
onUnmounted(() => clearTimeout(timer))
</script>

<template>
  <section class="notes-page" aria-label="我的学习笔记">
    <div v-if="workspace.error" class="alert alert-error" role="alert">{{ workspace.error }}</div>
    <div v-if="workspace.storageError" class="alert alert-error" role="alert">{{ workspace.storageError }}</div>
    <p v-if="workspace.notice" class="alert alert-info" role="status">{{ workspace.notice }}</p>
    <div class="notes-layout">
      <aside class="panel notes-list-panel" aria-label="笔记列表">
        <div class="panel-heading"><h2>我的笔记</h2><span class="badge">{{ workspace.items.length }} 篇</span></div>
        <div class="notes-actions">
          <button class="button primary" :disabled="Boolean(workspace.busy || workspace.pending)" @click="workspace.newNote()">新建笔记</button>
          <label class="button secondary notes-import">导入文件<input type="file" accept=".md,.markdown,.txt,text/plain,text/markdown" class="sr-only" aria-label="导入 UTF-8 Markdown 或 TXT 笔记" :disabled="Boolean(workspace.busy || workspace.pending)" @change="importFile" /></label>
        </div>
        <p class="small muted">UTF-8 Markdown/TXT，最多 64 KiB；导入后保存到当前学习标识。</p>
        <form class="notes-filter" @submit.prevent="workspace.load()">
          <label for="notes-query">按标题搜索</label><input id="notes-query" v-model="workspace.query" maxlength="100" placeholder="输入标题关键词" />
          <label for="notes-knowledge-filter">按知识点筛选</label><select id="notes-knowledge-filter" v-model="workspace.knowledge"><option value="">全部知识点</option><option v-for="point in knowledge" :key="point.id" :value="point.id">{{ point.name }}</option></select>
          <button class="button secondary" :disabled="Boolean(workspace.busy)">筛选 / 刷新列表</button>
        </form>
        <p v-if="workspace.busy === 'load'" role="status">正在读取笔记…</p>
        <ul v-if="workspace.items.length" class="notes-list"><li v-for="note in workspace.items" :key="note.id"><button :class="{ active: workspace.draft?.id === note.id }" :disabled="Boolean(workspace.busy || workspace.pending)" @click="workspace.open(note.id)"><strong>{{ note.title }}</strong><span>版本 {{ note.revision }} · {{ note.knowledge_point_ids.length }} 个关联知识点</span></button></li></ul>
        <div v-else-if="!workspace.busy" class="notes-empty"><Icon name="book" :size="26" /><p>{{ workspace.query || workspace.knowledge ? '当前筛选下没有笔记。' : '写下第一个理解，之后可以继续补充。' }}</p></div>
        <div v-if="workspace.localDrafts.length" class="notes-local-drafts"><h3>本机未完成草稿</h3><button v-for="note in workspace.localDrafts" :key="note.id" class="text-button" :disabled="Boolean(workspace.busy || workspace.pending)" @click="workspace.open(note.id)">{{ note.title || '未命名草稿' }}</button></div>
      </aside>
      <section class="panel note-editor-panel" aria-label="笔记编辑与预览">
        <template v-if="workspace.draft">
          <div class="note-editor-heading"><h2>{{ workspace.baseline ? '编辑笔记' : '新笔记草稿' }}</h2><span class="badge" role="status" aria-live="polite">{{ workspace.status }}</span></div>
          <label class="field-label" for="note-title">笔记标题</label><input id="note-title" v-model="workspace.draft.title" maxlength="120" :disabled="editingDisabled" />
          <fieldset class="note-links" :disabled="editingDisabled"><legend>关联知识点（可多选）</legend><label v-for="point in knowledge" :key="point.id"><input v-model="workspace.draft.knowledge_point_ids" type="checkbox" :value="point.id" />{{ point.name }}</label></fieldset>
          <div class="note-save-actions"><button class="button primary" :disabled="Boolean(workspace.busy || (!workspace.dirty && !workspace.pending))" @click="workspace.save()">{{ workspace.busy === 'save' || workspace.busy === 'import' ? '保存中…' : workspace.pending ? workspace.pending.retryReady ? '重试原请求' : '核对请求结果' : '保存笔记' }}</button><button class="button secondary" :disabled="Boolean(workspace.busy || workspace.pending)" @click="workspace.requestDelete()">{{ workspace.baseline ? '删除笔记' : '移除本机草稿' }}</button><span class="small muted">{{ bytes }} / 65536 字节 · {{ workspace.baseline ? `已保存版本 ${workspace.baseline.revision}` : '尚未保存到服务器' }}</span></div>
          <div v-if="workspace.conflict" class="note-conflict" role="alert"><p>服务器版本已变化，本地修改没有被覆盖。</p><button class="button secondary" :disabled="Boolean(workspace.busy || workspace.pending)" @click="workspace.readServer()">保留副本并读取服务器</button><button class="button secondary" :disabled="Boolean(workspace.busy || workspace.pending)" @click="workspace.saveAsNew()">将本地内容另存为新笔记</button></div>
          <div class="notes-view-switch" aria-label="编辑与预览"><button :aria-pressed="mode === 'edit'" @click="mode = 'edit'">编辑</button><button :aria-pressed="mode === 'preview'" @click="mode = 'preview'">预览</button></div>
          <div class="note-editor-grid" :class="`mode-${mode}`">
            <div class="note-edit"><label class="field-label" for="note-content">Markdown 原文</label><textarea id="note-content" v-model="workspace.draft.content_md" rows="20" :disabled="editingDisabled" spellcheck="false" placeholder="# 我的理解&#10;&#10;行内公式 $w$，块级公式使用 $$。" @keydown.ctrl.s.prevent="workspace.save()" @keydown.meta.s.prevent="workspace.save()" /></div>
            <div class="note-preview" role="region" aria-label="Markdown 实时预览"><h3>实时预览</h3><MarkdownRenderer v-if="preview" :source="preview" /><p v-else class="muted">正文将在这里显示，支持 Markdown 和 LaTeX。</p></div>
          </div>
          <p v-if="workspace.baseline?.generation_origin" class="alert alert-info" role="status">来源：工作台回答，生成于 {{ new Date(workspace.baseline.generation_origin.generated_at).toLocaleString('zh-CN') }}。{{ workspace.baseline.generation_origin.edited || workspace.dirty ? '笔记已有修改，当前内容不代表原始回答。' : '当前为另存初版，可继续编辑。' }}原回答及引用保存在工作台历史（{{ workspace.baseline.generation_origin.request_id }}）。</p>
          <p class="small muted note-scope-notice">笔记仅在当前演示学习标识下管理；该标识不是账号认证。索引状态：{{ workspace.draft.index_status || '待保存' }}。可在资料学习工作台明确选择参与检索；发送模型前需本轮同意。保存或编辑笔记不改变 BKT。</p>
        </template>
        <div v-else class="empty-state"><Icon name="book" :size="36" /><h3>把理解写成自己的笔记。</h3><p>新建、导入或打开已有笔记，公式和原文会一起保存。</p></div>
      </section>
    </div>
  </section>
</template>
