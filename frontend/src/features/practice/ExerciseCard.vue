<script setup>
import { computed } from 'vue'
import QuestionContent from '../questions/QuestionContent.vue'
import MarkdownRenderer from '../../components/MarkdownRenderer.vue'
import { questionTypes, objective } from '../questions/types.js'
const props = defineProps({ workspace: Object, readonly: Boolean })
const w = props.workspace
const question = computed(() => w.session?.question)
const multiple = computed(() => question.value?.question_type === 'multiple_choice')
const choice = computed(() => objective(question.value) || multiple.value)
const selectedKeys = computed(() => w.selected.split(',').map(v => v.trim()))
function select(key, checked) {
  if (!multiple.value) { w.selected = key; return }
  const values = new Set(selectedKeys.value.filter(Boolean))
  if (checked) values.add(key); else values.delete(key)
  w.selected = question.value.options.filter(o => values.has(o.key)).map(o => o.key).join(',')
}
</script>
<template>
  <article v-if="question" class="exercise-card">
    <header><span class="exercise-type">{{questionTypes[question.question_type]}}</span><span>{{w.session.source.title || '我的题目'}} · 第{{w.session.question_revision}}版</span></header>
    <div class="exercise-stem"><QuestionContent :value="question" /></div>
    <p v-if="question.automation" class="exercise-verification">自动整理 · 答案尚未人工核验，本轮只提供参考对照。</p>
    <form @submit.prevent="!readonly && w.submit()"><fieldset :disabled="Boolean(readonly || w.busy || w.pending || w.session.result)"><legend class="sr-only">{{choice?'选择答案':'文字作答'}}</legend>
      <div v-if="choice" class="exercise-options"><label v-for="option in question.options" :key="option.key" :class="{selected:selectedKeys.includes(option.key)}"><input :type="multiple?'checkbox':'radio'" :name="multiple?'ordinary-multiple':'ordinary-answer'" :checked="multiple?selectedKeys.includes(option.key):w.selected===option.key" :value="option.key" @change="select(option.key,$event.target.checked)" /><span class="exercise-option-key">{{option.key==='true'?'✓':option.key==='false'?'×':option.key}}</span><MarkdownRenderer :source="option.text" /></label></div>
      <div v-else class="exercise-writing"><label for="exercise-response">写下你的思路</label><textarea id="exercise-response" v-model="w.selected" rows="8" maxlength="16000" placeholder="支持 Markdown 和 LaTeX。你的思考过程也值得记录。" @keydown.ctrl.s.prevent="w.saveResponseDraft()" /><label class="exercise-review-check"><input v-model="w.needsReview" type="checkbox" />标记为需要复习（主观标记）</label><p>文字作答独立保存，不进行自动主观评分。</p></div>
      <footer v-if="!w.session.result"><button v-if="!choice || multiple" class="product-secondary" type="button" :disabled="Boolean(w.busy || w.pending)" @click="w.saveResponseDraft()">保存草稿</button><button class="product-primary" :disabled="Boolean(!w.selected.trim() || w.busy || w.pending)">{{w.busy?'正在保存…':'提交作答'}}</button></footer>
    </fieldset></form>
  </article>
</template>
