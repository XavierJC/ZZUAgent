import { vi } from 'vitest'
import { ApiError } from '../api.js'

export const copy = value => JSON.parse(JSON.stringify(value))
export const noteId = '4a973493-950c-4970-82c4-d29d3346d10c'
export function note(overrides = {}) {
  return { id: noteId, student_id: 'learner-test', course_id: 'machine_learning', title: '损失函数',
    content_md: '# 我的理解\n\n均方误差 $L=(y-\\hat y)^2$。', revision: 1, content_hash: 'example-hash',
    knowledge_point_ids: ['linear_regression_loss'], created_via: 'manual',
    created_at: '2026-10-20T08:00:00Z', updated_at: '2026-10-20T08:00:00Z', index_status: 'disabled', ...overrides }
}
export function notesStore(initial = {}) {
  const data = copy(initial)
  return { read: vi.fn(owner => copy(data[owner] || {})), write: vi.fn((owner, value) => {
    data[owner] = copy(value); return true
  }) }
}
export function notesApi(initial = []) {
  const data = new Map(initial.map(value => [`${value.student_id}:${value.id}`, copy(value)]))
  const key = (owner, id) => `${owner}:${id}`
  const missing = () => new ApiError('笔记不存在', { status: 404 })
  const conflict = () => new ApiError('版本已变化', { status: 409 })
  return { data,
    notes: vi.fn(async (owner, q = '', point = '') => ({ items: [...data.values()]
      .filter(value => value.student_id === owner && value.title.includes(q) && (!point || value.knowledge_point_ids.includes(point)))
      .map(copy), total: data.size })),
    note: vi.fn(async (owner, id) => {
      if (!data.has(key(owner, id))) throw missing()
      return copy(data.get(key(owner, id)))
    }),
    createNote: vi.fn(async (owner, body) => {
      const value = note({ ...body, student_id: owner }); data.set(key(owner, body.id), value); return copy(value)
    }),
    updateNote: vi.fn(async (owner, id, body) => {
      const value = data.get(key(owner, id)); if (!value) throw missing()
      if (body.expected_revision !== value.revision) throw conflict()
      const { expected_revision, ...changes } = body
      const updated = { ...value, ...changes, revision: value.revision + 1 }
      data.set(key(owner, id), updated); return copy(updated)
    }),
    deleteNote: vi.fn(async (owner, id, revision) => {
      const value = data.get(key(owner, id)); if (!value) throw missing()
      if (revision !== value.revision) throw conflict()
      data.delete(key(owner, id))
    }),
    importNote: vi.fn(async (owner, body) => {
      const bytes = Uint8Array.from(atob(body.content_base64), char => char.charCodeAt(0))
      const value = note({ id: body.id, student_id: owner, title: body.file_name.replace(/\.[^.]+$/, '').slice(0, 120),
        content_md: new TextDecoder().decode(bytes).replace(/\r\n?/g, '\n'), knowledge_point_ids: [], created_via: 'import' })
      data.set(key(owner, body.id), value); return { ...copy(value), import_warnings: [] }
    }),
  }
}
export function deferred() {
  let resolve, reject
  const promise = new Promise((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}
export function file(name, text) {
  const bytes = typeof text === 'string' ? new TextEncoder().encode(text) : text
  return { name, size: bytes.length, arrayBuffer: async () => bytes.buffer }
}
