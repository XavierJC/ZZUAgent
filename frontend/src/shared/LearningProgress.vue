<script setup>
import { computed } from 'vue'
const props = defineProps({ value: Number, total: Number, label: String, description: String })
const count = computed(() => Math.max(0, Math.min(props.value || 0, props.total || 0)))
</script>
<template><div class="learning-progress"><div><span>{{label}}</span><strong>{{count}} / {{total || 0}}</strong></div><progress :value="count" :max="total || 1" :aria-label="label" :aria-valuetext="`${count} / ${total || 0}`">{{count}} / {{total || 0}}</progress><p v-if="description">{{description}}</p></div></template>
