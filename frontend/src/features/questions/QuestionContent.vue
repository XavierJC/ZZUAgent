<script setup>
import MarkdownRenderer from '../../components/MarkdownRenderer.vue'
defineProps({ value: Object })
</script>
<template>
  <MarkdownRenderer v-if="value.shared_context" :source="value.shared_context" />
  <MarkdownRenderer :source="value.stem" />
  <section v-for="(sub,index) in value.subquestions || []" :key="index"><h4>子问 {{ sub.number || index+1 }}</h4><QuestionContent :value="sub" /></section>
</template>
