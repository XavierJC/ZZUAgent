<script setup>
defineProps({ active: { type: String, default: 'practice' } })
defineEmits(['navigate'])
</script>
<template>
  <nav class="practice-modes" aria-label="练习方式">
    <button :aria-pressed="active==='practice'" :class="{active:active==='practice'}" @click="$emit('navigate','practice')"><strong>自由练习</strong><span>巩固知识，按自己的节奏来</span></button>
    <button :aria-pressed="active==='learn'" :class="{active:active==='learn'}" @click="$emit('navigate','learn')"><strong>测一下</strong><span>根据答题更新掌握情况</span></button>
  </nav>
</template>
