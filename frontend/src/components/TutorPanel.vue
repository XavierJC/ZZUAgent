<script setup>
import { ref } from 'vue'
import { toolLabels } from '../useWorkspace.js'
import Icon from './Icon.vue'
import MarkdownRenderer from './MarkdownRenderer.vue'
const props = defineProps({ reply: Object, runs: Array, busy: String, enabled: Boolean, pending: Object, topic: String })
defineEmits(['ask', 'view'])
const question = ref('')
const fallbackLabels = { authentication_failed: '模型服务暂不可用', insufficient_balance: '模型服务暂不可用', model_timeout: '模型响应超时', model_call_limit: '本次生成达到调用上限', unverified_model_answer: '生成内容的来源未通过检查', learning_state_changed: '生成期间学情已更新' }
function fill() { question.value = `请结合我的学情，检索课程资料讲解${props.topic}，并给出下一步学习建议。` }
</script>

<template>
  <section class="panel tutor-panel" aria-labelledby="tutor-title">
    <div class="panel-heading"><div class="heading-with-icon"><span class="tutor-icon"><Icon name="spark" :size="22" /></span><div><p class="eyebrow">LEARN WITH A LITTLE HELP</p><h2 id="tutor-title">让助教帮你理清思路</h2></div></div><span class="badge" :class="enabled ? 'badge-green' : ''">{{ enabled ? '助教已就绪' : '助教暂不可用' }}</span></div>
    <form class="tutor-form" @submit.prevent="$emit('ask', question)">
      <label for="tutor-question" class="sr-only">向学习助教提问</label>
      <textarea id="tutor-question" v-model="question" rows="3" maxlength="2000" placeholder="哪一步还没理解？把问题写在这里，助教会结合你的学情与课程资料回答。" :disabled="Boolean(busy || !enabled || pending)" />
      <div class="tutor-form-footer"><button type="button" class="text-button" :disabled="Boolean(busy || !enabled || pending)" @click="fill">讲解当前知识点</button><button type="submit" class="button primary" :disabled="Boolean(busy || !enabled || pending || !question.trim())">{{ busy === 'tutor' ? '正在整理讲解…' : '发送给助教' }}<Icon name="send" :size="17" /></button></div>
    </form>
    <p class="small muted tutor-cost">发送可能调用模型；资料不足时提供本地反馈，刷新只读取已保存讲解。</p>
    <div v-if="reply" class="tutor-reply" aria-live="polite">
      <div class="reply-heading"><strong>{{ reply.mode === 'deepseek' ? '助教讲解' : '本地学习反馈' }}</strong><span class="badge" :class="reply.mode === 'deepseek' ? 'badge-blue' : 'badge-amber'">{{ reply.fallback_reason === 'insufficient_evidence' ? '课程依据不足' : reply.mode === 'deepseek' ? '基于学情与资料' : '已降级为离线反馈' }}</span></div>
      <p v-if="reply.fallback_reason === 'insufficient_evidence'" class="fallback-note">没有找到足够相关的课程依据，本次未调用模型。可参考已有学习安排，或把问题具体到课程知识点。</p>
      <p v-else-if="reply.mode !== 'deepseek'" class="fallback-note">{{ fallbackLabels[reply.fallback_reason] || '模型未能完成有效回答' }}。以下为课程资料反馈与当前学习安排。</p>
      <MarkdownRenderer class="answer-text" :source="reply.answer" />
      <div v-if="reply.citations.length" class="citations"><p class="small muted">查阅原文，核对依据</p>
        <details v-for="citation in reply.citations" :key="citation.citation_id" class="citation"><summary><Icon name="book" :size="16" /><span>{{ citation.title }} · {{ citation.section }}</span><span class="citation-id">[{{ citation.citation_id }}]</span></summary><MarkdownRenderer :source="citation.content" /><small class="muted">{{ citation.source }} · {{ citation.review_status === 'pending' ? '资料待审阅' : '已审阅' }}</small></details>
      </div>
      <div class="tool-evidence"><span v-for="tool in reply.tools_used.filter(item => item.status === 'ok')" :key="tool.name"><Icon name="check" :size="13" />{{ toolLabels[tool.name] || '完成工具调用' }}</span></div>
    </div>
    <div v-else-if="busy !== 'tutor'" class="tutor-placeholder"><Icon name="book" :size="20" /><p>好的问题，让理解再向前一步。<br /><span class="muted small">讲解会附课程资料出处，便于回看与核对。</span></p></div>
    <details v-if="runs?.length > 1" class="previous-runs"><summary>回看最近 {{ runs.length }} 次讲解</summary><button v-for="(run, index) in runs" :key="run.run_id" class="text-button" @click="$emit('view', run)">讲解 {{ runs.length - index }} · 作答记录版本 {{ run.state_revision }} · {{ run.mode === 'deepseek' ? '模型讲解' : '离线反馈' }}</button></details>
  </section>
</template>
