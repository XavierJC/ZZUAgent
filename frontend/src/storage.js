const KEY = 'eduagent.workspace.v1'

// Browser storage can be unavailable (private mode/quota). Its absence must
// never prevent reads; uncertain answer writes require a durable receipt.
export function browserStore(storage) {
  return {
    read() {
      try {
        const value = JSON.parse((storage || globalThis.localStorage).getItem(KEY) || '{}')
        return value && typeof value === 'object' && !Array.isArray(value) ? value : {}
      } catch { return {} }
    },
    write(value) {
      try { (storage || globalThis.localStorage).setItem(KEY, JSON.stringify(value)); return true } catch { return false }
    },
  }
}
