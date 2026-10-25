<script setup>
import { ref } from 'vue'
import { useOverlayFocus } from './useOverlayFocus.js'
import Icon from '../components/Icon.vue'
const props = defineProps({ open: Boolean, title: String })
const emit = defineEmits(['close'])
const panel = ref(null)
const keyboard = useOverlayFocus(() => props.open, panel, () => emit('close'))
</script>
<template><div v-if="open" class="product-dialog-backdrop" @click.self="emit('close')"><section ref="panel" tabindex="-1" class="product-dialog" role="dialog" aria-modal="true" :aria-label="title" @keydown="keyboard"><header><h2>{{title}}</h2><button class="product-icon-button" aria-label="关闭对话框" @click="emit('close')"><Icon name="close" :size="19" /></button></header><slot /></section></div></template>
