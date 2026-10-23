<script setup>
import { onMounted } from 'vue'
import SelfAssessmentPanel from '../components/SelfAssessmentPanel.vue'
import LearningGuidancePanel from '../components/LearningGuidancePanel.vue'
import StudyGuidePanel from '../components/StudyGuidePanel.vue'
const props=defineProps({selfWorkspace:Object,guideWorkspace:Object,goals:String})
defineEmits(['navigate'])
onMounted(()=>{props.selfWorkspace.load();props.guideWorkspace.load()})
</script>
<template><section class="phase5-builder"><section class="panel"><h2>学习目标与证据</h2><p>{{ goals }}</p><p>自评是主观报告；BKT是依据客观作答的模型估计。无答题证据时待诊断。现有标识的目标固定，改变目标请新建演示标识，避免混用历史。</p><button class="button secondary" @click="$emit('navigate','learn')">返回下一步学习任务</button></section><SelfAssessmentPanel :workspace="selfWorkspace" /><LearningGuidancePanel :overview="selfWorkspace.overview" @navigate="$emit('navigate',$event)" /><StudyGuidePanel :workspace="guideWorkspace" /></section></template>
