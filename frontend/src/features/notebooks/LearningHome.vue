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
      <span class="learning-course-label"><Icon name="book" :size="17" />机器学习 · 当前目标</span>
      <h2>{{goal}}</h2>
      <p v-if="resume">继续「{{resume.title}}」{{resume.description?'：'+resume.description:'，从所选资料出发，提出一个问题。'}}</p>
      <p v-else>建立一个学习主题，把课件、问答、笔记和练习放在一起。</p>
      <p>{{space.w?.decision?.reason || (diagnosed?'结合已有答题反馈，复习当前目标并查找相关练习。':'尚无正式诊断依据。可以先阅读资料，或明确开始正式诊断。')}}</p>
      <div class="journey-actions"><button class="product-primary" @click="continueLearning">{{resume?'继续学习':'创建学习笔记本'}}<Icon name="arrow" :size="17" /></button><button class="product-text-button" @click="space.navigate('learn')">{{diagnosed?'查看正式复测':'开始正式诊断'}}</button></div>
    </section>
    <section class="learning-evidence-card" aria-label="真实测评状态"><h2>{{diagnosed?'已有正式答题依据':'待诊断'}}</h2><LearningProgress :value="diagnosed" :total="mastery.length" label="有正式答题依据的知识点" description="这是诊断覆盖范围，不代表课程完成度或掌握度。" /><p>正式作答 {{attempts}} 次 · 普通练习与自评独立记录</p><button class="product-text-button" @click="space.navigate('insights')">查看学习进度<Icon name="arrow" :size="15" /></button></section>
  </div>
</template>
