<script setup>
defineProps({ current: String })
defineEmits(['navigate'])
const steps = [{page:'materials',title:'查看资料原件'},{page:'architecture',title:'整理知识结构'},{page:'bank',title:'校对习题内容'},{page:'publish',title:'检查课程发布'}]
</script>
<template><nav class="authoring-steps" aria-label="课程准备流程"><button v-for="(step,i) in steps" :key="step.page" :aria-current="current===step.page?'step':undefined" @click="$emit('navigate',step.page)"><span>{{i+1}}</span>{{step.title}}</button></nav></template>
