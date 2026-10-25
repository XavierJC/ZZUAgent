<script setup>
import { useCurrentCourseSpace } from '../../app/courseSpace.js'
import QuestionBankView from '../../views/QuestionBankView.vue'
import { watch } from 'vue'
const space = useCurrentCourseSpace()
const bank = space.features.practice
watch([() => bank.current?.id, () => bank.section], ([id, section]) => {
  if (space.tab === 'bank' && id && (id !== space.route.params.question || section !== space.route.params.view)) {
    space.replaceRoute('bank', { ...space.route.params, question: id, view: section })
  }
})
</script>
<template><QuestionBankView :workspace="space.features.practice" :compact="space.modern" @navigate="space.navigate" /></template>
