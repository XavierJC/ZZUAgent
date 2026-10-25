<script setup>
import { useCurrentCourseSpace } from '../../app/courseSpace.js'
import PracticeHub from '../../views/PracticeHub.vue'
import ExerciseDesk from './ExerciseDesk.vue'
import PracticeModes from './PracticeModes.vue'
const space = useCurrentCourseSpace()
const { practice, documents } = space.features
</script>
<template><template v-if="space.modern"><PracticeModes @navigate="space.navigate" /><ExerciseDesk :workspace="practice" :documents="documents" :context="space.route.params" :points="space.w.knowledge" @navigate="space.navigate" /></template><PracticeHub v-else :workspace="practice" :documents="documents" :context="space.route.params" :points="space.w.knowledge" @navigate="space.navigate" /></template>
