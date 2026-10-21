<script setup>
const props = defineProps({ workspace: Object })
const levels = ['不了解', '理解概念', '能够完成基础习题', '能够独立应用']
const date = value => new Date(value).toLocaleString('zh-CN')
</script>
<template>
  <section class="panel self-panel" aria-labelledby="self-title">
    <h2 id="self-title">我的自评</h2><p class="small muted">主观报告与答题模型分开保存。信心可不填，不换算为掌握概率。</p>
    <p v-if="workspace.busy === 'load'" role="status">正在读取已保存学情…</p>
    <div v-if="workspace.error" class="alert alert-error" role="alert">{{ workspace.error }}</div><p v-if="workspace.notice" class="small" role="status">{{ workspace.notice }}</p>
    <form v-if="workspace.overview && workspace.overview.items.every(point => workspace.draft[point.knowledge_id])" @submit.prevent="workspace.save()">
      <fieldset :disabled="Boolean(workspace.busy === 'save' || workspace.pending)" class="self-fields"><legend class="sr-only">五知识点自评等级和学习信心</legend>
        <div v-for="point in workspace.overview.items" :key="point.knowledge_id" class="self-row">
          <strong>{{ point.name }}</strong>
          <label :for="`self-level-${point.knowledge_id}`">自评等级</label><select :id="`self-level-${point.knowledge_id}`" v-model="workspace.draft[point.knowledge_id].level"><option :value="null">未填写</option><option v-for="(label, index) in levels" :key="index" :value="index + 1">{{ index + 1 }} · {{ label }}</option></select>
          <label :for="`self-confidence-${point.knowledge_id}`">完成相关学习任务的信心</label><select :id="`self-confidence-${point.knowledge_id}`" v-model="workspace.draft[point.knowledge_id].confidence"><option :value="null">未填写信心</option><option v-for="n in 5" :key="n" :value="n">{{ n }} / 5{{ n === 1 ? ' · 很低' : n === 5 ? ' · 很高' : '' }}</option></select>
          <small class="muted">{{ point.self_report ? `上次报告：${date(point.self_report.created_at)} · 自评版本 ${point.self_report.assessment_revision}` : '尚无已保存自评' }}</small>
        </div>
      </fieldset>
      <p class="small" role="status">{{ workspace.status }} · 本机编辑基于自评版本 {{ workspace.revision }}</p>
      <button class="button primary" :disabled="Boolean(workspace.busy || (!workspace.dirty && !workspace.pending) || (workspace.conflict && !workspace.pending))">{{ workspace.pending ? workspace.pending.retryReady ? '重试原自评提交' : '查询原自评回执' : '保存自评' }}</button>
      <button v-if="workspace.conflict" type="button" class="button secondary" :disabled="Boolean(workspace.busy || workspace.pending)" @click="workspace.readLatest()">读取新版本并保留本机修改</button>
    </form>
    <details><summary>自评历史（最近50项）</summary><p v-if="!workspace.history.length" class="small muted">尚无自评记录。</p><ol class="self-history"><li v-for="entry in workspace.history" :key="entry.id">{{ workspace.overview?.items.find(p => p.knowledge_id === entry.knowledge_id)?.name || entry.knowledge_id }}：{{ levels[entry.level - 1] }}，信心 {{ entry.confidence ?? '未填写' }}<small>{{ date(entry.created_at) }} · 自评版本 {{ entry.assessment_revision }} · 答题版本 {{ entry.learning_revision_at_save }}</small></li></ol></details>
  </section>
</template>
