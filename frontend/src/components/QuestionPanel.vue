<script setup>
import { useId } from 'vue'
import { actionLabels, percent } from '../useWorkspace.js'
import Icon from './Icon.vue'
import MarkdownRenderer from './MarkdownRenderer.vue'
defineProps({ decision: Object, selected: String, feedback: Object, pending: Object, busy: String, topic: String, canReview: Boolean })
defineEmits(['select', 'submit', 'next', 'review', 'explain', 'navigate'])
const difficulties = { easy: '基础', medium: '进阶', hard: '挑战' }
const questionId = `question-stem-${useId()}`
</script>

<template>
  <section class="panel question-panel" aria-labelledby="question-title">
    <div class="panel-heading"><div><p class="eyebrow">ONE STEP AT A TIME</p><h2 id="question-title">{{ feedback ? '这道题，收获了什么？' : '从这一道题开始' }}</h2></div><span class="step-number">{{ decision ? String(decision.revision + 1).padStart(2, '0') : '…' }}</span></div>
    <div v-if="pending && decision?.decision_id !== pending.decision_id" class="empty-state" role="status">
      <h3>先确认上一次答题的结果。</h3><p>当前学习安排已经变化，原提交尚未确认。重试原编号会恢复对应回执，不会重复计分。</p>
      <button class="button primary" :disabled="Boolean(busy)" @click="$emit('submit')">重试原提交<Icon name="refresh" :size="17" /></button>
    </div>
    <template v-else-if="decision?.question">
      <div class="question-tags"><span class="badge badge-blue">{{ actionLabels[decision.action] }}</span><span class="tag">{{ topic }}</span><span class="tag">{{ difficulties[decision.question.difficulty] }}</span></div>
      <p class="decision-reason">{{ decision.reason }}</p>
      <form @submit.prevent="$emit('submit')">
        <fieldset :disabled="Boolean(busy || feedback || pending)" :aria-labelledby="questionId">
          <MarkdownRenderer :id="questionId" class="question-stem" :source="decision.question.stem" />
          <label v-for="(text, key) in decision.question.options" :key="key" class="option" :class="{ selected: selected === key, correct: feedback?.correct_answer === key, incorrect: feedback && !feedback.correct && feedback.selected_answer === key }">
            <input type="radio" name="answer" :value="key" :checked="selected === key" @change="$emit('select', key)" />
            <span class="option-key">{{ key }}</span><MarkdownRenderer :source="text" inline /><Icon v-if="feedback?.correct_answer === key" name="check" :size="18" />
          </label>
        </fieldset>
        <div v-if="!feedback" class="question-actions"><span class="small muted">{{ pending ? '重试会使用原提交编号' : '选择答案后查看解析与反馈' }}</span><button class="button primary" type="submit" :disabled="Boolean(busy || (!selected && !pending))">{{ busy === 'submit' ? '正在评分…' : pending ? '重试原提交' : '提交答案' }}<Icon name="arrow" :size="18" /></button></div>
      </form>
    </template>
    <div v-else-if="!feedback && decision" class="empty-state">
      <div class="empty-icon"><Icon :name="decision.action === 'finish' ? 'check' : 'book'" :size="30" /></div>
      <h3>{{ decision.stop_reason === 'insufficient_questions' ? '正式新题已做完，可以继续复习' : actionLabels[decision.action] }}</h3><p>{{ decision.reason }}</p>
      <template v-if="decision.stop_reason === 'insufficient_questions'">
        <p class="small muted">新题不足不代表已经掌握。可以复习已做题、查看讲解或做普通练习；这些活动不会重复计入掌握度。有新题加入后，还可以继续测一下。</p>
        <div class="phase5-actions"><button v-if="canReview" class="button primary" :disabled="Boolean(busy)" @click="$emit('review')">复习已做题（不更新掌握度）</button><button class="button secondary" @click="$emit('explain')">请助教讲解薄弱点</button><button class="button secondary" @click="$emit('navigate','practice')">进入普通练习</button></div>
      </template>
    </div>
    <p v-else-if="!feedback" class="muted">正在读取你的下一步学习安排…</p>
    <div v-if="feedback" class="feedback" :class="feedback.correct ? 'feedback-correct' : 'feedback-wrong'" role="status" aria-live="polite">
      <strong>{{ feedback.correct ? '答对了，继续积累。' : `再理解一步。正确选项为 ${feedback.correct_answer}。` }}</strong>
      <MarkdownRenderer :source="feedback.explanation" />
      <div class="feedback-mastery">掌握度估计 <span>{{ percent(feedback.prior) }}</span><Icon name="arrow" :size="15" /><b>{{ percent(feedback.next_mastery) }}</b></div>
      <details class="small"><summary>查看本次估计依据</summary><p>答题前 {{ percent(feedback.prior) }}；结合正误后的后验 {{ percent(feedback.posterior) }}；学习转移后 {{ percent(feedback.next_mastery) }}。这是演示参数下的概率估计。</p></details>
      <button class="button primary" :disabled="Boolean(busy)" @click="$emit('next')">继续下一步<Icon name="arrow" :size="18" /></button>
    </div>
  </section>
</template>
