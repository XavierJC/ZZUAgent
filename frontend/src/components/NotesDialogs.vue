<script setup>
import { nextTick, ref, watch } from 'vue'
const props = defineProps({ workspace: { type: Object, required: true } })
const dialog = ref(null)
let previousFocus
watch(() => props.workspace.guard, async (entry) => {
  if (entry) {
    previousFocus = document.activeElement
    await nextTick(); dialog.value?.querySelector('[data-cancel]')?.focus()
  } else previousFocus?.focus?.()
})
function keydown(event) {
  if (event.key === 'Escape') { event.preventDefault(); props.workspace.resolveGuard('cancel') }
  if (event.key !== 'Tab') return
  const buttons = [...dialog.value.querySelectorAll('button:not(:disabled)')]
  const first = buttons[0], last = buttons.at(-1)
  if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus() }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus() }
}
</script>

<template>
  <div v-if="workspace.guard" class="notes-dialog-backdrop">
    <section ref="dialog" class="notes-dialog" role="dialog" aria-modal="true" aria-labelledby="notes-dialog-title" @keydown="keydown">
      <h2 id="notes-dialog-title">{{ workspace.guard.kind === 'delete' ? '删除这篇笔记？' : '笔记还有未保存的修改' }}</h2>
      <p>{{ workspace.guard.kind === 'delete' ? '删除后将从列表隐藏，本地未保存修改也会移除。服务器保留删除记录以防旧请求恢复笔记。' : '可以先保存到服务器，或保留本机草稿后继续；选择取消可留在当前编辑。' }}</p>
      <p v-if="workspace.error || workspace.storageError" role="alert">{{ workspace.error || workspace.storageError }}</p>
      <div class="notes-actions">
        <button v-if="workspace.guard.kind === 'delete'" class="button primary" :disabled="Boolean(workspace.busy)" @click="workspace.resolveGuard('delete')">确认删除</button>
        <template v-else><button class="button primary" :disabled="Boolean(workspace.busy)" @click="workspace.resolveGuard('save')">保存并继续</button><button class="button secondary" :disabled="Boolean(workspace.busy)" @click="workspace.resolveGuard('keep')">保留本机草稿并继续</button></template>
        <button data-cancel class="button secondary" :disabled="Boolean(workspace.busy)" @click="workspace.resolveGuard('cancel')">取消</button>
      </div>
    </section>
  </div>
</template>
