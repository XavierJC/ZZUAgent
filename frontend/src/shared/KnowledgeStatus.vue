<script setup>
import { computed } from 'vue'
import LearningProgress from './LearningProgress.vue'
const props = defineProps({ items: {type:Array,default:()=>[]}, points: {type:Array,default:()=>[]}, current: String })
defineEmits(['practice'])
const pointName = id => props.points.find(p=>p.id===id)?.name || id
const evidence = computed(() => props.items.filter(p=>p.objective.has_evidence).length)
</script>
<template>
  <div class="knowledge-status"><LearningProgress :value="evidence" :total="items.length" label="正式诊断覆盖" description="BKT是基于正式答题的模型估计。先修关系沿用现有课程配置，不代表已解锁或已掌握。" /><ul class="knowledge-map-list"><li v-for="point in items" :key="point.knowledge_id" :class="{current:current===point.knowledge_id}"><strong>{{point.name}}</strong><p v-if="current===point.knowledge_id">当前建议知识点</p><p>{{point.objective.has_evidence ? `BKT ${(point.objective.probability*100).toFixed(1)}% · 正式作答 ${point.objective.attempts} 次` : '待诊断 · 尚无正式答题依据'}}</p><p>先修：{{points.find(p=>p.id===point.knowledge_id)?.prerequisites?.map(pointName).join('、') || '无配置先修'}}</p><p>自评：{{point.self_report ? `${point.self_report.level}级 · 信心 ${point.self_report.confidence ?? '未填'}` : '尚未填写'}}</p><button class="product-text-button" @click="$emit('practice',point.knowledge_id)">查找练习 →</button></li></ul></div>
</template>
