<script setup>
import { useCurrentCourseSpace } from '../../app/courseSpace.js'
import KnowledgeArchitecture from '../../components/KnowledgeArchitecture.vue'
const space = useCurrentCourseSpace()
</script>
<template><KnowledgeArchitecture :workspace="space.features.architecture" @navigate="space.navigate" /></template>
