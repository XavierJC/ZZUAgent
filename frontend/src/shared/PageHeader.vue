<script setup>
defineProps({ eyebrow: String, title: String, description: String, level:{type:Number,default:1} })
</script>
<template><header class="product-page-intro"><div><p v-if="eyebrow" class="product-kicker">{{eyebrow}}</p><component :is="level===2?'h2':'h1'">{{title}}</component><p v-if="description">{{description}}</p></div><div v-if="$slots.default" class="page-header-actions"><slot /></div></header></template>
