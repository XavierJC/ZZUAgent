<script setup>
import { useCurrentCourseSpace } from '../../app/courseSpace.js'
import StudyWorkbench from '../../components/StudyWorkbench.vue'
const space = useCurrentCourseSpace()
const { chat, documents, assessment } = space.features
</script>
<template>
  <StudyWorkbench :workspace="chat" :document-workspace="documents" :self-workspace="assessment"
    :snapshot="space.w.snapshot" :goal-names="space.goalsText" :current-topic="space.w.decision?.knowledge_id"
    @navigate="space.navigate" @edit-note="space.navigate('notes',{note:$event})" />
</template>
