<script setup>
import { percent } from '../useWorkspace.js'
import Icon from './Icon.vue'
defineProps({ snapshot: Object, current: String })
</script>

<template>
  <section class="panel mastery-panel" aria-labelledby="mastery-title">
    <div class="panel-heading"><div><p class="eyebrow">YOUR LEARNING MAP</p><h2 id="mastery-title">知识掌握概览</h2></div><Icon name="activity" /></div>
    <p class="muted small">每次作答，为下一步提供一点依据。</p>
    <ul class="mastery-list">
      <li v-for="item in snapshot?.mastery || []" :key="item.knowledge_id" :class="{ current: current === item.knowledge_id }">
        <div class="mastery-label"><span>{{ item.name }}</span><strong>{{ item.has_evidence ? percent(item.probability) : '待诊断' }}</strong></div>
        <div class="meter" role="progressbar" :aria-label="item.name" :aria-valuemin="0" :aria-valuemax="100"
             :aria-valuenow="item.has_evidence ? Math.round(item.probability * 100) : undefined"
             :aria-valuetext="item.has_evidence ? percent(item.probability) : '尚无答题证据'">
          <span :style="{ width: item.has_evidence ? percent(item.probability) : '0%' }" :class="{ mastered: item.has_evidence && item.probability >= snapshot.threshold }" />
        </div>
        <div class="mastery-meta"><span>{{ item.attempts ? `已完成 ${item.attempts} 道题` : '尚无答题证据' }}</span><span v-if="current === item.knowledge_id" class="blue-text">当前学习</span></div>
      </li>
    </ul>
    <div class="mastery-note"><span class="tiny-dot" />达到 {{ percent(snapshot?.threshold || 0.8) }} 为当前演示推进条件，数值为模型估计。</div>
  </section>
</template>
