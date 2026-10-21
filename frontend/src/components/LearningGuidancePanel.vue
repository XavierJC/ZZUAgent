<script setup>
defineProps({ overview: Object })
const emit = defineEmits(['navigate'])
const date = value => new Date(value).toLocaleString('zh-CN')
</script>
<template>
  <section v-if="overview" class="panel guidance-panel" aria-labelledby="guidance-title">
    <h2 id="guidance-title">学情对照与学习重点</h2><p class="small muted">答题版本 {{ overview.learning_revision }} · 自评版本 {{ overview.assessment_revision }}<br />{{ overview.rule_version }} · {{ overview.versions.bkt }} · {{ overview.versions.knowledge }}</p>
    <details><summary>五知识点主客观对照</summary><div v-for="point in overview.items" :key="point.knowledge_id" class="guidance-comparison"><strong>{{ point.name }}</strong><p>我的自评：{{ point.self_report ? `${point.self_report.level}级，信心 ${point.self_report.confidence ?? '未填写'}` : '未填写' }}</p><p>答题证据：{{ point.objective.attempts }}次 · {{ point.objective.has_evidence ? `BKT模型估计 ${(point.objective.probability * 100).toFixed(1)}%，最近${point.objective.last_correct ? '答对' : '答错'}` : '待诊断（先验不是诊断）' }}</p><small v-if="point.recent_attempts.length">最近作答：{{ date(point.recent_attempts[0].created_at) }}</small><small v-if="point.self_report">自评时间：{{ date(point.self_report.created_at) }} · 自评来源 {{ point.self_report.id }}</small><p v-if="point.blocked_by.length" class="small">先修待核验：{{ point.blocked_by.map(id => overview.items.find(p => p.knowledge_id === id)?.name || id).join('、') }}</p></div></details>
    <article v-for="point in overview.recommendations" :key="point.knowledge_id" class="guidance-focus"><h3>{{ point.priority }}. {{ point.name }}</h3><ul><li v-for="reason in point.reasons" :key="reason">{{ reason }}</li></ul><small class="muted">正式答题 {{ point.objective.attempts }}次 · 可用新题 {{ point.available_questions }}道</small><div class="guide-actions"><button v-for="action in point.actions" :key="action.kind" class="button secondary" @click="emit('navigate', action.kind === 'open_formal_practice' ? 'learn' : 'history')">{{ action.kind === 'open_formal_practice' ? '进入原正式练习' : '查看已有学习历史' }}</button></div></article>
    <p class="small muted">重点与原因由程序确定；正式练习仍按原规则分配，不承诺直接跳到推荐知识点。少量答题和自评不能证明真实能力。</p>
  </section>
</template>
