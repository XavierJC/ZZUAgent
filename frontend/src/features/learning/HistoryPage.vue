<script setup>
import { useCurrentCourseSpace } from '../../app/courseSpace.js'
import LearningHistory from '../../views/LearningHistory.vue'
const space = useCurrentCourseSpace()
</script>
<template><LearningHistory :w="space.w" @navigate="space.navigate" /></template>
