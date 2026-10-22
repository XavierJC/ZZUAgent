<script setup>
import PersonalBankWorkspace from '../components/PersonalBankWorkspace.vue'
defineProps({ workspace: Object })
defineEmits(['navigate'])
</script>
<template>
  <PersonalBankWorkspace mode="bank" :workspace="workspace" @navigate="(...args) => $emit('navigate', ...args)" />
</template>
