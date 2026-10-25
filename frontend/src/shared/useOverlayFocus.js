import { nextTick, onUnmounted, watch } from 'vue'

// Reference counts keep nested overlays from enabling each other's background.
const blocked = new Map()
let locks = 0, originalOverflow = ''
export function useOverlayFocus(open, panel, close) {
  let before, siblings = [], active = false, generation = 0
  function release() {
    if (!active) return
    active = false
    for (const el of siblings) {
      const record = blocked.get(el)
      if (record && --record.count === 0) { el.inert = record.original; blocked.delete(el) }
    }
    siblings = []
    if (--locks === 0) document.body.style.overflow = originalOverflow
    if (before?.isConnected && !before.closest('[inert]')) before.focus?.()
  }
  watch(open, async value => {
    const token = ++generation
    if (!value) { release(); return }
    before = document.activeElement
    await nextTick()
    if (token !== generation || !panel.value || active) return
    active = true
    if (locks++ === 0) { originalOverflow = document.body.style.overflow; document.body.style.overflow = 'hidden' }
    for (let branch = panel.value; branch?.parentElement && branch.parentElement !== document.documentElement; branch = branch.parentElement) {
      for (const sibling of branch.parentElement.children) {
        if (sibling === branch || !(sibling instanceof HTMLElement)) continue
        const record = blocked.get(sibling) || { count: 0, original: sibling.inert }
        record.count++; blocked.set(sibling,record); sibling.inert = true; siblings.push(sibling)
      }
    }
    const first = panel.value.querySelector('input:not(:disabled),textarea:not(:disabled)') || panel.value.querySelector('button:not(:disabled),select:not(:disabled),a[href]')
    ;(first || panel.value).focus()
  }, { immediate:true, flush:'post' })
  onUnmounted(() => { generation++; release() })
  function keydown(event) {
    if (!open()) return
    if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); close(); return }
    if (event.key !== 'Tab') return
    const nodes = [...panel.value.querySelectorAll('button:not(:disabled),input:not(:disabled),textarea:not(:disabled),select:not(:disabled),a[href],summary,[tabindex="0"]')].filter(el => {
      if (el.closest('[inert]')) return false
      for (let parent=el.parentElement; parent && parent!==panel.value; parent=parent.parentElement) {
        if (parent.tagName==='DETAILS' && !parent.open && parent.querySelector('summary')!==el) return false
      }
      return getComputedStyle(el).display !== 'none' && getComputedStyle(el).visibility !== 'hidden'
    })
    const first=nodes[0], last=nodes.at(-1)
    if (!first) { event.preventDefault(); panel.value.focus(); return }
    if (event.shiftKey && (document.activeElement===first || document.activeElement===panel.value)) { event.preventDefault(); last.focus() }
    else if (!event.shiftKey && document.activeElement===last) { event.preventDefault(); first.focus() }
  }
  return keydown
}
