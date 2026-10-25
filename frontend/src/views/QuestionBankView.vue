<script setup>
import PersonalBankWorkspace from '../components/PersonalBankWorkspace.vue'
defineProps({ workspace: Object, compact: Boolean })
defineEmits(['navigate'])
</script>
<template>
  <PersonalBankWorkspace mode="bank" :workspace="workspace" :compact="compact" @navigate="(...args) => $emit('navigate', ...args)" />
</template>
