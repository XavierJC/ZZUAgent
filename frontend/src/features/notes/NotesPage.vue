<script setup>
import { useCurrentCourseSpace } from '../../app/courseSpace.js'
import NotesPanel from '../../components/NotesPanel.vue'
const space = useCurrentCourseSpace()
</script>
<template><NotesPanel :workspace="space.features.notes" :knowledge="space.w.knowledge" /></template>
