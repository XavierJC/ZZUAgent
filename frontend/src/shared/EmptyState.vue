<script setup>
import Icon from '../components/Icon.vue'
defineProps({ title: String, description: String, icon: { type: String, default: 'book' } })
</script>
<template><section class="product-empty"><span class="product-empty-icon"><Icon :name="icon" :size="30" /></span><h2>{{title}}</h2><p>{{description}}</p><slot /></section></template>
