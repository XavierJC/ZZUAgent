import { effectScope, reactive, shallowReactive } from 'vue'

// A page may unmount; its state and request receipt must outlive that page.
// Factories run only on explicit use(), never when peeking or protecting drafts.
export function createFeatureRegistry(context, definitions) {
  const states = shallowReactive({})
  const scopes = new Map()
  const creating = new Set()
  let disposed = false
  function use(name) {
    if (disposed) throw new Error('学习空间已关闭')
    if (states[name]) return states[name]
    const definition = definitions[name]
    if (!definition) throw new Error(`未知业务模块：${name}`)
    if (creating.has(name)) throw new Error(`业务模块循环依赖：${name}`)
    const scope = effectScope(true)
    creating.add(name)
    try {
      const state = scope.run(() => reactive(definition.create({ ...context, use, peek })))
      states[name] = state
      scopes.set(name, scope)
      return state
    } catch (error) {
      scope.stop()
      throw error
    } finally { creating.delete(name) }
  }
  function peek(name) { return states[name] }
  function persist() {
    return Object.entries(states).every(([name, state]) =>
      !definitions[name].needsSave?.(state) || state.persist?.() !== false)
  }
  function hasUnsaved() {
    return Object.entries(states).some(([name, state]) => definitions[name].hasUnsaved?.(state))
  }
  function dispose() {
    if (disposed) return
    persist()
    scopes.forEach(scope => scope.stop())
    scopes.clear()
    disposed = true
  }
  return { use, peek, states, persist, hasUnsaved, dispose }
}
