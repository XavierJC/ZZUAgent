<script setup>
import { useCurrentCourseSpace } from '../../app/courseSpace.js'
import LearningOverview from '../../views/LearningOverview.vue'
const space = useCurrentCourseSpace()
</script>
<template><LearningOverview :w="space.w" :review="space.features.review" :flow="space.flow" :self-workspace="space.features.assessment" @navigate="space.navigate" @explain="space.explainNext" /></template>
