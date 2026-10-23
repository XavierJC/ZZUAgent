<script setup>
import { useId } from 'vue'
import MarkdownRenderer from './MarkdownRenderer.vue'
defineProps({ review: Object, topicName: Function })
defineEmits(['explain', 'navigate'])
const id = `review-${useId()}`
</script>

<template>
  <section class="panel question-panel review-practice" :aria-labelledby="`${id}-title`">
    <div class="panel-heading"><h2 :id="`${id}-title`">复习已做题</h2><button class="button secondary" @click="review.close()">返回正式学习</button></div>
    <p>可以反复作答、对照原解析。复习不更新 BKT，也不计入正式答题次数。</p>
    <p class="small muted">按原作答时保存的题目和答案复习；演示内容仍待人工审阅。进度仅保存在当前浏览器，清理浏览器或换设备后不会同步。</p>
    <p v-if="review.storageWarning" role="status">{{ review.storageWarning }}</p>
    <p v-if="review.error" class="alert alert-error" role="alert">{{ review.error }}<button class="button secondary" @click="review.load()">重新读取复习题</button></p>
    <p v-if="review.busy" role="status">正在读取已做题…</p>
    <template v-else-if="review.items.length">
      <label :for="`${id}-topic`">复习知识点</label>
      <select :id="`${id}-topic`" :value="review.focus" @change="review.changeFocus($event.target.value)"><option value="">全部已做题</option><option v-for="topic in review.topics" :key="topic" :value="topic">{{ topicName(topic) }}</option></select>
      <template v-if="review.current">
        <p class="small muted">{{ review.list.length }} 道可循环复习 · 本机已复习 {{ review.records.length }} 次（最多保留最近50次）</p>
        <div class="question-tags"><span class="badge badge-blue">复习 · 不计掌握度</span><span class="tag">{{ topicName(review.current.question.knowledge_id) }}</span><span class="tag">{{ review.current.last_correct ? '原作答正确' : '原错题，优先复习' }}</span></div>
        <form @submit.prevent="review.submit()">
          <fieldset :disabled="Boolean(review.result)" :aria-labelledby="`${id}-stem`">
            <MarkdownRenderer :id="`${id}-stem`" class="question-stem" :source="review.current.question.stem" />
            <label v-for="(text, key) in review.current.question.options" :key="key" class="option" :class="{selected: review.selected === key, correct: review.result && review.current.correct_answer === key, incorrect: review.result && !review.result.correct && review.selected === key}">
              <input type="radio" :name="`${id}-answer`" :value="key" :checked="review.selected === key" @change="review.select(key)" /><span class="option-key">{{ key }}</span><MarkdownRenderer :source="text" inline />
            </label>
          </fieldset>
          <div v-if="!review.result" class="question-actions"><span class="small muted">仅用于复习自查</span><button class="button primary" type="submit" :disabled="!review.selected">核对复习答案</button></div>
        </form>
        <div v-if="review.result" class="feedback" :class="review.result.correct ? 'feedback-correct' : 'feedback-wrong'" role="status" aria-live="polite">
          <strong>{{ review.result.correct ? '本次复习答对了。' : `本次复习再想一想，原参考答案为 ${review.current.correct_answer}。` }}</strong>
          <MarkdownRenderer :source="review.current.explanation" /><p>正式掌握度和答题记录保持不变。</p>
          <button class="button primary" @click="review.next()">{{ review.list.length > 1 ? '复习下一题' : '再练一遍' }}</button>
        </div>
      </template>
    </template>
    <p v-else-if="!review.error && !review.busy">当前标识还没有可复习的已做题。可以先完成正式诊断，或进入已有普通练习。</p>
    <div class="phase5-actions"><button class="button secondary" @click="$emit('explain')">请助教讲解当前薄弱点</button><button class="button secondary" @click="$emit('navigate','practice')">进入普通练习</button></div>
  </section>
</template>

<style scoped>
.review-practice select { width: 100%; margin: 8px 0 12px; }
.review-practice .panel-heading { flex-wrap: wrap; gap: 12px; }
.review-practice fieldset { min-width: 0; }
.review-practice :deep(.markdown-renderer) { min-width: 0; overflow-wrap: anywhere; }
</style>
