<script setup>
import { useCurrentCourseSpace } from '../../app/courseSpace.js'
import PracticeHub from '../../views/PracticeHub.vue'
const space = useCurrentCourseSpace()
const { practice, documents } = space.features
</script>
<template><PracticeHub :workspace="practice" :documents="documents" :context="space.route.params" :points="space.w.knowledge" @navigate="space.navigate" /></template>
