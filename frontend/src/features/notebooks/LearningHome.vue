<script setup>
import { computed } from 'vue'
import Icon from '../../components/Icon.vue'
import LearningProgress from '../../shared/LearningProgress.vue'
const props = defineProps({ space: Object, books: Object })
const emit = defineEmits(['create'])
const snapshot = computed(() => props.space.w?.snapshot)
const mastery = computed(() => snapshot.value?.mastery || [])
const diagnosed = computed(() => mastery.value.filter(p => p.has_evidence).length)
const attempts = computed(() => mastery.value.reduce((sum,p) => sum + (p.attempts || 0), 0))
const goal = computed(() => props.space.goalsText || '尚未设置正式学习目标')
const recent = computed(() => [...props.books.items].filter(b => !b.archived).sort((a,b) => new Date(b.updated_at)-new Date(a.updated_at)))
const resume = computed(() => {
  const current = props.books.current?.detail
  return current && !current.archived ? current : recent.value[0]
})
function continueLearning() { if(resume.value) props.space.navigate('notebook',{book:resume.value.id}); else emit('create') }
</script>
<template>
  <div class="learning-home-grid">
    <section class="learning-resume" aria-label="当前学习与下一步">
      <span class="learning-course-label"><Icon name="book" :size="17" />机器学习</span>
      <h2>{{resume?'接着上次的内容学':'从一个问题开始'}}</h2>
      <p v-if="resume">继续「{{resume.title}}」{{resume.description?'：'+resume.description:'，从所选资料出发，提出一个问题。'}}</p>
      <p v-else>建立一个学习主题，把课件、问答、笔记和练习放在一起。</p>
      <div class="journey-actions"><button class="product-primary" @click="continueLearning">{{resume?'继续学习':'开始我的第一个主题'}}<Icon name="arrow" :size="17" /></button><button class="product-text-button" @click="space.navigate('learn')">{{diagnosed?'再测一下':'不确定学什么？先测一下'}}</button></div>
    </section>
    <section class="learning-evidence-card" aria-label="真实测评状态"><h2>{{diagnosed?'看看最近的进步':'还没测过，也可以先学'}}</h2><LearningProgress :value="diagnosed" :total="mastery.length" label="已有答题记录的知识点" description="按实际作答记录展示，待诊断的内容不会预先打分。" /><p>已测 {{attempts}} 次</p><details><summary>学习范围</summary><p>{{goal}}</p></details><button class="product-text-button" @click="space.navigate('insights')">查看学习进度<Icon name="arrow" :size="15" /></button></section>
  </div>
</template>
