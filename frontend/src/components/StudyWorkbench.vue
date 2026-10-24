<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import QuickDocumentUpload from './QuickDocumentUpload.vue'
import DocumentPageRecognition from './DocumentPageRecognition.vue'
import { sourceKey } from '../useStudyWorkbench.js'
import MarkdownRenderer from './MarkdownRenderer.vue'
import MasteryPanel from './MasteryPanel.vue'
import SourceDrawer from './SourceDrawer.vue'
import LearningNextStep from './LearningNextStep.vue'
import { topicQuestion, sourcePosition } from '../features/learning/journey.js'
import '../workbench.css'
import '../study-guidance.css'
const props = defineProps({ workspace: { type: Object, required: true }, snapshot: Object, goalNames: String, currentTopic: String, selfWorkspace: Object, guideWorkspace: Object, documentWorkspace: Object, architectureWorkspace: Object, bankWorkspace: Object })
const emit = defineEmits(['navigate', 'edit-note'])
const sourceQuery=ref('')
const recognizing=ref(null)
const inspectorOpen=ref(false), questionInput=ref(null), returnPanel=ref('chat')
const partialSources=computed(()=>props.workspace.chosen.filter(s=>s.readable_units != null && s.readable_units < s.total_units))
const hasPrivateSources=computed(()=>props.workspace.personal.length || props.workspace.teachers?.length)
const localOnly=computed(()=>props.workspace.mode==='local' || (props.workspace.personal.length && !props.workspace.consent) || (props.workspace.teachers?.length && !props.workspace.teacherConsent))
const filteredSources=computed(()=>props.workspace.sources.filter(s=>s.title.toLocaleLowerCase().includes(sourceQuery.value.toLocaleLowerCase())))
const externalConsent=computed({get:()=> (!props.workspace.personal.length || props.workspace.consent) && (!props.workspace.teachers?.length || props.workspace.teacherConsent),set:value=>{props.workspace.consent=value;props.workspace.teacherConsent=value}})
const focus=computed(()=>props.selfWorkspace?.overview?.recommendations?.[0])
const label=s=>s.source_type==='personal_note'?'个人笔记 · 未核验':s.source_type==='uploaded_document'?'上传资料 · 未核验':s.source_type==='teaching_material'?'教师课件 · 已确认片段':'课程资料'
async function uploaded(id){await props.workspace.load();const item=props.workspace.sources.find(s=>s.source_type==='uploaded_document' && s.source_id===id);if(item?.index_status==='ready')props.workspace.toggle(item,true)}
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
async function prepare(question) { props.workspace.prepare(question); await nextTick(); questionInput.value?.focus() }
function closeSource() { props.workspace.closePreview(); props.workspace.panel=returnPanel.value; inspectorOpen.value=false }
function toggleInspector() { inspectorOpen.value=!inspectorOpen.value; if(inspectorOpen.value)props.workspace.panel='studio'; else props.workspace.panel='chat' }
watch(()=>props.workspace.drawer,(value,previous)=>{if(value){if(!previous)returnPanel.value=props.workspace.panel;inspectorOpen.value=true;props.workspace.panel='studio'}})
watch(()=>props.workspace.initialized,()=>{if(!props.workspace.initialized){inspectorOpen.value=false;recognizing.value=null}})
onMounted(() => props.workspace.load())
onMounted(() => props.selfWorkspace?.load())
</script>

<template>
  <section class="study-workbench" aria-label="资料学习工作台">
    <div class="wb-toolbar">
      <p>机器学习 · 资料、问答与练习</p>
      <div class="journey-actions"><button class="wb-text-button" :disabled="Boolean(workspace.busy)" @click="workspace.load()">刷新资料</button><button class="button secondary wb-inspector-toggle" :aria-expanded="inspectorOpen" aria-controls="wb-inspector" @click="toggleInspector">{{ inspectorOpen ? '收起学习面板' : '学习面板' }}</button></div>
    </div>
    <div v-if="workspace.error" class="alert alert-error" role="alert">{{ workspace.error }}</div>
    <div v-if="workspace.notice" class="alert alert-info" role="status">{{ workspace.notice }}</div>
    <nav class="wb-mobile-tabs" aria-label="工作台分栏"><button v-for="item in [['sources','资料来源'],['chat','助教问答'],['studio','学习工作室']]" :key="item[0]" class="button secondary" :aria-pressed="workspace.panel === item[0]" @click="workspace.panel = item[0]">{{ item[1] }}</button></nav>
    <div class="wb-grid" :data-panel="workspace.panel" :data-inspector="inspectorOpen ? 'open' : 'closed'">
      <aside class="panel wb-sources" aria-labelledby="wb-sources-title">
        <header class="wb-section-heading"><h2 id="wb-sources-title">我的资料</h2><span class="badge">{{workspace.sources.length}}</span></header>
        <QuickDocumentUpload v-if="documentWorkspace?.supported" :workspace="documentWorkspace" @ready="uploaded" />
        <label class="sr-only" for="wb-source-search">搜索资料</label><input id="wb-source-search" v-model="sourceQuery" placeholder="搜索资料" />
        <p class="small muted">勾选参与提问，打开查看原文。</p>
        <p v-if="workspace.busy === 'load'" role="status">正在恢复资料与历史…</p>
        <ul class="wb-source-list"><li v-for="source in filteredSources" :key="sourceKey(source)" :class="{'wb-source-selected':isSelected(source)}">
          <label class="wb-source-choice"><input type="checkbox" :checked="isSelected(source)" :disabled="source.source_type==='uploaded_document' ? source.index_status!=='ready' : !['ready','empty'].includes(source.index_status)" :aria-label="`选择来源：${source.title}`" @change="workspace.toggle(source, $event.target.checked)" /><span><strong>{{ source.title }}</strong><small>{{ label(source) }} · {{ indexNames[source.index_status] }}</small><small v-if="source.readable_units != null">可问 {{source.readable_units}} / {{source.total_units}} 个页面或文本单位</small></span></label>
          <div class="wb-source-actions"><button class="wb-text-button" :aria-label="`打开资料：${source.title}`" @click="workspace.open(source)">打开资料</button><button v-if="documentWorkspace?.supported && source.source_type==='uploaded_document' && source.file_format==='pdf' && source.readable_units < source.total_units" class="wb-text-button" :disabled="Boolean(documentWorkspace.busy)" @click="recognizing=source">识别缺失页面</button><button v-if="['uploaded_document','teaching_material'].includes(source.source_type)" class="wb-text-button" @click="emit('navigate','practice',{document:source.document_id || source.source_id})">相关练习</button></div>
        </li></ul>
        <DocumentPageRecognition v-if="recognizing" :key="recognizing.source_id" :workspace="documentWorkspace" :source="recognizing" @close="recognizing=null" @ready="uploaded" />
        <p v-if="!workspace.sources.length && !workspace.busy" class="small muted">添加一份课件或笔记，开始学习。</p>
        <p v-else-if="!filteredSources.length" role="status">没有匹配的资料，请换个名称。</p>
        <button class="wb-text-button" @click="emit('navigate','notes')">打开我的笔记</button>
      </aside>

      <section class="panel wb-chat" aria-labelledby="wb-chat-title">
        <header class="wb-section-heading"><div><p class="eyebrow">围绕资料学习</p><h2 id="wb-chat-title">AI 助教</h2></div><span class="badge">{{localOnly?'本地检索':'AI讲解'}}</span></header>
        <details v-if="workspace.runs.length" class="wb-history"><summary id="wb-history-title">问答历史 · {{workspace.runs.length}} 条</summary><p class="small muted">打开已保存回答，不会重新调用模型。</p><button v-for="run in workspace.runs" :key="run.request_id" class="wb-history-item" :aria-pressed="workspace.current?.request_id === run.request_id" @click="workspace.view(run)">{{run.question}}<small>{{date(run.created_at)}} · {{run.status==='complete'?'已回答':run.status==='uncertain'?'待确认':'已保存'}}</small></button></details>
        <div v-if="!workspace.current && !workspace.busy" class="wb-welcome">
          <h3>今天想弄懂什么？</h3><p>选择左侧资料，再提出一个具体问题。回答中的编号可以直接查看出处。</p>
          <div class="wb-starters"><button class="button secondary" @click="prepare(focus ? topicQuestion(focus.name) : '请解释所选资料中的核心概念，并举一个例子。')">理解核心概念</button><button class="button secondary" @click="prepare('请结合所选资料，解释一个容易混淆的概念，并给出对比例子。')">弄清容易混淆的地方</button></div>
        </div>
        <article v-if="workspace.current" class="wb-answer" aria-label="已保存的本轮回答">
          <h3>{{ workspace.current.question }}</h3><p class="small muted">{{ date(workspace.current.created_at) }} · {{ workspace.current.status === 'complete' ? '模型回答' : workspace.current.status === 'stale' ? '来源或学情已变化' : workspace.current.status === 'uncertain' ? '执行待确认' : '本地资料反馈' }}</p>
          <p v-if="workspace.current.reason" class="wb-run-notice" role="status">{{ reasons[workspace.current.reason] || '模型服务异常，已保留本轮状态和可用的本地片段。' }}</p>
          <p v-if="workspace.current.validation_error" class="wb-run-notice" role="status">具体原因：{{ validationErrors[workspace.current.validation_error] || '返回格式不符合约定。' }}</p>
          <p v-if="workspace.current.answer_basis === 'model_knowledge'" class="wb-run-notice" role="status">以下回答来自模型自身知识，可能有误，没有本地资料引用。</p>
          <p v-if="workspace.current.answer_basis === 'mixed'" class="small muted">本轮结合了所选资料与模型知识；引用可回溯，模型补充单独标注。</p>
          <p v-if="workspace.current.source_statuses.some(s => s.current_status !== 'current')" class="wb-run-notice">部分来源后来已修改或软删除；引用保留回答时的快照。</p>
          <MarkdownRenderer number-citations :source="workspace.current.answer" :citation-ids="workspace.current.citations.map(c => c.citation_id)" @citation="openInline" />
          <div class="wb-citations" aria-label="本轮实际引用"><button v-for="(item,index) in workspace.current.citations" :key="item.citation_id" class="wb-citation" @click="workspace.citation(item)"><strong>[{{ index+1 }}] {{ item.title }}</strong><span>{{label(item)}} · {{sourcePosition(item)}}</span></button></div>
          <button v-if="workspace.current.answer && ['complete','local','stale'].includes(workspace.current.status)" class="button secondary" :disabled="Boolean(workspace.busy)" @click="saveAndEdit">{{ workspace.busy === 'save' ? '正在保存…' : workspace.current.saved_note_id ? '打开另存笔记' : '另存为可编辑笔记' }}</button>
          <details><summary>本轮实际选中来源及版本</summary><p class="small muted">模型调用 {{workspace.current.model_calls}} 次</p><p v-if="workspace.current.max_output_tokens" class="small muted">本轮每次输出上限：{{workspace.current.max_output_tokens}} token</p><ul><li v-for="source in workspace.current.selected_sources" :key="sourceKey(source)" class="wb-version">{{source.title}} · {{label(source)}} · {{source.source_version}}</li></ul><p v-if="workspace.current.lesson_context">答题版本{{workspace.current.lesson_context.learning_revision}} · 自评版本{{workspace.current.lesson_context.assessment_revision}} · 发布版本{{workspace.current.lesson_context.release_version}}<template v-if="workspace.current.lesson_stale"> · 学情或课程后来已变化</template></p></details>
        </article>

        <form class="wb-question-form" @submit.prevent="workspace.ask()">
          <div class="wb-composer-scope"><strong>本轮已选 {{workspace.chosen.length}} 项资料</strong><button type="button" class="wb-text-button" @click="workspace.panel='sources'">选择资料</button></div>
          <ul class="wb-chips" aria-label="下一轮所选资料"><li v-for="source in workspace.chosen.slice(0,3)" :key="sourceKey(source)">{{source.title}}</li><li v-if="workspace.chosen.length>3">另 {{workspace.chosen.length-3}} 项</li></ul>
          <p v-if="partialSources.length" class="wb-coverage" role="status">部分资料仅有可读页面参与检索，尚未识别的公式或图片不在检索范围内。可在资料旁选择“识别缺失页面”。</p>
          <div v-if="workspace.suggestion" class="wb-pending"><p>已准备学习问题：{{workspace.suggestion}}</p><p class="small">你原来的问题草稿已保留。</p><button type="button" class="wb-text-button" @click="prepare(workspace.suggestion);workspace.query=workspace.suggestion;workspace.suggestion=''">使用此问题（替换当前草稿）</button><button type="button" class="wb-text-button" @click="workspace.suggestion=''">保留原草稿</button></div>
          <label for="wb-question">提出学习问题</label><textarea id="wb-question" ref="questionInput" v-model="workspace.query" rows="3" maxlength="1000" required placeholder="例如：梯度下降为什么沿负梯度方向更新？" @keydown.ctrl.enter.prevent="workspace.ask()" @keydown.meta.enter.prevent="workspace.ask()" />
          <div v-if="workspace.mode==='model' && hasPrivateSources" class="wb-consent"><strong>本轮资料外发授权</strong><p>将本轮问题和以下资料的相关片段发送至 {{workspace.capabilities?.provider}}（{{workspace.capabilities?.model}}），按量计费；不发送整个资料库或聊天历史。</p><ul><li v-for="s in [...workspace.personal,...(workspace.teachers || [])]" :key="sourceKey(s)">{{s.title}}</li></ul><label><input v-model="externalConsent" type="checkbox" />我有权外发，并同意仅本轮发送上述相关片段</label><p class="small">未同意时仅本地检索；下一轮重新确认，和页面识别/学习指南授权分开。</p></div>
          <p v-else-if="workspace.mode==='model'" class="small muted">本轮问题和所选课程资料片段将发送至 {{workspace.capabilities?.provider}}，按量计费。</p>
          <div class="wb-composer-actions"><details class="answer-settings"><summary>回答设置 · {{workspace.mode==='local'?'本地检索':'AI讲解'}}</summary><label class="wb-mode" for="wb-mode">处理方式<select id="wb-mode" v-model="workspace.mode"><option value="local">仅本地检索 · 不发送模型</option><option value="model" :disabled="!workspace.capabilities?.model_enabled">{{workspace.capabilities?.model_enabled ? `AI讲解 · ${workspace.capabilities.provider}` : '模型未启用'}}</option></select></label><p class="small muted">先检索再结合模型解释；模型补充会与资料依据区分。每次输出最多{{workspace.capabilities?.max_output_tokens || 1500}} token，每轮最多{{workspace.capabilities?.max_model_calls || 3}}次，执行不明不自动重发。</p></details><button class="button primary" :disabled="Boolean(workspace.busy || workspace.pendingId || !workspace.chosen.length || !workspace.query.trim())">{{workspace.busy==='ask'?'正在处理…':localOnly?'本地检索':'提问'}}</button></div>
          <p class="small muted">{{workspace.chosen.length?'Ctrl / ⌘ + Enter 发送；查看历史不会重新生成回答。':'请先选择至少一项资料。空选择不会检索整个资料库。'}}</p>
        </form>
        <div v-if="workspace.pendingId" class="wb-pending" role="status"><p>正在核对原请求，刷新仅查询记录，不会自动重发。</p><details><summary>请求编号</summary>{{workspace.pendingId}}</details><button class="button secondary" :disabled="Boolean(workspace.busy)" @click="workspace.load()">查询原请求状态</button><button class="wb-text-button" :disabled="Boolean(workspace.busy)" @click="workspace.releaseUncertain()">结束本轮等待（新请求可能另计费）</button></div>
      </section>

      <aside id="wb-inspector" class="wb-studio" aria-label="原文与学习面板">
        <SourceDrawer v-if="workspace.drawer" embedded :loading="workspace.opening" :source="workspace.drawer" @page="workspace.open(workspace.drawer,$event)" @close="closeSource" />
        <template v-else><section class="panel"><LearningNextStep :overview="selfWorkspace?.overview" :goals="goalNames" @navigate="(...args)=>emit('navigate',...args)" /><div class="wb-studio-actions"><button class="wb-text-button" @click="emit('navigate','insights')">查看学习进度与自评</button><button class="wb-text-button" @click="emit('navigate','notes')">我的笔记</button></div></section><details class="panel"><summary>知识掌握概况</summary><MasteryPanel :snapshot="selfWorkspace?.masterySnapshot || snapshot" :current="currentTopic" /></details></template>
      </aside>
    </div>
  </section>
</template>
