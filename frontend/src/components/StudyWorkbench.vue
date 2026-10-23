<script setup>
import { onMounted, ref } from 'vue'
import { sourceKey } from '../useStudyWorkbench.js'
import MarkdownRenderer from './MarkdownRenderer.vue'
import MasteryPanel from './MasteryPanel.vue'
import SourceDrawer from './SourceDrawer.vue'
import SelfAssessmentPanel from './SelfAssessmentPanel.vue'
import LearningGuidancePanel from './LearningGuidancePanel.vue'
import StudyGuidePanel from './StudyGuidePanel.vue'
import '../workbench.css'
import '../study-guidance.css'
const props = defineProps({ workspace: { type: Object, required: true }, snapshot: Object, goalNames: String, currentTopic: String, selfWorkspace: Object, guideWorkspace: Object, documentWorkspace: Object, architectureWorkspace: Object, bankWorkspace: Object })
const emit = defineEmits(['navigate', 'edit-note'])
const indexNames = { ready: '已就绪', empty: '无可检索正文', pending: '等待索引', building: '正在索引', failed: '索引失败', disabled: '索引停用' }
const reasons = { teacher_consent_required: '本轮未同意教师课件片段外发，仅本地检索。', local_requested: '本轮仅本地检索，未调用模型。', personal_consent_required: '本轮未同意个人笔记外发，已仅在本地检索。',
  model_disabled: '模型未启用，已提供本地检索结果。', insufficient_evidence: '所选资料依据不足，本轮未调用模型。',
  tool_scope_rejected: '模型工具请求超出本轮范围，已拒绝并返回本地片段。', unverified_model_answer: '模型回答格式或引用未通过校验，已返回可用的本地结果。',
  model_call_limit: '已达到模型调用预算，返回本地片段。', model_timeout: '模型超时，可能已执行；不会自动重发。', network_error: '模型网络异常，执行情况待确认；不会自动重发。',
  authentication_failed: '模型认证失败，返回本地片段。', insufficient_balance: '模型服务余额不足，返回本地片段。',
  incomplete_model_response: '模型未返回完整内容，具体终止原因不可用；不会自动重发。',
  model_output_truncated: '模型输出达到长度或上下文上限，回答被截断；已保留本轮结果，不会自动重发。',
  model_content_filtered: '模型服务过滤了本轮输出，未取得完整回答；不会自动重发。',
  model_resource_exhausted: '模型服务因资源不足中断输出；不会自动重发。', model_aborted: '模型服务中断了本轮生成；不会自动重发。',
  rate_limited: '模型服务请求受限，请稍后明确发起新请求；不会自动重发。', upstream_error: '模型上游服务返回异常，执行情况待确认；不会自动重发。',
  invalid_model_response: '模型服务返回了无法识别的响应，执行情况待确认；不会自动重发。',
  execution_unconfirmed: '原请求执行情况待确认；当前仅查询已保存记录。', context_changed: '生成期间资料或学习状态已变化；本结果属于当时版本。' }
const date = value => new Date(value).toLocaleString('zh-CN')
const validationErrors = { invalid_json: '返回内容不是可解析的JSON。', duplicate_json_fields: '返回JSON含重复字段，无法明确解释。',
  invalid_fields: '返回结构不符合该回答接口的约定。', invalid_answer: '回答为空、类型错误或超出长度限制。',
  missing_answer: '未找到可识别的回答正文字段。', ambiguous_fields: '返回了相互冲突的回答字段，无法安全确定正文。',
  forbidden_output_fields: '返回包含身份、权限或评分等控制字段，未采用这些字段。',
  invalid_citation_list: '引用列表类型、数量或编号格式不正确。', unknown_citation: '引用了本轮未取得的资料片段。',
  missing_citations: '使用资料回答时未提供引用。', unexpected_citations: '本轮没有资料片段，却返回了引用标记。',
  citation_mismatch: '正文引用标记与引用列表不一致。', disallowed_links: '回答包含不允许的链接。',
  supplement_citation: '模型知识补充不能借用或伪造本地资料引用。' }
function isSelected(source) { return props.workspace.selected.some(s => sourceKey(s) === sourceKey(source) && s.source_version === source.source_version) }
function openInline(id) { const item = props.workspace.current?.citations.find(c => c.citation_id === id); if (item) props.workspace.citation(item) }
async function saveAndEdit() { const result = await props.workspace.save(); if (result && !result.deleted) emit('edit-note', result.note_id) }
onMounted(() => props.workspace.load())
onMounted(() => { props.selfWorkspace?.load(); props.guideWorkspace?.load() })
</script>

<template>
  <section class="study-workbench" aria-label="资料学习工作台">
    <div v-if="workspace.current?.lesson_context" class="phase5-context"><p>此回答基于答题版本{{ workspace.current.lesson_context.learning_revision }}、自评版本{{ workspace.current.lesson_context.assessment_revision }}及课程发布版本{{ workspace.current.lesson_context.release_version }}。</p><p v-if="workspace.current.lesson_stale">学习状态或课程来源后来已变化，以上为当时讲解。</p></div><div class="wb-toolbar"><p>资料与学情共同支持学习。演示标识仅用于本机分组，不是真实身份认证。</p><button class="button secondary" :disabled="Boolean(workspace.busy)" @click="workspace.load()">刷新来源与历史</button></div>
    <div v-if="workspace.error" class="alert alert-error" role="alert">{{ workspace.error }}</div>
    <div v-if="workspace.notice" class="alert alert-info" role="status">{{ workspace.notice }}</div>
    <nav class="wb-mobile-tabs" aria-label="工作台分栏"><button v-for="item in [['sources','资料来源'],['chat','助教问答'],['studio','学习工作室']]" :key="item[0]" class="button secondary" :aria-pressed="workspace.panel === item[0]" @click="workspace.panel = item[0]">{{ item[1] }}</button></nav>
    <div class="wb-grid" :data-panel="workspace.panel">
      <aside class="panel wb-sources" aria-labelledby="wb-sources-title">
        <h2 id="wb-sources-title">资料来源</h2><p class="small muted">打开用于查看；勾选才会参与下一轮检索。个人笔记默认不选。</p>
        <p v-if="workspace.busy === 'load'" role="status">正在恢复资料与历史…</p>
        <ul class="wb-source-list"><li v-for="source in workspace.sources" :key="sourceKey(source)">
          <label class="wb-source-choice"><input type="checkbox" :checked="isSelected(source)" :disabled="!['ready','empty'].includes(source.index_status)" :aria-label="`选择来源：${source.title}`" @change="workspace.toggle(source, $event.target.checked)" /><span><strong>{{ source.title }}</strong><small>{{ source.source_type === 'personal_note' ? '个人笔记 · 未核验' : source.source_type==='teaching_material'?'教师课件 · 已确认片段':'课程资料' }} · {{ indexNames[source.index_status] }}</small><small class="wb-version" :title="source.source_version">版本 {{ source.source_revision ? `r${source.source_revision} · ` : '' }}当前来源</small></span></label>
          <button class="wb-text-button" :aria-label="`打开资料：${source.title}`" @click="workspace.open(source)">打开资料</button>
        </li></ul>
        <p v-if="!workspace.sources.length && !workspace.busy" class="small muted">当前没有可用资料。</p>
      </aside>

      <section class="panel wb-chat" aria-labelledby="wb-chat-title">
        <header class="wb-section-heading"><h2 id="wb-chat-title">AI 助教</h2><span class="badge">本地优先</span></header>
        <p class="small muted">下一轮已选 {{ workspace.chosen.length }} 项：</p><ul class="wb-chips" aria-label="下一轮所选资料"><li v-for="source in workspace.chosen" :key="sourceKey(source)">{{ source.title }}</li></ul>
        <form class="wb-question-form" @submit.prevent="workspace.ask()">
          <label for="wb-question">提出学习问题</label><textarea id="wb-question" v-model="workspace.query" rows="3" maxlength="1000" required placeholder="例如：梯度下降为什么沿负梯度方向更新？" />
          <label class="wb-mode" for="wb-mode">处理方式<select id="wb-mode" v-model="workspace.mode"><option value="local">仅本地检索 · 不发送模型</option><option value="model" :disabled="!workspace.capabilities?.model_enabled">{{ workspace.capabilities?.model_enabled ? `使用 ${workspace.capabilities.provider} / ${workspace.capabilities.model}` : '模型未启用' }}</option></select></label>
          <div v-if="workspace.mode === 'model' && workspace.personal.length" class="wb-consent">
            <strong>本轮个人笔记外发说明</strong><p>若同意，将把问题及下列选中笔记的相关检索片段发送至 {{ workspace.capabilities?.provider }}（{{ workspace.capabilities?.model }}），不会发送整本笔记库或聊天历史。</p>
            <ul><li v-for="source in workspace.personal" :key="source.source_id">{{ source.title }}</li></ul>
            <label><input v-model="workspace.consent" type="checkbox" />我同意仅本轮发送上述笔记的相关片段</label><p class="small">未同意时只做本地检索；下轮需要重新同意。课程资料和问题在使用模型时也将发送至该服务。</p>
          </div>
          <p v-else-if="workspace.mode === 'model'" class="small muted">本轮问题和选中课程资料的相关片段将发送至 {{ workspace.capabilities?.provider }} / {{ workspace.capabilities?.model }}。</p>
          <div v-if="workspace.mode==='model' && workspace.teachers?.length" class="wb-consent"><strong>本轮教师课件外发说明</strong><p>仅将问题及下列所选课件中实际检索到的已确认片段发送至 {{ workspace.capabilities?.provider }} / {{ workspace.capabilities?.model }}，不发送整份课件。此授权与页面识别、个人笔记及学习指南分开。</p><ul><li v-for="s in workspace.teachers" :key="s.source_id">{{ s.title }}</li></ul><label><input v-model="workspace.teacherConsent" type="checkbox" />我有权外发，并同意仅本轮发送上述课件的相关片段</label><p>未同意只做本地检索，下轮重新确认。</p></div>
          <p v-if="workspace.mode === 'model'" class="small muted">先检索所选资料，再由大模型结合资料和自身知识综合生成回答；未找到片段或资料只覆盖部分问题时，也可继续解释。资料引用与模型补充会明确区分。</p>
          <p v-if="workspace.mode === 'model' && workspace.capabilities?.max_output_tokens" class="small muted">每次模型输出上限 {{ workspace.capabilities.max_output_tokens }} token，本轮最多 {{ workspace.capabilities.max_model_calls }} 次模型调用；失败不会自动重发。</p>
          <button class="button primary" :disabled="Boolean(workspace.busy || workspace.pendingId || !workspace.chosen.length || !workspace.query.trim())">{{ workspace.busy === 'ask' ? '正在处理本轮请求…' : workspace.mode === 'local' || (workspace.personal.length && !workspace.consent) || (workspace.teachers?.length && !workspace.teacherConsent) ? '本地检索' : '发送本轮问题' }}</button>
        </form>
        <div v-if="workspace.pendingId" class="wb-pending" role="status"><p>原请求 {{ workspace.pendingId }} 仍需核对，刷新仅查询记录。</p><button class="button secondary" :disabled="Boolean(workspace.busy)" @click="workspace.load()">查询原请求状态</button><button class="wb-text-button" :disabled="Boolean(workspace.busy)" @click="workspace.releaseUncertain()">结束本轮等待（新请求可能另计费）</button></div>
        <article v-if="workspace.current" class="wb-answer" aria-label="已保存的本轮回答">
          <h3>{{ workspace.current.question }}</h3><p class="small muted">{{ date(workspace.current.created_at) }} · {{ workspace.current.status === 'complete' ? '模型回答' : workspace.current.status === 'stale' ? '来源或学情已变化' : workspace.current.status === 'uncertain' ? '执行待确认' : '本地资料反馈' }} · 模型调用 {{ workspace.current.model_calls }} 次</p>
          <p v-if="workspace.current.reason" class="wb-run-notice" role="status">{{ reasons[workspace.current.reason] || '模型服务异常，已保留本轮状态和可用的本地片段。' }}</p>
          <p v-if="workspace.current.reason === 'model_output_truncated' && workspace.current.max_output_tokens" class="small muted">本轮每次输出上限：{{ workspace.current.max_output_tokens }} token。截断内容未作为完整回答展示，新的请求可能另计费。</p>
          <p v-if="workspace.current.validation_error" class="wb-run-notice" role="status">具体原因：{{ validationErrors[workspace.current.validation_error] || '返回格式不符合约定。' }}</p>
          <p v-if="workspace.current.answer_basis === 'model_knowledge'" class="wb-run-notice" role="status">以下回答来自模型自身知识，可能有误，没有本地资料引用。</p>
          <p v-if="workspace.current.answer_basis === 'mixed'" class="wb-run-notice" role="status">本轮结合了所选资料与模型知识；带引用内容可回溯原文，“模型知识补充”不代表资料原文。</p>
          <details><summary>本轮实际选中来源及版本</summary><ul><li v-for="source in workspace.current.selected_sources" :key="sourceKey(source)" class="wb-version">{{ source.title }} · {{ source.source_type === 'personal_note' ? '个人笔记' : '课程资料' }} · {{ source.source_version }}</li></ul></details>
          <p v-if="workspace.current.source_statuses.some(s => s.current_status !== 'current')" class="wb-run-notice">部分来源后来已修改、软删除或不可用；以下引用保留当时快照，不代表当前版本。</p>
          <MarkdownRenderer :source="workspace.current.answer" :citation-ids="workspace.current.citations.map(c => c.citation_id)" @citation="openInline" />
          <div class="wb-citations" aria-label="本轮实际引用"><button v-for="item in workspace.current.citations" :key="item.citation_id" class="wb-citation" @click="workspace.citation(item)"><strong>[{{ item.citation_id }}] {{ item.title }}</strong><span>{{ item.source_type === 'personal_note' ? '个人笔记 · 未核验' : item.source_type==='teaching_material'?'教师课件':'课程资料' }} · {{ item.page_number ? `原PDF第${item.page_number}页` : `行${item.start_line}–${item.end_line}` }}</span></button></div>
          <button v-if="workspace.current.answer && ['complete','local','stale'].includes(workspace.current.status)" class="button secondary" :disabled="Boolean(workspace.busy)" @click="saveAndEdit">{{ workspace.busy === 'save' ? '正在保存…' : workspace.current.saved_note_id ? '打开另存笔记' : '另存为可编辑笔记' }}</button>
        </article>
        <section class="wb-history" aria-labelledby="wb-history-title"><h3 id="wb-history-title">问答历史</h3><p class="small muted">查看已保存记录，不重新调用模型。最近20轮；完整记录保存在本机。</p><button v-for="run in workspace.runs" :key="run.request_id" class="wb-history-item" :aria-pressed="workspace.current?.request_id === run.request_id" @click="workspace.view(run)">{{ run.question }}<small>{{ date(run.created_at) }} · {{ run.status }}</small></button></section>
      </section>

      <aside class="wb-studio" aria-labelledby="wb-studio-title"><section class="panel"><h2 id="wb-studio-title">学习工作室</h2><h3>当前学习目标</h3><p>{{ goalNames }}</p><p class="small muted">学情版本 {{ selfWorkspace?.overview?.learning_revision ?? snapshot?.revision }} · 根据正式作答更新</p><div class="wb-studio-actions"><button class="button primary" @click="emit('navigate', 'learn')">进入正式练习</button><button class="button secondary" @click="emit('navigate', 'history')">查看学习历史</button><button v-if="selfWorkspace" class="button secondary" :disabled="Boolean(selfWorkspace.busy)" @click="selfWorkspace.load()">只读刷新学情与自评</button></div></section><SelfAssessmentPanel v-if="selfWorkspace" :workspace="selfWorkspace" /><LearningGuidancePanel v-if="selfWorkspace" :overview="selfWorkspace.overview" @navigate="emit('navigate', $event)" /><StudyGuidePanel v-if="selfWorkspace && guideWorkspace" :workspace="guideWorkspace" :self-workspace="selfWorkspace" :capabilities="workspace.capabilities" /><MasteryPanel :snapshot="selfWorkspace?.masterySnapshot || snapshot" :current="currentTopic" /></aside>
    </div>
    <SourceDrawer :source="workspace.drawer" @close="workspace.drawer = null" />
  </section>
</template>
