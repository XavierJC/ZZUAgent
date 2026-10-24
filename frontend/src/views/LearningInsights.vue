<script setup>
import { computed, onMounted } from 'vue'
import LearningNextStep from '../components/LearningNextStep.vue'
import SelfAssessmentPanel from '../components/SelfAssessmentPanel.vue'
import LearningGuidancePanel from '../components/LearningGuidancePanel.vue'
import StudyGuidePanel from '../components/StudyGuidePanel.vue'
const props=defineProps({selfWorkspace:Object,guideWorkspace:Object,goals:String,capabilities:Object})
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
    <section class="panel"><header class="wb-section-heading"><h2>知识点学习情况</h2><button class="wb-text-button" @click="selfWorkspace.load()">刷新学习进度</button></header><p class="small muted">BKT依据正式答题估计；自评是主观报告。普通练习单独记录。</p><div class="progress-topics"><article v-for="point in items" :key="point.knowledge_id"><div><strong>{{point.name}}</strong><p class="small">{{point.objective.has_evidence ? `BKT ${(point.objective.probability*100).toFixed(1)}% · 正式作答 ${point.objective.attempts} 次` : '待诊断 · 尚无正式答题依据'}}</p><p class="small muted">自评：{{point.self_report ? `${point.self_report.level}级 · 信心 ${point.self_report.confidence ?? '未填'}` : '尚未填写'}}</p></div><button class="wb-text-button" @click="$emit('navigate','practice',{knowledge:point.knowledge_id})">查找练习</button></article></div><p v-if="!items.length" role="status">正在读取已保存的学情；不会自动分配题目。</p></section>
    <details class="panel"><summary>填写或修改自评</summary><SelfAssessmentPanel :workspace="selfWorkspace" /></details>
    <details class="panel"><summary>推荐依据与主客观对照</summary><LearningGuidancePanel :overview="selfWorkspace.overview" @navigate="(...args)=>$emit('navigate',...args)" /></details>
    <details class="panel"><summary>学习指南与历史</summary><StudyGuidePanel :workspace="guideWorkspace" :self-workspace="selfWorkspace" :capabilities="capabilities" /></details>
  </section>
</template>
