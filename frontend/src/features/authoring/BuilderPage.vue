<script setup>
import { useCurrentCourseSpace } from '../../app/courseSpace.js'
import CourseBuilderView from '../../views/CourseBuilderView.vue'
const space = useCurrentCourseSpace()
</script>
<template><CourseBuilderView :workspace="space.features.builder" :overview="space.tab==='builder'" @navigate="space.navigate" /></template>
