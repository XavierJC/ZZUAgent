<script setup>
import { useCurrentCourseSpace } from '../../app/courseSpace.js'
import PracticeHub from '../../views/PracticeHub.vue'
import ExerciseDesk from './ExerciseDesk.vue'
const space = useCurrentCourseSpace()
const { practice, documents } = space.features
</script>
<template><ExerciseDesk v-if="space.modern" :workspace="practice" :documents="documents" :context="space.route.params" :points="space.w.knowledge" @navigate="space.navigate" /><PracticeHub v-else :workspace="practice" :documents="documents" :context="space.route.params" :points="space.w.knowledge" @navigate="space.navigate" /></template>
