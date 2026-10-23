<script setup>
import { ref } from 'vue'
import PersonalBankWorkspace from '../components/PersonalBankWorkspace.vue'
defineProps({ bank: Object, documents: Object, architecture: Object })
defineEmits(['navigate', 'edit-note'])
const view = ref('resources')
</script>
<template>
  <nav class="doc-switch" aria-label="课程资料视图">
    <button class="button secondary" :aria-pressed="view === 'resources'" @click="view = 'resources'">资料目录与上传</button>
    <button class="button secondary" @click="$emit('navigate','architecture')">课程知识体系</button>
    <button class="button secondary" :aria-pressed="view === 'search'" @click="view = 'search'">课程片段检索</button>
  </nav>
  <PersonalBankWorkspace v-if="view === 'resources'" mode="resources" :workspace="bank" :document-workspace="documents" @edit-note="$emit('edit-note', $event)" @navigate="(...args) => $emit('navigate', ...args)" />
  <slot v-else />
</template>
