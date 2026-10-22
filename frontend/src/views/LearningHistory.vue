<script setup>
import { computed } from 'vue'
import Icon from '../components/Icon.vue'
import MarkdownRenderer from '../components/MarkdownRenderer.vue'
import { percent } from '../useWorkspace.js'
const props=defineProps({ w: Object })
defineEmits(['navigate'])
const recentAccuracy=computed(()=>props.w.history.length ? `${Math.round(props.w.history.filter(i=>i.correct).length/props.w.history.length*100)}%` : '—')
function formatDate(value) { return new Intl.DateTimeFormat('zh-CN',{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'}).format(new Date(value)) }
</script>
<template>
          <section class="panel history-panel"><div class="panel-heading"><div><p class="eyebrow">LEARNING JOURNAL</p><h2>答题与反馈</h2></div><span class="badge">最近 {{ w.history.length }} 条</span></div><div v-if="w.history.length" class="history-summary"><span>已记录作答 <strong>{{ w.snapshot.revision }}</strong></span><span>最近 {{ w.history.length }} 题正确率 <strong>{{ recentAccuracy }}</strong></span></div><div v-if="w.history.length" class="history-list"><details v-for="item in w.history" :key="item.event_id" class="history-item"><summary><span class="result-mark" :class="item.correct ? 'right' : 'wrong'">{{ item.correct ? '✓' : '×' }}</span><span class="history-topic"><strong>{{ w.topicName(item.knowledge_id) }}</strong><small>{{ formatDate(item.created_at) }} · {{ item.question_id }}</small></span><span class="history-answer">{{ item.selected_answer }} <small>{{ item.correct ? '答对' : '答错' }}</small></span><span class="history-probability">{{ percent(item.next_mastery) }}<small>掌握度估计</small></span><Icon name="chevron" :size="16" /></summary><div class="history-detail"><p>正确答案 {{ item.correct_answer }}。</p><MarkdownRenderer :source="item.explanation" /><span>答题前 {{ percent(item.prior) }} → 后验 {{ percent(item.posterior) }} → 转移后 {{ percent(item.next_mastery) }}</span></div></details></div><div v-else class="empty-state"><Icon name="history" :size="36" /><h3>第一条记录，从下一次作答开始。</h3><p>完成练习后，可以在这里回看解析与掌握度变化。</p><button class="button primary" @click="$emit('navigate','learn')">开始练习<Icon name="arrow" :size="17" /></button></div></section>

</template>