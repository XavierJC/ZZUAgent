<script setup>
import MarkdownRenderer from './MarkdownRenderer.vue'
import SourceDrawer from './SourceDrawer.vue'
const props = defineProps({ workspace: Object, selfWorkspace: Object, capabilities: Object })
const labels = { teacher_consent_required: '本轮指南未单独授权上传资料外发，仅提供本地规则和引用。', rules_requested: '本轮为本地规则指南，没有调用模型。', personal_consent_required: '本轮未同意个人笔记外发，仅保留规则指南和本地参考。',
  model_disabled: '模型未启用，规则指南仍可使用。', insufficient_evidence: '所选资料依据不足，保留规则指南，不编造引用。',
  model_timeout: '模型超时，执行情况待确认，不自动重发。', network_error: '模型网络异常，执行情况待确认，不自动重发。',
  execution_unconfirmed: '原请求执行情况待确认，只读取保存记录。', tool_scope_rejected: '模型越权工具请求已拒绝，保留程序规则。',
  unverified_model_answer: '模型输出未通过约束检查，保留规则指南。', context_changed: '生成期间学情或资料变化，当前展示当时快照。' }
const date = value => new Date(value).toLocaleString('zh-CN')
function citation(id) { const item = props.workspace.current?.citations.find(c => c.citation_id === id); if (item) props.workspace.citation(item) }
</script>
<template>
  <section class="panel study-guide-panel" aria-labelledby="study-guide-title">
    <h2 id="study-guide-title">我的学习指南</h2><p class="small muted">只使用已保存学情；生成指南不会修改BKT或分配新题。查看历史不重新调用模型。</p>
    <div v-if="workspace.error" class="alert alert-error" role="alert">{{ workspace.error }}</div><p v-if="workspace.notice" role="status" class="small">{{ workspace.notice }}</p>
    <form class="guide-form" @submit.prevent="workspace.generate()">
      <label for="guide-mode">指南方式<select id="guide-mode" v-model="workspace.mode"><option value="rules">本地规则指南</option><option value="model" :disabled="!capabilities?.model_enabled">{{ capabilities?.model_enabled ? `规则 + ${capabilities.provider}辅助讲解` : '模型未启用' }}</option></select></label>
      <label v-if="workspace.mode === 'rules'" class="guide-check"><input v-model="workspace.useSources" type="checkbox" />附加当前选中资料的本地检索片段</label>
      <p class="small">本轮资料：{{ workspace.selected.length ? workspace.selected.map(s => s.title).join('、') : '未使用资料，仅依据保存学情；不会检索全库' }}</p>
      <p v-if="workspace.mode === 'model'" class="small">将向 {{ capabilities?.provider }} / {{ capabilities?.model }} 发送本轮目标、自评/信心、BKT及答题摘要、所选资料的相关片段；不发送身份标识、完整作答记录或旧聊天。</p>
      <div v-if="workspace.mode === 'model' && workspace.personal.length" class="wb-consent"><strong>指南个人笔记外发同意</strong><p>本轮相关片段来自：{{ workspace.personal.map(s => s.title).join('、') }}。此授权与Chat独立，不跨轮复用。</p><label><input v-model="workspace.consent" type="checkbox" />我同意仅本轮指南发送上述笔记的相关片段</label><small>未同意时整轮保留本地规则与检索。</small></div>
      <p v-if="!selfWorkspace.canGenerate" class="small" role="status">请先保存自评或核对版本/原提交，再依据已保存学情生成指南。</p>
      <button class="button primary" :disabled="Boolean(workspace.busy || workspace.pendingId || !workspace.ready || !selfWorkspace.canGenerate || (workspace.mode === 'model' && !workspace.selected.length))">{{ workspace.busy === 'generate' ? '正在生成指南…' : workspace.mode === 'model' && (!workspace.personal.length || workspace.consent) ? '生成指南与辅助讲解' : '生成并保存本地指南' }}</button>
    </form>
    <div v-if="workspace.pendingId" class="wb-pending" role="status"><p>指南请求 {{ workspace.pendingId }} 待确认。</p><button class="button secondary" :disabled="Boolean(workspace.busy)" @click="workspace.load()">查询原指南状态</button><button class="wb-text-button" :disabled="Boolean(workspace.busy)" @click="workspace.release()">结束等待（新模型请求可能另计费）</button></div>
    <article v-if="workspace.current" class="saved-guide"><p class="small muted">{{ date(workspace.current.created_at) }} · 模型调用 {{ workspace.current.model_calls }}次 · {{ workspace.current.status }}</p><p v-if="workspace.stale" class="wb-run-notice" role="status">此指南可能过期：答题、自评、资料或规则版本已变化。以下保留生成时内容，不代表当前版本。</p><p v-if="workspace.current.reason" class="small" role="status">{{ labels[workspace.current.reason] || '本轮模型补充未完成，保留规则与明确状态，不自动重新生成。' }}</p>
      <MarkdownRenderer :source="workspace.current.rules_md" />
      <template v-if="workspace.current.explanation_md"><h3>模型辅助讲解</h3><p class="small muted">辅助文字可能有误，不覆盖程序重点、事实数值或正式规则。</p><MarkdownRenderer :source="workspace.current.explanation_md" :citation-ids="workspace.current.citations.map(c => c.citation_id)" @citation="citation" /></template>
      <h3 v-if="workspace.current.citations.length">本轮资料参考</h3><button v-for="item in workspace.current.citations" :key="item.citation_id" class="wb-citation" @click="workspace.citation(item)">[{{ item.citation_id }}] {{ item.title }}<span>{{ item.source_type === 'personal_note' ? '个人笔记 · 未核验' : '课程资料' }} · 行{{ item.start_line }}–{{ item.end_line }}</span></button>
    </article>
    <details class="guide-history"><summary>指南历史（最近20轮）</summary><button type="button" class="wb-text-button" :disabled="Boolean(workspace.busy)" @click="workspace.load()">只读刷新指南历史</button><button v-for="run in workspace.runs" :key="run.request_id" type="button" class="wb-history-item" :aria-pressed="workspace.current?.request_id === run.request_id" @click="workspace.view(run)">{{ date(run.created_at) }} · 答题{{ run.snapshot.learning_revision }}/自评{{ run.snapshot.assessment_revision }} · {{ run.status }}</button><p v-if="!workspace.runs.length" class="small muted">尚无指南记录。</p></details>
    <SourceDrawer :source="workspace.drawer" @close="workspace.drawer = null" />
  </section>
</template>
