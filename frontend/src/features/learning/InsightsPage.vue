<script setup>
import { computed, onMounted, ref } from 'vue'
import { useCurrentCourseSpace } from '../../app/courseSpace.js'
import LearningInsights from '../../views/LearningInsights.vue'
import '../../study-guidance.css'
const space = useCurrentCourseSpace(), config = ref(null)
const capabilities = computed(() => space.features.chat?.capabilities || config.value)
onMounted(async () => {
  const owner = space.w.student
  if (!space.features.chat && space.client.workbenchCapabilities) {
    try { const result = await space.client.workbenchCapabilities(owner); if (owner === space.w.student) config.value = result } catch { /* Rules and saved history remain usable. */ }
  }
})
</script>
<template><LearningInsights :self-workspace="space.features.assessment" :guide-workspace="space.features.guides" :capabilities="capabilities" :goals="space.goalsText" :points="space.w.knowledge" :current="space.flow.data?.next_task?.knowledge_id || space.w.decision?.knowledge_id || space.features.assessment.overview?.recommendations?.[0]?.knowledge_id" @navigate="space.navigate" /></template>
