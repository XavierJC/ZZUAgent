<script setup>
import { computed, defineAsyncComponent, provide } from 'vue'
import { courseSpaceKey, useCourseSpace } from './app/courseSpace.js'
import CourseShell from './app/CourseShell.vue'
import CourseWelcome from './app/CourseWelcome.vue'
import CoursePage from './app/CoursePage.vue'
import Icon from './components/Icon.vue'
import AuthoringSteps from './app/AuthoringSteps.vue'
import { headings } from './app/navigation.js'
import './phase5.css'

const props = defineProps({ client: Object, store: Object, notesStore: Object })
const space = useCourseSpace(props)
provide(courseSpaceKey, space)
const NotesDialogs = defineAsyncComponent(() => import('./components/NotesDialogs.vue'))
const heading = computed(() => headings[space.tab] || headings.study)
</script>

<template>
  <CourseShell :space="space">
    <NotesDialogs v-if="space.features.notes" :workspace="space.features.notes" />
    <div v-if="space.tab!=='notes' && space.features.notes?.error" class="alert alert-error" role="alert">{{space.features.notes.error}}</div>
    <div v-if="space.w.error" class="alert alert-error" role="alert">{{space.w.error}}<span v-if="space.w.pending">原提交编号已保留，请重试原提交。</span></div>
    <div v-if="space.w.notice" class="alert alert-info" role="status">{{space.w.notice}}</div>
    <div v-if="space.routeError" class="alert alert-error" role="alert">{{space.routeError}}</div>
    <div v-if="space.w.busy==='boot'" class="loading-state" role="status">正在准备你的学习空间…</div>
    <CourseWelcome v-else-if="!space.w.active" :space="space" />
    <template v-else>
      <section v-if="!space.modern || !['notebooks','notebook','practice','learn'].includes(space.tab)" class="page-heading" :class="{'learning-page-heading':['study','practice','insights'].includes(space.tab)}">
        <div><p class="eyebrow">{{space.isBuilder?'课程内容维护':'COURSE LEARNING SPACE'}}</p><h1>{{heading[0]}}</h1><p>{{heading[1]}}</p></div>
        <span class="course-badge"><Icon name="book" :size="17" />{{space.course.title}}</span>
      </section>
      <AuthoringSteps v-if="space.isBuilder && space.modern" :current="space.tab" @navigate="space.navigate" />
      <CoursePage :space="space" />
    </template>
  </CourseShell>
</template>
