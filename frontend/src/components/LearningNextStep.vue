<script setup>
import { computed } from 'vue'
import { topicQuestion } from '../features/learning/journey.js'
const props = defineProps({ overview: Object, goals: String })
const emit = defineEmits(['navigate'])
const focus = computed(() => props.overview?.recommendations?.[0])
</script>

<template>
  <section class="learning-next" aria-label="下一步学习建议">
    <p class="eyebrow">下一步</p>
    <h3>{{ focus?.name || '从一份资料开始' }}</h3>
    <p v-if="goals" class="small muted">学习目标：{{ goals }}</p>
    <p>{{ focus?.reasons?.[0] || '添加课程资料，提出一个问题，再用练习检验理解。' }}</p>
    <p v-if="focus" class="small muted">正式作答 {{ focus.objective.attempts }} 次 · {{ focus.objective.has_evidence ? '已有客观答题依据' : '待诊断，尚无客观答题依据' }}</p>
    <div class="journey-actions">
      <button class="button primary" @click="emit('navigate', 'study', focus ? { knowledge: focus.knowledge_id, question: topicQuestion(focus.name) } : {})">{{ focus ? '学习这个知识点' : '添加资料并提问' }}</button>
      <button class="button secondary" @click="emit('navigate', 'practice', focus ? { knowledge: focus.knowledge_id } : {})">查找相关练习</button>
      <button class="wb-text-button" @click="emit('navigate', 'learn')">{{ focus?.available_questions === 0 ? '正式新题已用完 · 查看复习' : '进入正式诊断 / 复测' }}</button>
    </div>
  </section>
</template>
