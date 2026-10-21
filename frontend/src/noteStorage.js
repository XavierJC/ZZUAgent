// Scope-local draft recovery; this is neither authentication nor encryption.
export function noteStore(storage) {
  const key = (student) => `eduagent.notes.v1.${encodeURIComponent(student)}.machine_learning`
  return {
    read(student) {
      try {
        const value = JSON.parse((storage || globalThis.localStorage).getItem(key(student)) || '{}')
        return value && typeof value === 'object' && !Array.isArray(value) ? value : {}
      } catch { return {} }
    },
    write(student, value) {
      try { (storage || globalThis.localStorage).setItem(key(student), JSON.stringify(value)); return true } catch { return false }
    },
  }
}
