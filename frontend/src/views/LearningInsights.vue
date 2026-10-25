<script setup>
import { computed, onMounted } from 'vue'
import KnowledgeStatus from '../shared/KnowledgeStatus.vue'
import LearningNextStep from '../components/LearningNextStep.vue'
import SelfAssessmentPanel from '../components/SelfAssessmentPanel.vue'
import LearningGuidancePanel from '../components/LearningGuidancePanel.vue'
import StudyGuidePanel from '../components/StudyGuidePanel.vue'
const props=defineProps({selfWorkspace:Object,guideWorkspace:Object,goals:String,capabilities:Object,points:Array,current:String})
defineEmits(['navigate'])
const items=computed(()=>props.selfWorkspace.overview?.items || [])
const attempts=computed(()=>items.value.reduce((sum,p)=>sum+p.objective.attempts,0))
const diagnosed=computed(()=>items.value.filter(p=>p.objective.has_evidence).length)
onMounted(()=>{props.selfWorkspace.load();props.guideWorkspace.load()})
</script>
<template>
  <section class="phase5-builder">
    <div v-if="selfWorkspace.error" class="alert alert-error" role="alert">{{selfWorkspace.error}}</div>
    <section class="progress-summary" aria-label="学习进度概览"><div class="panel"><span>当前目标</span><strong>{{goals || '尚未选择'}}</strong></div><div class="panel"><span>正式作答</span><strong>{{attempts}} 次</strong></div><div class="panel"><span>已有答题依据</span><strong>{{diagnosed}} / {{items.length}} 个知识点</strong><small>其余待诊断</small></div></section>
    <section class="panel"><LearningNextStep :overview="selfWorkspace.overview" :goals="goals" @navigate="(...args)=>$emit('navigate',...args)" /></section>
    <section class="panel"><header class="wb-section-heading"><h2>知识点学习情况</h2><button class="wb-text-button" @click="selfWorkspace.load()">刷新学习进度</button></header><p class="small muted">掌握情况来自“测一下”的答题记录；你对自己的评价和自由练习另行保存。</p><KnowledgeStatus class="progress-topics" :items="items" :points="points" :current="current" @practice="$emit('navigate','practice',{knowledge:$event})" /><p v-if="!items.length" role="status">正在读取已保存的学情；不会自动分配题目。</p></section>
    <details class="panel"><summary>填写或修改自评</summary><SelfAssessmentPanel :workspace="selfWorkspace" /></details>
    <details class="panel"><summary>推荐依据与主客观对照</summary><LearningGuidancePanel :overview="selfWorkspace.overview" @navigate="(...args)=>$emit('navigate',...args)" /></details>
    <details class="panel"><summary>学习指南与历史</summary><StudyGuidePanel :workspace="guideWorkspace" :self-workspace="selfWorkspace" :capabilities="capabilities" /></details>
  </section>
</template>
