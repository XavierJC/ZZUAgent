import { ref, onMounted, onUnmounted } from 'vue'

const pages = new Set(['learn', 'study', 'materials', 'bank', 'notes', 'history'])
export function usePageRoute(before = () => true) {
  function read() {
    const [page, query = ''] = location.hash.replace(/^#\/?/, '').split('?')
    return { page: pages.has(page) ? page : 'learn', params: Object.fromEntries(new URLSearchParams(query)) }
  }
  const route = ref(read())
  function go(page, params = {}, replace = false) {
    if (!pages.has(page) || !before()) return false
    const query = new URLSearchParams(Object.entries(params).filter(([, v]) => v))
    const hash = `#/${page}${query.size ? '?' + query : ''}`
    history[replace ? 'replaceState' : 'pushState'](null, '', hash)
    route.value = read()
    return true
  }
  function pop() {
    if (before()) route.value = read()
    else {
      const query=new URLSearchParams(route.value.params)
      history.replaceState(null,'',`#/${route.value.page}${query.size ? '?' + query : ''}`)
    }
  }
  onMounted(() => { window.addEventListener('popstate', pop); window.addEventListener('hashchange',pop) })
  onUnmounted(() => { window.removeEventListener('popstate', pop); window.removeEventListener('hashchange',pop) })
  return { route, go }
}
