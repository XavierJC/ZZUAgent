<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
const props = defineProps({ workspace: Object })
const error = ref('')
let timer
async function refresh() { try { await props.workspace.loadTasks() } catch(e) { error.value = e.message } }
onMounted(() => { refresh(); timer = setInterval(() => { if (props.workspace.tasks.some(t => t.status === 'running')) refresh() }, 2000) })
onUnmounted(() => clearInterval(timer))
const statuses = { running: '正在提取', complete: '待审核草稿已保存', uncertain: '执行待确认，不自动重发', stale: '来源或原题已变化，未发布', failed: '提取失败，原文保留' }
const errors = { model_timeout:'模型等待超时，执行情况待确认',network_error:'模型网络中断，执行情况待确认',source_changed:'选中资料已有新版本或已删除',revision_conflict:'原题已被编辑，请重新对照',model_output_truncated:'输出被截断，请减少选页或题目数量',invalid_question_payload:'题目结构不完整，需缩小范围并核对',quote_not_in_selected_original:'引用片段与本轮原文不匹配',stem_not_in_original:'题干无法与原文匹配',option_not_in_original:'选项无法与原文匹配',answer_not_in_original:'答案文字缺少原文依据',answer_key_not_in_original:'答案键缺少本题原文依据',execution_unconfirmed:'服务曾中断，执行情况待确认',authentication_failed:'模型服务认证失败',insufficient_balance:'模型服务余额不足' }
</script>
<template>
  <section class="panel"><h3>原题提取任务</h3><p class="small muted">刷新只读取已保存任务，不重新调用模型。局部重识别只产生修正草稿，不覆盖原题。</p><p v-if="error" role="alert">{{ error }}</p><button class="button secondary" @click="refresh">刷新提取记录</button>
    <article v-for="t in workspace.tasks" :key="t.request_id" class="source-card"><strong>{{ t.source.title }}</strong><p>{{ statuses[t.status] }} · {{ t.model_calls }}次模型调用</p><p v-if="t.result.message">{{ t.result.message }}</p><p v-if="t.result.error_code" role="status">{{ errors[t.result.error_code] || '输出未通过结构校验，请对照原页后明确重试' }}</p><button v-for="(id,index) in t.result.question_ids || []" :key="id" class="button secondary" @click="workspace.section = 'bank'; workspace.open(id)">校对第{{ index+1 }}题</button><details><summary>技术详情</summary><p>请求 {{ t.request_id }} · 来源版本 {{ t.source.source_version }} · {{ t.source_status }} · {{ t.result.error_code }}</p></details></article>
  </section>
</template>
