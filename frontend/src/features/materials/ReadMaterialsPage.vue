<script setup>
import { useCurrentCourseSpace } from '../../app/courseSpace.js'
import LearningResources from '../../views/LearningResources.vue'
import './resource-library.css'
const space = useCurrentCourseSpace()
</script>
<template><div class="resource-library"><LearningResources :workspace="space.features.library" @navigate="space.navigate" @edit-note="space.navigate('notes',{note:$event})" /></div></template>
