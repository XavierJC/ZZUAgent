<script setup>
import { computed } from 'vue'
import { renderMarkdown } from '../rendering/markdown.js'
import 'katex/dist/katex.min.css'
import 'highlight.js/styles/github-dark.css'
import '../rendering/markdown.css'

const props = defineProps({ source: { type: String, default: '' }, inline: Boolean, citationIds: { type: Array, default: () => [] }, numberCitations: Boolean })
const emit = defineEmits(['citation'])
const rendered = computed(() => renderMarkdown(props.source, { inline: props.inline, citationIds: props.citationIds, numberCitations: props.numberCitations }))
function openCitation(event) {
  const anchor = event.target.closest?.('a')
  const href = anchor?.getAttribute('href') || ''
  if (!href.startsWith('#eduagent-citation/')) return
  event.preventDefault()
  let id
  try { id = decodeURIComponent(href.slice('#eduagent-citation/'.length)) } catch { return }
  if (props.citationIds.includes(id)) emit('citation', id)
}
</script>

<template>
  <component :is="inline ? 'span' : 'div'" class="markdown-content" :class="{ 'markdown-inline': inline }" @click="openCitation">
    <!-- This is the sole HTML sink; renderMarkdown sanitizes all plugin output. -->
    <component :is="inline ? 'span' : 'div'" class="markdown-body" v-html="rendered.html" />
    <span v-for="notice in rendered.notices" :key="notice" class="markdown-notice" role="status">{{ notice }}</span>
  </component>
</template>
