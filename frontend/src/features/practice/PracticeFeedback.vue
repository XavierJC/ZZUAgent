<script setup>
import MarkdownRenderer from '../../components/MarkdownRenderer.vue'
import Icon from '../../components/Icon.vue'
defineProps({ result: Object })
</script>
<template>
  <section v-if="result" class="practice-feedback" :class="result.correct===true?'correct':result.correct===false?'incorrect':'ungraded'" role="status"><header><span><Icon :name="result.correct===false?'refresh':'check'" :size="22" /></span><div><h3>{{result.correct===true?'回答正确':result.correct===false?'再巩固一下这个知识点':'作答已保存'}}</h3><p>{{result.correct===null?'本题未进行客观判分，参考内容可帮助你核对思路。':'根据已确认的参考答案判断，本次自由练习不计入掌握度。'}}</p></div></header><div v-if="result.reference_answer || result.correct_answer" class="feedback-reference"><span>{{result.correct===null?'参考答案 · 来源审核状态以原题为准':'已确认答案'}}</span><MarkdownRenderer :source="String(result.correct_answer ?? result.reference_answer)" /></div><p v-if="result.reference_match!=null" class="feedback-reference-match">{{result.reference_match?'与未核验参考答案一致':'与未核验参考答案不同'}}，不作为客观评分。</p><MarkdownRenderer v-if="result.explanation" :source="result.explanation" /><small v-if="result.needs_review">已按你的主观判断标记需要复习。</small></section>
</template>
