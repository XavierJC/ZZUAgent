<script setup>
import { useCurrentCourseSpace } from '../../app/courseSpace.js'
import { ref, watch } from 'vue'
import ResourceLibrary from './ResourceLibrary.vue'
import TeachingMaterialReview from '../../components/TeachingMaterialReview.vue'
import CourseMaterialSearch from './CourseMaterialSearch.vue'
const space = useCurrentCourseSpace()
const view = ref('resources')
watch(() => space.features.library.resource?.resource_id, id => {
  if (space.tab === 'materials' && id && space.route.params.resource !== id) space.replaceRoute('materials', { resource: id })
})
</script>
<template>
  <nav class="doc-switch" aria-label="课程资料视图"><button class="button secondary" :aria-pressed="view==='resources'" @click="view='resources'">资料目录与上传</button><button class="button secondary" @click="space.navigate('architecture')">课程知识体系</button><button class="button secondary" :aria-pressed="view==='search'" @click="view='search'">课程片段检索</button></nav>
  <ResourceLibrary v-if="view==='resources'" :workspace="space.features.library" :documents="space.features.documents" @navigate="space.navigate" @edit-note="space.navigate('notes',{note:$event})" />
  <CourseMaterialSearch v-else :workspace="space.w" />
  <TeachingMaterialReview v-if="space.client.teachingLinks" :workspace="space.features.links" :documents="space.features.documents" :student="space.w.student" />
</template>
